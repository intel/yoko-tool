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

"""The standard python packaging script."""

import re
from setuptools import setup, find_packages

def get_version(filename):
    """Fetch the project version number."""

    ver = None

    with open(filename, "r") as fobj:
        for line in fobj:
            matchobj = re.match(r'^VERSION = "(\d+.\d+)"$', line)
            if matchobj:
                ver = matchobj.group(1)
                break
    assert ver
    return ver

setup(
    name="yoko-tool",
    description="Tool to control the Yokogawa power meters",
    author="Artem Bityutskiy",
    author_email="artem.bityutskiy@linux.intel.com",
    version=get_version("yokolibs/yokotool.py"),
    entry_points={
        'console_scripts': ['yokotool=yokolibs.yokotool:main'],
    },
    data_files=[('share/man/man1', ['docs/man1/yokotool.1']),
                ("share/yoko-tool", ["yokotool.conf"])],
    packages=find_packages(exclude=["test*"]),
    license='GPLv2',
    install_requires=["pyserial", "colorama", "argcomplete"],
    long_description="""This package provides yokotool - a Linux command-line tool for controlling
                        Yokogawa power meters. There are also python modules providing the API for
                        python programs.""",
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research"
        "Topic :: System :: Hardware",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Programming Language :: Python :: 3 :: Only",
        "Development Status :: 4 - Beta",
    ],
)
