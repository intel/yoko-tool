#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (c) 2013-2018 Intel, Inc.
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

"""
This is a py.test configuration file that adds the the '--devspec' option support. This option
allows users to specify the power meters to run the tests on.
"""

def pytest_addoption(parser):
    """Add custom pytest options."""

    text = "The device node path or the configuration files section names defining the power " \
           "meters to run the tests for."
    parser.addoption("--devspec", action="append", default=[], help=text)
    parser.addoption("--loglevel", action="store", default="WARNING", help="Set logging level.")

def pytest_generate_tests(metafunc):
    """Run tests for the custom options."""

    if 'devspec' in metafunc.fixturenames:
        metafunc.parametrize("devspec", metafunc.config.getoption('devspec'))
