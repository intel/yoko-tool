#!/usr/bin/env python
#
# Copyright (C) 2013-2020 Intel Corporation
# SPDX-License-Identifier: GPL-2.0-only
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

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
