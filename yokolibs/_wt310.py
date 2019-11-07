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
This module implements the Yokogawa WT310 power meter support. It also works for WT330 series, but
only one input element is supported.
"""

from __future__ import absolute_import, division, print_function
import re
from collections import OrderedDict
from yokolibs import _yokobase
from yokolibs._exceptions import Error

_MAX_DATA_ITEMS = 10
_ELEMENTS_COUNT = 1

# WT310-specific data items.
_WT310_DATA_ITEMS = OrderedDict([
    ("Vmin", "minimum voltage"),
    ("Imin", "minimum current"),
    ("Pmax", "maximum power"),
    ("Pmin", "minimum power"),
    ("Vrange", "voltage range"),
    ("Irange", "current range"),
])

# WT310 Data Item Translation Table - maps protocol-level data item names to "human" data item
# names.
_DITT = (
    ("V", "U"),
    ("Fv", "Fu"),
    ("Vmax", "Uppeak"),
    ("Vmin", "Umpeak"),
    ("Imax", "Ippeak"),
    ("Imin", "Impeak"),
    ("Pmax", "Pppeak"),
    ("Pmin", "Pmpeak"),
    ("Vrange", "Urange"),
)

# WT310 requires these math functions to end with the element number, e.g., cfv1.
_MATH_NAMES_WITH_ELEMENTS = set(("cfv", "cfi", "avw"))

# Commands.
_RAW_COMMANDS = (
    ("get-line-filter", ":INP:FILT:LINE?"),
    ("set-line-filter", ":INP:FILT:LINE"),
    ("get-freq-filter", ":INP:FILT:FREQ?"),
    ("set-freq-filter", ":INP:FILT:FREQ"),
    ("get-max-hold", ":MEAS:MHOL?"),
    ("set-max-hold", ":MEAS:MHOL"),
    ("get-current-auto-range", ":INP:CURR:AUTO?"),
    ("set-current-auto-range", ":INP:CURR:AUTO"),
    ("get-current-range", ":INP:CURR:RANG?"),
    ("set-current-range", ":INP:CURR:RANG"),
    ("get-voltage-auto-range", ":INP:VOLT:AUTO?"),
    ("set-voltage-auto-range", ":INP:VOLT:AUTO"),
    ("get-voltage-range", ":INP:VOLT:RANG?"),
    ("set-voltage-range", ":INP:VOLT:RANG"),
    ("get-keys-locking", ":SYST:KLOC?"),
    ("set-keys-locking", ":SYST:KLOC"),
    ("get-measurement-mode", ":INP:MODE?"),
    ("set-measurement-mode", ":INP:MODE"),
    ("get-sync-source", ":INP:SYNC?"),
    ("set-sync-source", ":INP:SYNC"),
    ("get-crest-factor", ":INP:CFAC?"),
    ("set-crest-factor", ":INP:CFAC"),
    ("get-wiring-system", ":INP:WIR?"),
    ("get-smoothing-status", ":MEAS:AVER:STATE?"),
    ("set-smoothing-status", ":MEAS:AVER:STATE"),
    ("get-smoothing-type", ":MEAS:AVER:TYPE?"),
    ("set-smoothing-type", ":MEAS:AVER:TYPE"),
    ("get-smoothing-factor", ":MEAS:AVER:COUN?"),
    ("set-smoothing-factor", ":MEAS:AVER:COUN"),
    ("get-integration-state", ":INTEG:STAT?"),
    ("set-math", ":MATH"),
    ("set-compat-mode", ":SYST:COMM:COMM"),
    ("get-data-format", ":NUM:FORM?"),
    ("set-data-format", ":NUM:FORM"),
    ("get-data-items-count", ":NUM:NORM:NUM?"),
    ("set-data-items-count", ":NUM:NORM:NUM"),
    ("read-data", ":NUM:NORM:VAL?"),
)

# Valid arguments for some of the commands.
_CHOICES = (
    {
        "commands" : ("get-integration-state",),
        "choices" : ("start", "stop", "reset", "timeup", "error"),
    },
    {
        "commands" : ("get-data-format", "set-data-format"),
        "choices" : ("ascii", "float"),
    },
    {
        "commands" : ("get-keys-locking", "set-keys-locking"),
        "choices" : _yokobase.ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-compat-mode", "set-compat-mode"),
        "choices" : ("WT200", "WT300"),
    },
)

def _math_response_tweak(_, value):
    """Remove the element number part from a math function name."""

    match = re.search(r"([^\d]*)(\d+)$", value)
    if match:
        value = match.group(1)
    if value.startswith("cfu"):
        value = "cfv" + value[3:]
    return value

def _math_input_tweak(_, value):
    """
    Do the opposite to '_math_response_tweak()' function - append '1' to the math function names
    that do not end with an element number, but it is required.
    """

    if value in _MATH_NAMES_WITH_ELEMENTS:
        value += "1"
    if value.startswith("cfv"):
        value = "cfu" + value[3:]
    return value

# The tweaks.
_TWEAKS = {
    "get-smoothing-type" : {
        "response-tweaks" : (_yokobase.to_lower_tweak,),
    },
    "get-integration-state" : {
        "response-tweaks" : (_yokobase.to_lower_tweak,),
    },
    "get-keys-locking" : {
        "response-tweaks" : (_yokobase.on_off_tweak,),
    },
    "get-data-format" : {
        "response-tweaks" : (_yokobase.to_lower_tweak,),
    },
    "get-math" : {
        "response-tweaks" : (_yokobase.to_lower_tweak, _math_response_tweak),
    },
    "set-math" : {
        "input-tweaks"    : (_yokobase.to_lower_tweak, _math_input_tweak,),
    },
}

def _verify_data_items_count(item):
    """Verify whether or not the amount of data items range from 1 to '_MAX_DATA_ITEMS'."""

    return _yokobase.is_in_range(item, 1, _MAX_DATA_ITEMS)

class WT310(_yokobase.YokoBase):
    """This class implements Yokogawa WT310 power meter."""

    pmtypes = ("wt310", "wt330", "wt333", "wt333")
    name = "Yokogawa WT310 or WT33x"

    def _verify_math_name(self, name):
        """
        Verify whether of not 'name' argument is a valid math function. Please, see the
        'WT310/WT310HC/WT330 Digital Power Meter Communication Interface User's Manual', page 6-16.
        """

        if name is None:
            return False

        match = re.search(r"([^\d]*)(\d+)$", name)
        if match:
            if not _yokobase.is_in_range(match.group(2), 1, _ELEMENTS_COUNT):
                return False
            name = match.group(1)
            if name not in _MATH_NAMES_WITH_ELEMENTS:
                return False

        if name not in self.commands["set-math"]["choices-set"]:
            return False

        return True

    def _iter_data_item_commands(self):
        """Yield the (cmd_part, get_cmd, set_cmd) tuples for each possible data item command."""

        for num in range(1, self.max_data_items + 1):
            yield (num, "get-data-item%d" % num, "set-data-item%d" % num)

    def _configure_data_items_cmd(self, cmd, items):
        """Set the data items that the power meter will return on the next read command."""

        items = super(WT310, self)._configure_data_items_cmd(cmd, items)

        if items:
            self._command("set-data-items-count", len(items))
            for idx, data_item in enumerate(items, 1):
                self._command("set-data-item%d" % idx, data_item)

    def _get_data_tweak(self, cmd, response):
        """Process the data returned by the 'get-data' command."""

        response = [str(float(v)) for v in response.split(",")]
        return super(WT310, self)._get_data_tweak(cmd, response)

    def _add_wt310_commands(self):
        """Add WT310-specific commands."""

        self.commands["get-integration-state"] = {
            "property-descr" : "integration state",
            "descr" : "get the integration feature state",
        }
        self.commands["get-keys-locking"] = {
            "property-descr" : "keys lock status",
            "descr" : "check whether device's physical keys are locked or not",
        }
        self.commands["set-keys-locking"] = {
            "property-descr" : "keys lock status",
            "descr" : "lock/unlock device's physical keys",
        }

        # Add commands for getting and setting data items.
        for _, get_cmd, set_cmd in self._iter_data_item_commands():
            self._commands[get_cmd] = {}
            self._commands[set_cmd] = {}

    def _populate_arg_verify_funcs(self):
        """Populate the 'self._commands' dictionary with command verification functions."""

        self._commands["set-data-items-count"]["verify-arg"] = _verify_data_items_count
        self._commands["set-math"]["verify-arg"] = self._verify_math_name

    def _populate_raw_commands(self, raw_commands):
        """Populate the raw (wire) power meter commands to 'self._commands'."""

        super(WT310, self)._populate_raw_commands(raw_commands)

        # Cover the data item get/set commands as well.
        for cmd_part, get_cmd, set_cmd in self._iter_data_item_commands():
            self._commands[get_cmd] = {}
            self._commands[get_cmd]["raw-cmd"] = ":NUM:NORM:ITEM%d?" % cmd_part
            self._commands[set_cmd] = {}
            self._commands[set_cmd]["raw-cmd"] = ":NUM:NORM:ITEM%d" % cmd_part

        self._add_command_func("configure-data-items", self._configure_data_items_cmd)
        self._populate_raw_commands_post()

    def __init__(self, transport):
        """The class constructor."""

        # Call the base class constructor first.
        super(WT310, self).__init__(transport)

        self._pmtype = None
        self.max_data_items = _MAX_DATA_ITEMS

        self._populate_data_items(_WT310_DATA_ITEMS, _DITT)
        self._add_wt310_commands()
        self._populate_choices(_CHOICES)
        self._populate_raw_commands(_RAW_COMMANDS)
        self._populate_tweaks(_TWEAKS)
        self._populate_arg_verify_funcs()
        self._populate_errors_map_map()

        self._init_pmeter()

        # Verify that we are dealing with a WT310.
        ids = self._command("get-id")
        split_ids = ids.split(",")
        if len(ids) < 2:
            raise Error("'%s' has ID string '%s' and it does not look like a WT310 power meter"
                        % (transport.devnode, ids))

        self.pmtype = split_ids[1].strip().lower()
        if not any([self.pmtype.startswith(pmtype) for pmtype in self.pmtypes]):
            raise Error("'%s' has ID string '%s' and it does not look like a WT310 power meter"
                        % (transport.devnode, ids))

        # Set data format to ascii.
        self._command("set-data-format", "ascii")
        # Enable WT310 commands
        self._command("set-compat-mode", "WT300")
        # Enable verbose mode which makes the power meter reply with full strings instead of cut
        # ones.
        self._command("set-verbose-mode", "on")
