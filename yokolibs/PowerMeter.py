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

# Meta-commands do not map to a power meter command but implement a higher-level logic
_META_COMMANDS = {
    "set-data-items" : {
        "has-response" : False,
        "has-argument" : True,
    },
}

class PowerMeter(object):
    """This class extends the capabilities of 'WT310' class."""

    def __init__(self, devnode):
        """The class constructor."""

        transport_obj = _transport.USBTMC(devnode)
        self._meter = _wt310.WT310(transport_obj)

        self._meter.commands.update(_META_COMMANDS)
        self._meter._command_map.update({
            "set-data-items"   : self._set_data_items,
        })

    def __getattr__(self, name):
        """
        If an attribute is not found in PowerMeter, then it is searched for in 'self._meter', the
        object representing a specific power meter model (eg., WT310).
        """
        return getattr(self._meter, name)

    def _set_data_items(self, _cmd, data_items):
        """Configure the power meter before reading data."""

        if len(data_items) > self._meter.max_data_items:
            raise Error("too many data items to read, please, specify at most %s items"
                        % self._meter.max_data_items)

        for idx, data_item in enumerate(data_items, 1):
            self._meter._verify_argument("set-data-item%d" % idx, data_item)

        self._meter.command("set-data-items-count", len(data_items))
        for idx, data_item in enumerate(data_items, 1):
            self._meter.command("set-data-item%d" % idx, data_item)
