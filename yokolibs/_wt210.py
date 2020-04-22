#!/usr/bin/env python
#
# Copyright (C) 2013-2020 Intel Corporation
# SPDX-License-Identifier: GPL-2.0-only
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

# Historical note: this module was created by copying the _wt310.py module.

"""
This module implements the Yokogawa WT210 power meter support.
"""

from __future__ import absolute_import, division, print_function
import re
from yokolibs import _yokobase
from yokolibs._exceptions import Error, ErrorBadResponse

_MAX_DATA_ITEMS = 19

# WT210 Data Item Translation Table - maps protocol-level data item names to "human" data item
# names.
_DITT = (
    ("I", "A"),
    ("P", "W"),
    ("S", "Va"),
    ("Q", "Var"),
    ("Lambda", "PF"),
    ("Phi", "Degree"),
    ("Fv", "VHz"),
    ("Fi", "AHz"),
    ("Vmax", "Vpk"),
    ("Imax", "Apk"),
)

# Commands.
_RAW_COMMANDS = (
    ("get-line-filter", ":CONF:LFILT?"),
    ("set-line-filter", ":CONF:LFILT"),
    ("get-freq-filter", ":CONF:FILT?"),
    ("set-freq-filter", ":CONF:FILT"),
    ("get-max-hold", ":CONF:MHOL?"),
    ("set-max-hold", ":CONF:MHOL"),
    ("get-current-auto-range", ":CONF:CURR:AUTO?"),
    ("set-current-auto-range", ":CONF:CURR:AUTO"),
    ("get-current-range", ":CONF:CURR:RANG?"),
    ("set-current-range", ":CONF:CURR:RANG"),
    ("get-voltage-auto-range", ":CONF:VOLT:AUTO?"),
    ("set-voltage-auto-range", ":CONF:VOLT:AUTO"),
    ("get-voltage-range", ":CONF:VOLT:RANG?"),
    ("set-voltage-range", ":CONF:VOLT:RANG"),
    ("get-measurement-mode", ":CONF:MODE?"),
    ("set-measurement-mode", ":CONF:MODE"),
    ("get-sync-source", ":CONF:SYNC?"),
    ("set-sync-source", ":CONF:SYNC"),
    ("get-crest-factor", ":CONF:CFAC?"),
    ("set-crest-factor", ":CONF:CFAC"),
    ("get-wiring-system", ":CONF:WIR?"),
    ("get-smoothing-status", ":CONF:AVER:STAT?"),
    ("set-smoothing-status", ":CONF:AVER:STAT"),
    ("get-smoothing-type", ":CONF:AVER:TYPE?"),
    ("set-smoothing", ":CONF:AVER:TYPE"),
    ("get-smoothing-factor", ":CONF:AVER:TYPE?"),
    ("set-math-type", ":MATH:TYPE"),
    ("set-math-cfac", ":MATH:CFAC"),
    ("set-math-aver", ":MATH:AVER"),
    ("set-math-arit", ":MATH:ARIT"),
    ("read-data", ":MEAS:VAL?"),
)

# Valid arguments for some of the commands.
_CHOICES = (
    {
        "commands" : ("get-integration-state",),
        # In case of WT210 we did not find a non-disruptive way to distinguish between the
        # integration start and stop states.
        "choices" : ("start or stop", "reset"),
    },
)

def _math_response_tweak(_, value):
    """
    Remove the '1' part from a math function name. Additionally, add a comma between the math
    function name and the element number which makes math functions look consistent with data item
    names.
    """

    parts = value.split(";")
    if parts[0] == "ARITHMETIC":
        return parts[1].lower()
    elif parts[1] == "A,1":
        return "cfi"
    elif parts[1] == "V,1":
        return "cfv"
    elif parts[1] == "W,1":
        return "avw"

    raise Error("unknown power meter math function '%s'" % value)

# The tweaks.
_TWEAKS = {
    "get-smoothing-type" : {
        "response-tweaks" : (_yokobase.to_lower_tweak, lambda _, x: x.split(",")[0]),
    },
    "get-smoothing-factor" : {
        "response-tweaks" : (_yokobase.to_lower_tweak, lambda _, x: x.split(",")[1]),
    },
    "get-math" : {
        "response-tweaks" : (_math_response_tweak,),
    },
}

class WT210(_yokobase.YokoBase):
    """This class implements Yokogawa WT210 power meter."""

    pmtypes = ("wt210", )
    name = "Yokogawa WT210"

    def _set_math_cmd(self, _, arg):
        """Implement the 'set-math' command."""

        if arg in ("cfi", "cfv"):
            self._command("set-math-type", "CFAC")
            if arg == "cfi":
                self._command("set-math-cfac", "A,1")
            else:
                self._command("set-math-cfac", "V,1")
        elif arg == "avw":
            self._command("set-math-type", "AVER")
            self._command("set-math-aver", "W,1")
        else:
            self._command("set-math-type", "ARIT")
            self._command("set-math-arit", arg)

    def _get_integration_state_cmd(self, *_):
        """Emulate the 'get-integration-state' command."""

        # Line filter changing in prohibited when integreation is in a non-reset state.
        # Get the current value in order to set the same value later. Retry for a second becasue
        # sometimes it fails when executed right after 'start-integration'.
        state = self._command("get-line-filter")

        try:
            self._command("set-line-filter", state)
        except Error:
            return "start or stop"
        return "reset"

    def _set_smoothing_cmd(self, cmd, arg):
        """
        Smoothing factor and smoothing type can only be changed together using one WT210 command.
        This function implements the 'set-smoothing-type' and 'set-smoothing-factor' commands and
        sets them independently.
        """

        if cmd == "set-smoothing-type":
            typ = arg
            factor = self._command("get-smoothing-factor")
        elif cmd == "set-smoothing-factor":
            typ = self._command("get-smoothing-type")
            factor = arg
        else:
            assert False

        self._command("set-smoothing", arg="%s,%s" % (typ, factor))

    def _configure_data_items_cmd(self, cmd, items):
        """Set the data items that the power meter will return on the next read command."""

        items = super(WT210, self)._configure_data_items_cmd(cmd, items)
        if not items:
            return

        self._wt210_items_to_read = items
        items = set(items)
        self._wt210_item_indexes = {}
        idx = 0
        for item in self._data_items:
            if item in self._vdata_items:
                continue
            if item in items:
                self._wt210_item_indexes[item] = idx
                idx += 1
                self._command("set-data-item-%s" %  item, "on")
            else:
                self._command("set-data-item-%s" %  item, "off")

    def _get_data_tweak(self, cmd, response):
        """Process the data returned by the 'get-data' command."""

        items = []
        for item in response.split(","):
            item = float(item)
            if item >= 9.9E37:
                items.append("nan")
            else:
                items.append(str(item))

        result = []
        for item in self._wt210_items_to_read:
            result.append(items[self._wt210_item_indexes[item]])

        return super(WT210, self)._get_data_tweak(cmd, result)

    def _iter_data_item_commands(self):
        """Yield the (cmd_part, get_cmd, set_cmd) tuples for each possible data item command."""

        for name in self._data_items:
            yield (name, "get-data-item-%s" % name, "set-data-item-%s" % name)

    def _populate_raw_commands(self, raw_commands):
        """Populate the raw (wire) power meter commands to 'self._commands'."""

        super(WT210, self)._populate_raw_commands(raw_commands)

        # Cover the data item get/set commands as well.
        for cmd_part, get_cmd, set_cmd in self._iter_data_item_commands():
            name = self._ditt["htop"].get(cmd_part, cmd_part)
            self._commands[get_cmd] = {}
            self._commands[get_cmd]["raw-cmd"] = ":MEAS:ITEM:%s?" % name
            self._commands[set_cmd] = {}
            self._commands[set_cmd]["raw-cmd"] = ":MEAS:ITEM:%s" % name

        self._add_command_func("configure-data-items", self._configure_data_items_cmd)
        self._add_command_func("set-smoothing-type", self._set_smoothing_cmd)
        self._add_command_func("set-smoothing-factor", self._set_smoothing_cmd)
        self._add_command_func("get-integration-state", self._get_integration_state_cmd)
        self._add_command_func("set-math", self._set_math_cmd)

        self._populate_raw_commands_post()

    def __init__(self, transport):
        """The class constructor."""

        # Call the base class constructor first.
        super(WT210, self).__init__(transport)

        self.pmtype = "wt210"
        self.max_data_items = _MAX_DATA_ITEMS

        # Indexes for the data items that were configured to be read by 'configure-data-items'.
        self._wt210_item_indexes = None
        # List of items configured to be read by 'configure-data-items'.
        self._wt210_items_to_read = None

        self._populate_data_items({}, _DITT)
        self._populate_choices(_CHOICES)
        self._populate_raw_commands(_RAW_COMMANDS)
        self._populate_tweaks(_TWEAKS)
        self._populate_arg_verify_funcs()
        self._populate_errors_map_map()

        try:
            self._init_pmeter()
        except ErrorBadResponse as err:
            msg = "%s\n%s" % (err, "Did you switch your WT210 to the '488.2' mode?")
            raise ErrorBadResponse(msg=msg)

        # The ID string of WT210 does not seem to contain a "WT210", so we cannot easily figure out
        # the power meter type.
        ids = self._command("get-id")

        match = re.match(r"WT\d+", ids)
        if match and match.group(0).lower() != "wt210":
            raise Error("'%s' is not a WT210 power meter" % transport.devnode)

        self._command("set-remote-mode", "on")

        # Run a command which is specific to WT210 to verify we are really talking to a WT210.
        self._command("get-line-filter")
