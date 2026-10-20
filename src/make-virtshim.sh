#!/bin/bash
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

uid=$1
input=/source_images/$2
output=/build/$3
tmp_output=/build/tmp_$3

[ ! -f "${input}" ] && echo "Input file \"${input}\" not found!" && exit 1

# Copy cloud-init templates to a random directory in /tmp.
ci_iso=/tmp/cloud-init.iso
dir=/tmp/vs.$RANDOM
mkdir "${dir}"
cp /src/cloud-init/user-data "${dir}"
cp /src/cloud-init/meta-data "${dir}"

# Bundle files from files/ into user-data.
echo "write_files:" >> "${dir}/user-data"
while read file; do
  content=$(base64 -w 0 "${file}")
  path=${file:10}
  perms=0$(stat -c "%a" "${file}")
  cat << _EOF_ >> "${dir}/user-data"
  - encoding: b64
    content: ${content}
    owner: root:root
    path: ${path}
    permissions: '${perms}'
_EOF_
done < <(find /src/files/ -type f)

# Make the cloud-init ISO for the virtshim installation.
/usr/bin/genisoimage \
    -output "${ci_iso}" \
    -volid cidata \
    -joliet \
    -rock \
    "${dir}/user-data" \
    "${dir}/meta-data"

# Copy the source image to /build.
/usr/bin/cp "${input}" "${tmp_output}"
/usr/bin/chown ${uid}:${uid} "${tmp_output}"

# Resize the image to 50G.
# (cloud-init will automatically resize the partitions and filesystem.)
/usr/bin/qemu-img resize ${tmp_output} 50G

# Run QEMU with cloud-init to setup the virtshim image.
/usr/bin/qemu-system-x86_64 \
    -nic user,model=virtio \
    -m 512 \
    -nographic \
    -hda "${tmp_output}" \
    -cdrom "${ci_iso}"

mv -f "${tmp_output}" "${output}"