#!/usr/bin/env python3
#
# Copyright (c) 2024 Nutanix, Inc. All rights reserved.
#
# Author: Felipe Franciosi <felipe@nutanix.com>
#
# This file is part of virtshim.
#
# virtshim is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see https://www.gnu.org/licenses/.

from random import randint
from subprocess import run
import json
import os

def get_blk_devs():
    ret = run(['/usr/bin/lsblk', '-J'],
              capture_output=True, check=False)
    out = json.loads(ret.stdout)
    devs = [dev['name']
            for dev in out['blockdevices']
            if dev.get('type') == 'disk' and
               not '/' in dev['mountpoints'] and
               not any('/' in child['mountpoints']
                       for child in dev.get('children', {}))]
    return devs

def get_num_cpus():
    ret = run(['/usr/bin/nproc'],
              capture_output=True, check=False)
    return int(ret.stdout)

def get_memtotal_mb():
    with open('/proc/meminfo', 'r', encoding='utf-8') as fpe:
        for line in fpe.readlines():
            if line.startswith('MemTotal:'):
                total = line.split()[1]
            break
        else:
            raise ValueError('MemTotal not found')
    return int(int(total)/1024)

def get_dev_mac(dev):
    with open(f'/sys/class/net/{dev}/address', 'r', encoding='utf-8') as fpe:
        return fpe.read().strip()

def set_dev_mac(dev, mac):
    run(['/usr/sbin/ip', 'link', 'set', 'dev', dev, 'address', mac], check=True)

def new_random_mac():
    return '52:54:00:%02x:%02x:%02x' % tuple(randint(0, 255) for v in range(3))

def add_dev_to_bridge(dev, bridge):
    run(['/usr/sbin/ip', 'link', 'set', 'dev', dev, 'master', bridge],
        check=True)

def new_tap(dev):
    run(['/usr/sbin/ip', 'tuntap', 'add', 'dev', dev, 'mode', 'tap'],
        check=True)

def new_bridge(bridge):
    run(['/usr/sbin/ip', 'link', 'add', 'name', bridge,
         'address', new_random_mac(), 'type', 'bridge'], check=True)

def set_dev_up(dev):
    run(['/usr/sbin/ip', 'link', 'set', 'dev', dev, 'up'], check=True)

def flip_mac_bit(mac):
    return hex(int(mac[:2], 16) ^ 0x80)[2:] + mac[2:]

def get_net_taps():
    """
    Ensure every network interface is on a bridge alongside a tap device and
    return the list of taps.
    When setting up the networking, copy the ens mac address to the tap, but
    flip the most significant bit of its first byte. This allows the script
    to later bring up the L2 VM with the same mac as the original ens without
    confusing the bridge. The ens gets a random mac address during the swap.
    """
    net_ifaces = os.listdir('/sys/class/net')

    # Map out all tap, ens, and bridges (which follow our naming convention).
    taps = [x for x in net_ifaces if x.startswith('tap')]
    enss = [x for x in net_ifaces if x.startswith('ens')]
    brs = [x for x in net_ifaces if x.startswith('br')]

    # Filter out enss which aren't virtio-net.
#    for ens in enss[:]:
#        path = f'/sys/class/net/{ens}/device/driver'
#        if not (os.path.exists(path) and \
#                os.path.basename(os.readlink(path)) == 'virtio_net'):
#            enss.remove(ens)

    # If any taps/brs, get their highest index.
    next_tap = 0
    if taps:
        next_tap = max(map(lambda x: int(x[3:]), taps)) + 1

    next_br = 0
    if brs:
        next_br = max(map(lambda x: int(x[2:]), brs)) + 1

    # Create a map from bridge to enss/tap.
    br_map = {}
    for bridge in brs:
        br_map[bridge] = {'enss': [], 'tap': None}

        # Populate the entry with their taps/enss.
        for dev in os.listdir(f'/sys/devices/virtual/net/{bridge}/brif'):
            if dev.startswith('ens'):
                br_map[bridge]['enss'].append(dev)
                enss.remove(dev)
                continue
            if dev.startswith('tap'):
                # Only take one tap per bridge:
                if br_map[bridge]['tap'] is None:
                    br_map[bridge]['tap'] = dev
                else:
                    pass
                    # FIXME: Log that @dev is being ignored.
                taps.remove(dev)

        # We don't want existing bridges without enss.
        if not br_map[bridge]['enss']:
            del br_map[bridge]
            continue

        # Any bridges left must have a tap device and be up.
        if br_map[bridge]['tap'] is None:
            tap = f'tap{next_tap}'
            next_tap += 1
            new_tap(tap)
            ens_mac = get_dev_mac(ens)
            set_dev_mac(ens, new_random_mac())
            set_dev_mac(tap, flip_mac_bit(ens_mac))

            add_dev_to_bridge(tap, bridge)
            br_map[bridge]['tap'] = tap

        # Bring bridge and enss up.
        set_dev_up(bridge)
        for ens in br_map[bridge]['enss']:
            set_dev_up(ens)

    # Any enss dangling? Throw them into bridges alongside a tap.
    for ens in enss:
        ens_mac = get_dev_mac(ens)
        set_dev_mac(ens, new_random_mac())

        bridge = f'br{next_br}'
        next_br += 1
        new_bridge(bridge)

        tap = f'tap{next_tap}'
        next_tap += 1
        new_tap(tap)
        set_dev_mac(tap, flip_mac_bit(ens_mac))

        add_dev_to_bridge(ens, bridge)
        add_dev_to_bridge(tap, bridge)
        set_dev_up(bridge)
        set_dev_up(ens)

        br_map[bridge] = {'enss': [ens], 'tap': tap}

    return [br_map[x]['tap'] for x in br_map]

def get_mem_overhead_mb():
    # TODO: Calculate how much to reserve.
    return 1024

def main():
    vm_mem_mb = get_memtotal_mb() - get_mem_overhead_mb()
    assert vm_mem_mb > 0
    num_cpus = get_num_cpus()
    blk_devs = get_blk_devs()
    tap_devs = get_net_taps()

    qemu_cmdline = [
        '/usr/bin/qemu-system-x86_64',
        '-vnc', '127.0.0.1:0',
        '-device', 'usb-ehci,id=usb-bus',
        '-device', 'usb-tablet',
        '-smp', f'{num_cpus}', # FIXME: Mimic L1's topology.
        '-cpu', 'max',
        '-m', f'{vm_mem_mb}',
        '-device', 'pvscsi,id=scsi0',
    ]

    for idx, blk_dev in enumerate(blk_devs):
        qemu_cmdline.extend([
            '-device', f'scsi-hd,drive=drive{idx},bus=scsi0.0,channel=0,scsi-id={idx},lun=0',
            '-drive', f'file=/dev/{blk_dev},if=none,id=drive{idx},format=raw'])

    for tap in tap_devs:
        mac = flip_mac_bit(get_dev_mac(tap))
        qemu_cmdline.extend(['-nic', f'tap,model=vmxnet3,ifname={tap},mac={mac}'])

    if os.path.exists('/dev/kvm'):
        qemu_cmdline.extend(['-accel', 'kvm'])

    if os.path.exists('/dev/sr0'):
        qemu_cmdline.extend(['-cdrom', '/dev/sr0'])

    pid = os.fork()
    if pid == 0:
        # Child.
        os.execv(qemu_cmdline[0], qemu_cmdline)
        os.exit(1)

    try:
        os.waitpid(pid, 0)
    except Exception:
        pass

    os.execl('/usr/sbin/halt', '/usr/sbin/halt', '-p')

if __name__ == '__main__':
    main()
