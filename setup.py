#!/usr/bin/env python
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (c) 2014-2016 Intel, Inc.
# License: GPLv2
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.

import re
from setuptools import setup, find_packages

def get_version():
    """Fetch the project version number from the 'yokotool' file."""

    with open("yokotool", "r") as fobj:
        for line in fobj:
            matchobj = re.match(r'^VERSION = "(\d+.\d+)"$', line)
            if matchobj:
                return matchobj.group(1)

    return None

setup(
    name="yoko-tools",
    description="Tool to control the Yokogawa WT310 power meter",
    author="Artem Bityutskiy",
    author_email="artem.bityutskiy@linux.intel.com",
    version=get_version(),
    scripts=['yokotool'],
    packages=find_packages(exclude=["test*"]),
    license='GPLv2',
    long_description="""This package provides yokotool - a Linux command-line tool for controlling
                        the Yokogawa WT310 power meter. Namely, it allows for configuring the power
                        meter and reading the measurements data. There are also python modules which
                        provide the power meter control APIs for external python programs."""
)
