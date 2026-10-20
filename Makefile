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

# Debian setup.
DEBIAN_FAMILY ?= trixie
DEBIAN_MAJOR ?= 13
DEBIAN_ARCH ?= amd64
DEBIAN_FLAVOUR ?= generic
DEBIAN_BUILD ?= latest

SOURCE_IMAGES = source_images
SCRATCH = scratch
BUILD = build

UID = $(shell /usr/bin/id -u)
BASE_URL = https://cdimage.debian.org/images/cloud/$(DEBIAN_FAMILY)/$(DEBIAN_BUILD)
ifeq ($(DEBIAN_BUILD), latest)
	QCOW2 = debian-$(DEBIAN_MAJOR)-$(DEBIAN_FLAVOUR)-$(DEBIAN_ARCH).qcow2
else
	QCOW2 = debian-$(DEBIAN_MAJOR)-$(DEBIAN_FLAVOUR)-$(DEBIAN_ARCH)-$(DEBIAN_BUILD).qcow2
endif
QCOW2_URL = $(BASE_URL)/$(QCOW2)
QCOW2_PATH = $(SOURCE_IMAGES)/$(QCOW2)
OUTPUT = build/virtshim.qcow2

all: $(QCOW2_PATH) $(OUTPUT)

docker:
	docker build -t virtshim docker/
.PHONY: docker

$(OUTPUT): $(shell find src -type f)
	docker/run.sh "/src/make-virtshim.sh $(UID) $(QCOW2) virtshim.qcow2"

$(QCOW2_PATH):
	curl -Lo $(QCOW2_PATH) $(QCOW2_URL)

clean:
	-rm $(QCOW2_PATH)
	-rm $(OUTPUT)
	-docker image rm virtshim:latest

# vim: noet
