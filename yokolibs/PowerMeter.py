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

import re
import time

from yokolibs import _transport, _wt310
from yokolibs._exceptions import Error

# Some data items come from the power meter (e.g., power, current, voltage, etc), others are
# generated on-the-fly by this library and we refer to them as 'virtual data items'.
_VDATA_ITEMS = (
    ("T", "time stamp"),
    ("J", "Joules"),
)

class PowerMeter(object):
    """This class extends the capabilities of 'WT310' class."""

    def __init__(self, devnode):
        """The class constructor."""

        transport_obj = _transport.USBTMC(devnode)
        self._meter = _wt310.WT310(transport_obj)

        # The original list of arguments users requested to read
        self._argcopy = None
        # The data items to be read from the power meter
        self._data_items = None
        # The interval is needed to compute the Joules virtual data item
        self._interval = self._meter.command("get-interval")
        # The time stamp virtual data item
        self._timestamp = None

        self._extend_assortments()

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

    def _extend_assortments(self):
        """
        Extend the 'assortments' of the power meter: the description of commands like
        'set-data-item%d' should include the virtual data items.
        """

        vdata_items_descr = ""
        for vdata_item, descr in _VDATA_ITEMS:
            vdata_items_descr += "{} - {}\n".format(vdata_item, descr)

        for cmd in self._meter._assortments:
            if re.match(r"(set-data-item[0-9]+)", cmd):
                self._meter._assortments[cmd]["text-descr"] += vdata_items_descr

    def _get_data_items_to_read(self, data_items):
        """
        Get the list of data items to be read from the power meter. If users request to read
        the 'Joules' virtual data item, we read 'Power' and will use this value to later compute
        the Joules.
        """

        self._data_items = []
        vdata_items = [vitem[0] for vitem in _VDATA_ITEMS]

        for data_item in data_items:
            if data_item not in vdata_items:
                self._data_items.append(data_item)
            elif data_item == "J":
                self._data_items.append("P")

    def _set_data_items(self, data_items):
        """Configure the power meter before reading data."""

        if len(data_items) > self._meter.max_data_items:
            raise Error("too many data items to read, "
                        "please, specify at most {} items".format(self._meter.max_data_items))

        self._get_data_items_to_read(data_items)

        if self._data_items:
            for idx, data_item in enumerate(self._data_items, 1):
                self._meter._verify_argument("set-data-item{}".format(idx), data_item)

            self._meter.command("set-data-items-count", len(self._data_items))
            for idx, data_item in enumerate(self._data_items, 1):
                self._meter.command("set-data-item{}".format(idx), data_item)

        self._argcopy = data_items

    def _inject_vdata_items(self, response):
        """Inject the virtual data items into the read response."""

        updated_response = []
        vdata_items = [vitem[0] for vitem in _VDATA_ITEMS]

        for arg in self._argcopy:
            if arg not in vdata_items:
                updated_response.append(response[0])
                del response[0]
            elif arg == "T":
                updated_response.append(self._timestamp)
            elif arg == "J":
                updated_response.append(str(float(response[0]) * self._interval))
                del response[0]

        return updated_response

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
            self._timestamp = str(time.time())
            response = self._meter.command(cmd, arg)
            if cmd == "set-interval":
                self._interval = arg
            elif cmd == "get-data":
                response = self._inject_vdata_items(response)
        return response
