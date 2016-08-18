#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (c) 2016 Intel, Inc.
# License: GPLv2
# Author: Helia Correia <helia.correia@linux.intel.com>
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
This module implements some high-level logic that complements the functionalities of Yokogawa's
power meters.
"""

from yokolibs import _transport, _wt310
from yokolibs._exceptions import Error

class PowerMeter(object):
    """This class extends the capabilities of 'WT310' class."""

    def __init__(self, devnode):
        """The class constructor."""

        transport_obj = _transport.USBTMC(devnode)
        self._meter = _wt310.WT310(transport_obj)

    def __getattr__(self, name):
        """
        If an attribute is not found in PowerMeter, then it is searched for in 'self._meter', the
        object representing a specific power meter model (eg., WT310).
        """
        return getattr(self._meter, name)
