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

image_name=virtshim

docker image inspect "${image_name}" 1>/dev/null 2>&1
[[ $? -eq 1 ]] && make docker

docker run -it --rm \
    -v "$(pwd)/source_images:/source_images" \
    -v "$(pwd)/build:/build" \
    -v "$(pwd)/src:/src" \
    -p 5900:5900 \
    "${image_name}" \
    /bin/bash -ci "${@}"


#    --device /dev/fuse \
#    --cap-add SYS_ADMIN \
#    --security-opt apparmor:unconfined \
