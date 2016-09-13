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

# pylint: disable=protected-access

from yokolibs import _transport, _wt310
from yokolibs._exceptions import Error

class PowerMeter(object):
    """This class extends the capabilities of 'WT310' class."""

    def __init__(self, devnode):
        """The class constructor."""

        transport_obj = _transport.USBTMC(devnode)
        self._meter = _wt310.WT310(transport_obj)

    def close(self):
        """Close the communication interface with the power meter."""

        if self._meter:
            self._meter.close()
            self._meter = None

    def __getattr__(self, name):
        """
        If an attribute is not found in PowerMeter, then it is searched for in 'self._meter', the
        object representing a specific power meter model (eg., WT310).
        """
        return getattr(self._meter, name)

    def _set_data_items(self, data_items):
        """Configure the power meter before reading data."""

        if len(data_items) > self._meter.max_data_items:
            raise Error("too many data items to read, "
                        "please, specify at most {} items".format(self._meter.max_data_items))

        for idx, data_item in enumerate(data_items, 1):
            self._meter._verify_argument("set-data-item{}".format(idx), data_item)

        self._meter.command("set-data-items-count", len(data_items))
        for idx, data_item in enumerate(data_items, 1):
            self._meter.command("set-data-item{}".format(idx), data_item)

    def command(self, cmd, arg=None):
        """
        Override the 'command()' method of the power meter to intercept the meta-commands like
        'set-data-items'. Meta-commands do not map to power meter commands. Instead, they implement
        a higher-level logic.
        """

        if cmd == "set-data-items":
            self._set_data_items(arg)
            response = None
        else:
            response = self._meter.command(cmd, arg)
        return response
