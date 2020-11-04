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
This module contains the common code shared by all the supported power meters so far. The module is
not supposed to be imported by the end users. Instead, the specific power meter implementation
should be based on this module.
"""

# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines

from __future__ import absolute_import, division, print_function
import time
import logging
from collections import OrderedDict
from yokolibs import Transport
from yokolibs._exceptions import Error, ErrorBadArgument, ErrorBadResponse

# This makes sure all classes are the new-style classes by default.
__metaclass__ = type # pylint: disable=invalid-name

_LOG = logging.getLogger("_yokobase")

# The data items supported by all power meters.
_DATA_ITEMS = OrderedDict([
    ("V", "voltage"),
    ("I", "current"),
    ("P", "active power"),
    ("S", "apparent power"),
    ("Q", "reactive power"),
    ("Lambda", "power factor (λ)"),
    ("Phi", "phase difference (Φ)"),
    ("Fv", "voltage frequency"),
    ("Fi", "current frequency"),
    ("Wh", "watt-hours"),
    ("Whp", "positive watt-hours"),
    ("Whm", "negative watt-hours"),
    ("Ah", "ampere-hours"),
    ("Ahp", "positive ampere hours"),
    ("Ahm", "negative ampere hours"),
    ("Vmax", "maximum voltage"),
    ("Imax", "maximum current"),
    ("Time", "integration time"),
    ("Math", "value computed during integration"),
])

# Virtual data items are are generated on-the-fly in software.
_VDATA_ITEMS = OrderedDict([
    ("T", "time stamp at the end of the measurement interval"),
    ("J", "Joules (calculated as Power * Interval)"),
])

# Power meter math function names and description.
_MATH_NAMES = OrderedDict([
    ("cfv", "voltage crest factor"),
    ("cfi", "current crest factor"),
    ("add", "A+B"),
    ("sub", "A-B"),
    ("mul", "A*B"),
    ("div", "A/B"),
    ("diva", "A/B^2"),
    ("divb", "A^2/B"),
    ("avw", "Average active power"),
])

# The power meter commands common for all power meters.
# * property - whether this command just reads or changes a power meter configuration option or a
#              property. Can be 'None'.
# * property-descr - if the command is about reading/changing a property, this is a short human
#                    readable string describing the the property the command deals with. Can be
#                    'None'.
# * descr - human-readable description for the command.
#
# The following keys are added dynamically when the power meter object is initialized:
# * choices - list of all the possible values accepted or return by the command. Can be 'None'.
# * choices-set - same as choices, but of the 'set' type. Can be 'None'.
# * value-descr - human-readable text description of the possible values the command returns or
#                 accepts. Can be 'None'.
COMMANDS = OrderedDict([
    ("get-id", {
        "property-descr" : "device ID",
        "descr" : "get the device identification string",
    }),
    ("get-current-auto-range", {
        "property-descr" : "current auto range status",
        "descr" : "check whether the automatic current range feature is enabled",
    }),
    ("set-current-auto-range", {
        "property-descr" : "current auto range status",
        "descr" : "enable or disable the automatic current range feature",
    }),
    ("get-current-range", {
        "property-descr" : "current range (amperes)",
        "descr" : "get current range in amperes",
    }),
    ("set-current-range", {
        "property-descr" : "current range (amperes)",
        "descr" : "set current range in amperse",
    }),
    ("get-voltage-auto-range", {
        "property-descr" : "voltage auto range status",
        "descr" : "check whether the automatic voltage range feature is enabled",
    }),
    ("set-voltage-auto-range", {
        "property-descr" : "voltage auto range status",
        "descr" : "enable or disable the automatic voltage range feature",
    }),
    ("get-voltage-range", {
        "property-descr" : "voltage range (volts)",
        "descr" : "get voltage range in volts",
    }),
    ("set-voltage-range", {
        "property-descr" : "voltage range (volts)",
        "descr" : "set current range in volts",
    }),
    ("get-interval", {
        "property-descr" : "data update interval (seconds)",
        "descr" : "get the data update interval in seconds",
    }),
    ("set-interval", {
        "property-descr" : "data update interval (seconds)",
        "descr" : "set the data update interval in seconds",
    }),
    ("configure-data-items", {
        "property-descr" : None,
        "descr" : "set data items to read",
    }),
    ("wait-data-update", {
        "property-descr" : None,
        "descr" : "wait for data update",
    }),
    ("read-data", {
        "property-descr" : None,
        "descr" : "read power meter data",
    }),
    ("get-crest-factor", {
        "property-descr" : "crest factor",
        "descr" : "get crest factor",
    }),
    ("set-crest-factor", {
        "property-descr" : "crest factor",
        "descr" : "set crest factor",
    }),
    ("get-smoothing-status", {
        "property-descr" : "smoothing feature status",
        "descr" : "check whether the smoothing feature is enabled or disabled",
    }),
    ("set-smoothing-status", {
        "property-descr" : "smoothing feature status",
        "descr" : "enable or disable the smoothing feature",
    }),
    ("get-smoothing-type", {
        "property-descr" : "smoothing type",
        "descr" : "get smoothing type",
    }),
    ("set-smoothing-type", {
        "property-descr" : "smoothing type",
        "descr" : "set smoothing type",
    }),
    ("get-smoothing-factor", {
        "property-descr" : "smoothing factor",
        "descr" : "get the configured smoothing factor",
    }),
    ("set-smoothing-factor", {
        "property-descr" : "smoothing factor",
        "descr" : "set smoothing factor",
    }),
    ("get-integration-mode", {
        "property-descr" : "integration mode",
        "descr" : "get integration mode",
    }),
    ("set-integration-mode", {
        "property-descr" : "integration mode",
        "descr" : "set integration mode",
    }),
    ("get-integration-state", {
        "property-descr" : "integration state",
        "descr" : "get integration state",
    }),
    ("get-integration-timer", {
        "property-descr" : "integration timer value",
        "descr" : "get the integration timer value value",
    }),
    ("set-integration-timer", {
        "property-descr" : "integration timer value",
        "descr" : "get the integration timer value",
    }),
    ("start-integration", {
        "property-descr" : None,
        "descr" : "start integration",
    }),
    ("stop-integration", {
        "property-descr" : None,
        "descr" : "stop integration",
    }),
    ("reset-integration", {
        "property-descr" : None,
        "descr" : "reset integration",
    }),
    ("get-math", {
        "property-descr" : "computation function",
        "descr" : "get the currently configured computation function",
    }),
    ("set-math", {
        "property-descr" : "computation function",
        "descr" : "set the computation function",
    }),
    ("get-remote-mode", {
        "property-descr" : "remote mode status",
        "descr" : "check whether the remote mode is enabled or disabled",
    }),
    ("set-remote-mode", {
        "property-descr" : "remote mode status",
        "descr" : "enable or disable the remote mode",
    }),
    ("get-local-mode", {
        "property-descr" : "local mode status",
        "descr" : "check whether the local mode is enabled or disabled",
    }),
    ("set-local-mode", {
        "property-descr" : "local mode status",
        "descr" : "enable or disable the local mode",
    }),
    ("get-wiring-system", {
        "property-descr" : "wiring system type",
        "descr" : "get the wiring system type",
    }),
    ("factory-reset", {
        "property-descr" : None,
        "descr" : "reset to the factory default settings",
    }),
    ("calibrate", {
        "property-descr" : None,
        "descr" : "execute zero-level compensation",
    }),
    ("clear", {
        "property-descr" : None,
        "descr" : "clear the device output queue"
    }),
    ("get-installed-opts", {
        "property-descr" : "installed device options",
        "descr" : "get information about the installed device options",
    }),
    ("get-measurement-mode", {
        "property-descr" : "measurement mode",
        "descr" : "get the measurement mode",
    }),
    ("set-measurement-mode", {
        "property-descr" : "measurement mode",
        "descr" : "set the measurement mode",
    }),
    ("get-sync-source", {
        "property-descr"  : "synchronization source",
        "descr"  : "the information about the synchronization source",
    }),
    ("set-sync-source", {
        "property-descr"  : "synchronization source",
        "descr"  : "set the synchronization source",
    }),
    ("get-hold", {
        "property-descr" : "the 'hold' feature status",
        "descr"  : "check whether the 'hold' feture is on or off",
    }),
    ("set-hold", {
        "property-descr" : "the 'hold' feature status",
        "descr" : "switch the 'hold' feture is on or off",
    }),
    ("get-max-hold", {
        "property-descr" : "the 'max hold' feature status",
        "descr" : "check whether the 'max hold' feture is on or off",
    }),
    # WT210 says no help text for max hold on ./yokotool wt210 set max-hold
    ("set-max-hold", {
        "property-descr" : "the 'max hold' feature status",
        "descr" : "switch the 'max hold' feture is on or off",
    }),
    ("get-line-filter", {
        "property-descr" : "line filter status",
        "descr" : "check if the line filter is enabled or disabled",
    }),
    ("set-line-filter", {
        "property-descr" : "line filter status",
        "descr" : "enable or disable the line filter",
    }),
    ("get-freq-filter", {
        "property-descr" : "frequency filter status",
        "descr" : "check if the frequency filter is enabled or disabled",
    }),
    ("set-freq-filter", {
        "property-descr" : "frequency filter status",
        "descr" : "enable or disable the frequency filter",
    }),
])

_RAW_COMMANDS = (
    ("get-id", "*IDN?"),
    ("get-installed-opts", "*OPT?"),
    ("get-interval", ":SAMP:RATE?"),
    ("set-interval", ":SAMP:RATE"),
    ("get-hold", ":SAMP:HOLD?"),
    ("set-hold", ":SAMP:HOLD"),
    ("get-integration-mode", ":INTEG:MODE?"),
    ("set-integration-mode", ":INTEG:MODE"),
    ("get-integration-timer", ":INTEG:TIM?"),
    ("set-integration-timer", ":INTEG:TIM"),
    ("start-integration", ":INTEG:STAR"),
    ("stop-integration", ":INTEG:STOP"),
    ("reset-integration", ":INTEG:RES"),
    ("get-math", ":MATH?"),
    ("get-remote-mode", ":COMM:REM?"),
    ("set-remote-mode", ":COMM:REM"),
    ("get-local-mode", ":COMM:LOCK?"),
    ("set-local-mode", ":COMM:LOCK"),
    ("factory-reset", "*RST"),
    ("calibrate", "*CAL?"),
    ("get-error-status", ":STAT:ERR?"),
    ("clear", "\n*CLS"),
    ("set-verbose-errors", ":STAT:QMES"),
    ("set-headers", ":COMM:HEAD"),
    ("set-verbose-mode", ":COMM:VERB"),
    ("get-eesr", ":STAT:EESR?"),
)

# Valid arguments for the "enable/disable" type of commands.
ON_OFF_CHOICE = ("on", "off")

# The valid arguments for various commands.
_CHOICES = (
    {
        "commands" : ("get-current-range", "set-current-range"),
        # Note: the allowed values also depend on the crest-factor.
        "choices" : ("auto", "0.0025", "0.005", "0.01", "0.02", "0.05", "0.1", "0.2", "0.5", "1",
                     "2", "5", "10", "20"),
    },
    {
        "commands" : ("get-voltage-range", "set-voltage-range"),
        # Note: the allowed values also depend on the crest-factor.
        "choices" : ("7.5", "15", "30", "60", "75", "150", "300", "600"),
    },
    {
        "commands" : ("get-current-auto-range", "set-current-auto-range"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-voltage-auto-range", "set-voltage-auto-range"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-crest-factor", "set-crest-factor"),
        "choices" : ("3", "6"),
    },
    {
        "commands" : ("get-interval", "set-interval"),
        "choices" : ("0.1", "0.25", "0.5", "1", "2", "5"),
    },
    {
        "commands" : ("get-line-filter", "set-line-filter"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-freq-filter", "set-freq-filter"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-smoothing-status", "set-smoothing-status"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-smoothing-type", "set-smoothing-type"),
        "choices" : ("linear", "exponent"),
    },
    {
        "commands" : ("get-smoothing-factor", "set-smoothing-factor"),
        "choices" : ("8", "16", "32", "64"),
    },
    {
        "commands" : ("get-integration-mode", "set-integration-mode"),
        "choices" : ("normal", "continuous"),
    },
    {
        "commands" : ("get-measurement-mode", "set-measurement-mode"),
        "choices" : ("rms", "vmean", "dc"),
    },
    {
        "commands" : ("get-display-digits", "set-display-digits"),
        "choices" : ("4", "5"),
    },
    {
        "commands" : ("get-remote-mode", "set-remote-mode"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-local-mode", "set-local-mode"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-verbose-errors", "set-verbose-errors"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-verbose-mode", "set-verbose-mode"),
        "choices" : ON_OFF_CHOICE,
    },
    {
        "commands" : ("get-headers", "set-headers"),
        "choices" : ON_OFF_CHOICE,
    },
)

# The EESR register bits. It is important to keep this list ordered correctly.
_EESR_BITS = {
    "upd":  0,  # Measurement data is being updated.
    "itg":  1,  # Integration started.
    "itm":  2,  # Integration timer started.
    "ovrs": 3,  # Computation result overflow.
    "fov":  4,  # Frequency is out of range.
    "str":  5,  # 'storage' is ongoing.
    "ovr1": 6,  # Voltage or current on the 1st element is out of range.
    "pov1": 7,  # Peak voltage on the 1st element is out of range.
    "poa1": 8,  # Peak current on the 1st element is out of range.
    "ovr2": 9,  # Voltage or current on the 2nd element is out of range.
    "pov2": 10, # Peak voltage on the 2nd element is out of range.
    "poa2": 11, # Peak current on the 2nd element is out of range.
    "ovr3": 12, # Voltage or current on the 3rd element is out of range.
    "pov3": 13, # Peak voltage on the 3rd element is out of range.
    "poa3": 14, # Peak current on the 3rd element is out of range.
}

#
# Power meter's input and output values are not always very human-friendly. Below set of functions,
# referred to as 'tweaks', transform these values into a human-friendly format, and vice-versa, they
# also transform human-friendly notations into power meter's format.
#

def on_off_tweak(_, value):
    """Translate '0' and non-zero strings to 'off' and 'on' strings."""

    if value == "0":
        return "off"
    return "on"

def to_lower_tweak(_, value):
    """Translate 'value' to lowercase."""
    return value.lower()

def _to_lower_capitalize_tweak(_, value):
    """Translate 'value' to lowercase and capitalize it."""
    return value.lower().capitalize()

def _float_to_str_tweak(_, value):
    """Translate a float to string dropping superfluous zeros."""
    return "%g" % float(value)

def _success_failure_tweak(_, value):
    """Translate '0' and non-zero strings to 'success' and 'failure' strings."""

    if value == "0":
        return "success"
    return "failure"

def _csv_to_seconds_tweak(_, value):
    """Convert time from 'h,m,s' CSV format to seconds."""

    seconds = 0
    for item in value.split(','):
        seconds = seconds * 60 + int(item)
    return str(seconds)

def _seconds_to_csv_tweak(_, value):
    """Convert time from seconds to 'h,m,s' CSV format."""

    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    return "%d,%d,%d" % (hours, minutes, seconds)

def _first_data_element_tweak(_, value):
    """Remove the ',1' ending from a data item."""

    if value.endswith(",1"):
        return value[:-2]
    return value

# The tweaks.
_TWEAKS = {
    "get-voltage-auto-range" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-current-auto-range" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-hold" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-max-hold" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-line-filter" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-freq-filter" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-smoothing-status" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-sync-source" : {
        "response-tweaks" : (to_lower_tweak,),
    },
    "get-measurement-mode" : {
        "response-tweaks" : (to_lower_tweak,),
    },
    "get-remote-mode" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-local-mode" : {
        "response-tweaks" : (on_off_tweak,),
    },
    "get-voltage-range" : {
        "response-tweaks" : (_float_to_str_tweak,),
    },
    "get-current-range" : {
        "response-tweaks" : (_float_to_str_tweak,),
    },
    "get-interval" : {
        "response-tweaks" : (_float_to_str_tweak,),
    },
    "calibrate" : {
        "response-tweaks" : (_success_failure_tweak,),
    },
    "get-integration-mode" : {
        "response-tweaks" : (to_lower_tweak,),
    },
    "get-integration-timer" : {
        "response-tweaks" : (_csv_to_seconds_tweak,),
    },
    "set-integration-timer" : {
        "input-tweaks" : (_seconds_to_csv_tweak,),
    },
}

# Map a power meter error code into a human-readable message. We do not cover all codes here so far.
_ERROR_CODES_MAP = {
    813 : {"msg" : "operation is not allowed during integration, please reset integration first"},
}

def is_in_range(value, start=0, stop=0):
    """Verify whether or not a string 'value' contains an integer in the [min, max] range."""

    try:
        value = int(value)
    except (ValueError, TypeError):
        return False
    if value < start or value > stop:
        return False
    return True

def _verify_integration_time(value):
    """
    Verify whether or not the input value for integration time is an integer representing seconds,
    and if it is lower or equal to 10000 hours.
    """
    return is_in_range(value, 0, 10000 * 60 * 60)

def _cmd_to_str(cmd, arg):
    """Convert command 'cmd' with argument 'arg' to a string for printing."""

    if arg is not None:
        return "%s %s" % (cmd, arg)
    return cmd

class YokoBase():
    """
    This is the base class for all power meters. Each specific type of power meter should be derived
    from this class.
    """

    def _htop_tweak(self, _, value):
        """Translate data item in human notation to the protocol notation."""
        return self._ditt["htop"].get(value, value)

    def _ptoh_tweak(self, _, value):
        """Translate data item in protocol notation to the human notation."""
        return self._ditt["ptoh"].get(value, value)

    def _add_choices_from_dict(self, cmd, choices_dict):
        """
        Add "choices" and "value-descr" for command 'cmd' from the the 'choices_dict' dictionary.
        """

        self.commands[cmd]["choices"] = tuple(choices_dict)

        lines = []
        for name, descr in choices_dict.items():
            lines.append("%s - %s" % (name, descr))
        self.commands[cmd]["value-descr"] = "\n".join(lines)

    def _iter_data_item_commands(self):
        """
        Yield the (cmd_part, get_cmd, set_cmd) tuples for each possible data item command. Must be
        implemented by the child class.
        """

    def _populate_choices(self, choices):
        """Populate the valid values for various WT310 commands to 'self.commands'."""

        cmds = self.commands
        for info in _CHOICES:
            for cmd in info["commands"]:
                if cmd in cmds:
                    cmds[cmd]["choices"] = info["choices"]

        for info in choices:
            for cmd in info["commands"]:
                if cmd in cmds:
                    cmds[cmd]["choices"] = info["choices"]

        self._add_choices_from_dict("read-data", self._data_items)
        self._add_choices_from_dict("configure-data-items", self._data_items)
        self._add_choices_from_dict("get-math", _MATH_NAMES)
        self._add_choices_from_dict("set-math", _MATH_NAMES)

        descr = "integer amount of seconds (0-10000 hours)"
        cmds["get-integration-timer"]["value-descr"] = descr
        cmds["set-integration-timer"]["value-descr"] = descr

        for info in cmds.values():
            if "choices" not in info:
                info["choices"] = None
                info["choices-set"] = None
            if "choices-set" not in info:
                info["choices-set"] = set(info["choices"])
            if "value-descr" not in info:
                info["value-descr"] = None

    def _populate_data_items(self, items, pairs):
        """
        Initialize data items dictionary and build the data items translation tables which is needed
        because often human name for the data item is different to the protocol name and we
        translate the name. This helper creates and returns the data item translation table, which
        is just a dictionary that can be used to quickly get human name by the protocol name and
        vice versa.  The 'pairs' input argument is an iterable containing the (human name, protocol
        name) pairs.
        """

        self._data_items = _DATA_ITEMS
        for name, descr in items.items():
            self._data_items[name] = descr
        for name, descr in _VDATA_ITEMS.items():
            self._data_items[name] = descr

        self._ditt = {}
        self._ditt["htop"] = {}
        self._ditt["ptoh"] = {}
        for hname, pname in pairs:
            self._ditt["htop"][hname] = pname
            self._ditt["ptoh"][pname] = hname

    def _populate_raw_commands(self, raw_commands):
        """Populate the raw (wire) power meter commands to 'self._commands'."""

        for cmd, raw_cmd in _RAW_COMMANDS:
            self._commands[cmd] = {}
            self._commands[cmd]["raw-cmd"] = raw_cmd

        for cmd, raw_cmd in raw_commands:
            self._commands[cmd] = {}
            self._commands[cmd]["raw-cmd"] = raw_cmd

    def _populate_tweaks(self, tweaks):
        """
        Pupulate the tweaks to 'self._commands'. The tweaks are functions applied to command
        arguments before running the command or to the results of a command before returning the
        results to the end user.
        """

        for cmd, info in _TWEAKS.items():
            for key, value in info.items():
                self._commands[cmd][key] = value

        for cmd, info in tweaks.items():
            for key, value in info.items():
                self._commands[cmd][key] = value

        self._commands["read-data"]["response-tweaks"] = (self._get_data_tweak,)

        # Cover the data item get/set commands as well.
        response_tweaks = (_first_data_element_tweak, _to_lower_capitalize_tweak, self._ptoh_tweak)
        input_tweaks = (_to_lower_capitalize_tweak, self._htop_tweak)
        for _, get_cmd, set_cmd in self._iter_data_item_commands():
            self._commands[get_cmd]["response-tweaks"] = response_tweaks
            self._commands[set_cmd]["input-tweaks"] = input_tweaks

    def _populate_arg_verify_funcs(self):
        """Populate arugment verification functions. They are executed before the command is run."""

        self._commands["set-integration-timer"]["verify-arg"] = _verify_integration_time

    def _add_command_func(self, cmd, func):
        """
        Some commands require a handler function, this helpers adds one to the internal
        'self._commands' dictionary.
        """

        if cmd not in self._commands:
            self._commands[cmd] = {}
        if "raw-cmd" not in self._commands[cmd]:
            self._commands[cmd]["raw-cmd"] = None
        self._commands[cmd]["func"] = func

    def _populate_raw_commands_post(self):
        """Add post process and add common raw commands."""

        # Cover the EESR-related commands (one command per a EESR bit).
        for name, bit in self._eesr_bits.items():
            cmd = "set-eesr-filter-%s" % name
            self._commands[cmd] = {}
            self._commands[cmd]["raw-cmd"] = ":STAT:FILT%d" % (bit + 1)
            cmd = "eesr-wait-%s" % name
            self._commands[cmd] = {}
            self._commands[cmd]["raw-cmd"] = ":COMM:WAIT %d" % (bit + 1)

        self._add_command_func("wait-data-update", self._wait_data_update_cmd)
        self._add_command_func("get-current-range", self._get_range_cmd)
        self._add_command_func("set-current-range", self._set_range_cmd)
        self._add_command_func("get-voltage-range", self._get_range_cmd)
        self._add_command_func("set-voltage-range", self._set_range_cmd)
        self._add_command_func("start-integration", self._start_integration_cmd)

        for cmd, info in self._commands.items():
            if cmd.startswith("get-") or (info["raw-cmd"] and info["raw-cmd"].endswith("?")):
                info["has-response"] = True
                info["has-argument"] = False
            else:
                info["has-response"] = False
                info["has-argument"] = True

    def _populate_errors_map_map(self):
        """
        Error codes map mapes power meter error code number either to a human-readable message or to
        an error handler that may either generate a human-readable message or handle the error
        condition.
        """

        self._errors_map = _ERROR_CODES_MAP
        self._errors_map[842] = self._errors_map[844] = self._errors_map[845] = \
                {"func" : self._integration_error_handler}

    @staticmethod
    def _integration_error_handler(cmd, arg, code, rawmsg): # pylint: disable=unused-argument
        """This function implements error handler for the integration commands."""

        if code == 845:
            # start -> reset
            return "current integration state is 'start' and it cannot be changed to 'reset', " \
                   "please stop it first"
        if code == 842:
            # start -> start
            return "integration is already in the 'start' state"
        if code == 844:
            # This is either 'reset->stop' or 'stop->stop'.
            return "cannot stop integration because it is not in the 'start' state, please " \
                   "start it first"

        return ""

    def _prepare_data_items_to_read(self, items):
        """
        The input 'items' list is a mix of pyisical and vitual data items. The former are provided
        by the power meter and the latter are computed in software. This function constructs and
        returns a list of physical data items from 'items'. We also avoid reading the same data item
        more than once with help of this function.
        """

        result = []
        self._item_indexes = {}

        idx = 0
        for item in items:
            # If users request to read the 'Joules' virtual data item, we read the and will use
            # this value to later compute the Joules.
            if item == "J":
                item = "P"
            if item not in _VDATA_ITEMS and item not in self._item_indexes:
                result.append(item)
                self._item_indexes[item] = idx
                idx += 1

        return result

    def _get_data_tweak(self, _, response):
        """Inject the virtual data items into power meter read response."""

        timestamp = time.time()
        items = []

        for item in self._items_to_read:
            if item not in _VDATA_ITEMS:
                items.append(response[self._item_indexes[item]])
            elif item == "T":
                items.append(str(timestamp))
            elif item == "J":
                items.append(str(float(response[self._item_indexes["P"]]) * self._interval))

        return items

    def _configure_data_items_cmd(self, _, items):
        """Set the data items that will be read by next "get-data" command."""

        self._items_to_read = items

        if len(items) > self.max_data_items:
            raise Error("too many data items, please, specify at most %s" % self.max_data_items)

        for item in items:
            if item not in self._data_items:
                msg = "bad data item '%s'" % item
                raise ErrorBadArgument(None, None, msg=msg)

        # The interval is needed to compute the Joules virtual data item.
        self._interval = float(self._command("get-interval"))
        items = self._prepare_data_items_to_read(items)
        _LOG.debug("data items to read from power meter: %s", ",".join(items))

        # Configure a trigger for the "UPD" bit changing from 1 to 0, which happens when data update
        # finishes.
        self._command("set-eesr-filter-upd", "fall")
        return items

    def _wait_data_update_cmd(self, _, __):
        """Wait until WT210 updates the data."""

        # Note, we use 'check_status=False' in this function because the status check commands may
        # take take long time in case of a low baud rate serial connection and we may be late when
        # the update interval is short.

        # Clear EESR by reading it.
        self._command("get-eesr", check_status=False)
        # Wait for the event.
        self._command("eesr-wait-upd", check_status=False)

    def _get_range_cmd(self, cmd, _):
        """Implements the 'get-current-range' and 'get-voltage-range' commands."""

        result = self._command(cmd, func=False)
        auto = self._command(cmd.replace("-range", "-auto-range"))

        if auto == "on":
            result += " (auto)"
        return result

    def _set_range_cmd(self, cmd, arg):
        """Implements the 'set-current-range' and 'set-voltage-range' commands."""

        auto_range_cmd = cmd.replace("-range", "-auto-range")
        if arg == "auto":
            self._command(auto_range_cmd, "on")
            return

        self._command(auto_range_cmd, "off")
        choices = self.commands[cmd]["choices"]
        if arg in (choices[1], choices[-1]):
            # The first and the last current/voltage range availability depends on the crest factor.
            what = cmd.split("-")[1]
            crest = self._command("get-crest-factor")
            crest_needed = None
            if crest == "3" and arg == choices[1]:
                crest_needed = "6"
            elif crest == "6" and arg == choices[-1]:
                crest_needed = "3"
            if crest_needed:
                raise Error("%s range %s is only available when crest factor is %s, but currently "
                            "it is %s" % (what, arg, crest_needed, crest))

        self._command(cmd, arg, func=False)

    def _start_integration_cmd(self, cmd, _):
        """
        Adds a delay after the 'start' integration command. The delay is necessary because some of
        the subsequent commands may fail if executed right after integration had been started. There
        is some sort of the internal integrator busy period which we let pass by introducing a short
        delay.
        """

        self._command(cmd, func=False)
        time.sleep(0.2)

    def _apply_response_tweaks(self, cmd, response):
        """
        Tweak 'response' as defined within a specific type of power meter, then return the tweaked
        argument.
        """

        if "response-tweaks" in self._commands[cmd]:
            for tweak_func in self._commands[cmd]["response-tweaks"]:
                response = tweak_func(cmd, response)
        return response

    def _apply_input_tweaks(self, cmd, arg):
        """
        Tweak 'input' as defined within a specific type of power meter, then return the tweaked
        argument.
        """

        if "input-tweaks" in self._commands[cmd]:
            for tweak_func in self._commands[cmd]["input-tweaks"]:
                arg = tweak_func(cmd, arg)
        return arg

    def _verify_argument(self, cmd, arg):
        """Verify whether or not 'arg' argument is valid for 'cmd' command."""

        choices = self.commands[cmd]["choices-set"]
        if choices:
            # 'arg' may be a list, in which case we check every element of the list.
            if isinstance(arg, (list, tuple)):
                for elt in arg:
                    if elt not in choices:
                        raise ErrorBadArgument(cmd, elt)
            else:
                if arg not in choices:
                    raise ErrorBadArgument(cmd, arg)

        if "verify-arg" in self._commands[cmd]:
            func = self._commands[cmd]["verify-arg"]
            if not func(arg):
                raise ErrorBadArgument(cmd, arg)

        return True

    def _check_error_status(self, cmd, arg):
        """
        Check whether the power meter error status and possibly apply the error handlers. Returns
        'None' if there were no errors (or the error was handled) and the error message otherwise.
        """

        status_cmd = self._commands["get-error-status"]["raw-cmd"]
        try:
            response = self._transport.queryline(status_cmd)
        except Transport.Error as err:
            raise type(err)("failed to check error status of command '%s':\n%s\nRaw command was "
                            "'%s'" % (_cmd_to_str(cmd, arg), err, status_cmd))

        try:
            code, rawmsg = response.split(',', 1)
        except ValueError as err:
            raise ErrorBadResponse(raw_cmd=status_cmd, response=response)

        code = int(code)
        if code == 0:
            return None

        if code in self._errors_map:
            if "func" in self._errors_map[code]:
                msg = self._errors_map[code]["func"](cmd, arg, code, rawmsg)
                if not msg:
                    return None
                if msg == "":
                    # Empty string means that the error handler could generate a customized error
                    # message and the default one should be used.
                    msg = response
            else:
                msg = self._errors_map[code]["msg"]
        else:
            msg = response

        return "command '%s' failed:\n%s" % (_cmd_to_str(cmd, arg), msg)

    def _command(self, cmd, arg=None, check_status=True, func=True):
        """
        Actually execute the command, the tweaks, and the status checks, unless 'check_status' is
        'False'. Some commands have both the "raw-cmd" and "func" keys in their 'self._command'
        description, and the 'func' argument whether the function should be executed or the raw
        command should be executed.
        """

        _LOG.debug(_cmd_to_str(cmd, arg))

        if func and "func" in self._commands[cmd]:
            return self._commands[cmd]["func"](cmd, arg)

        if arg is not None:
            arg = self._apply_input_tweaks(cmd, arg)

        raw_cmd = self._commands[cmd]["raw-cmd"]
        if arg is not None:
            raw_cmd += " %s" % arg

        try:
            self._transport.writeline(raw_cmd)
        except Transport.Error as err:
            raise type(err)("failed to write command '%s' to the power meter:\n%s\nRaw command "
                            "was '%s'" % (cmd, err, raw_cmd))
        response = None
        if self._commands[cmd]["has-response"]:
            try:
                response = self._transport.readline()
            except Transport.Error as err:
                raise type(err)("failed to read power meter response to '%s':\n%s\nRaw command was "
                                "'%s'" % (_cmd_to_str(cmd, arg), err, raw_cmd))
            response = self._apply_response_tweaks(cmd, response)

        if check_status:
            msg = self._check_error_status(cmd, arg)
            if msg:
                raise Error(msg)

        return response

    def command(self, cmd, arg=None):
        """
        Execute the power meter command 'cmd' with argument 'arg' if it is not null. Return the
        command response or 'None' if the command has no response. 'cmd' should be a string, 'arg'
        can be of any type since 'command()' handles the typecast to string.
        """

        if not isinstance(cmd, str) or cmd not in self.commands:
            raise Error("bad command '%s'" % cmd)

        # We allow 'arg' to be of different types and convert it into a string
        if arg is not None:
            if isinstance(arg, list):
                for idx, item in enumerate(arg):
                    if not isinstance(item, str):
                        arg[idx] = str(item)
            elif not isinstance(arg, str):
                arg = str(arg)

        # Sanity checks.
        if self._commands[cmd]["has-argument"]:
            self._verify_argument(cmd, arg)
        elif arg is not None:
            raise Error("command '%s' accepts no arguments, but '%s' was provided" % (cmd, arg))

        return self._command(cmd, arg)

    def _init_pmeter(self):
        """Initialize the power meter."""

        # Clear the output and error queues of the power meter. The first command may fail with the
        # "interrupted" error if the power meter is currently expencting the results of the previous
        # command to be read, so clear 2 times.
        try:
            self._command("clear")
        except Error:
            self._command("clear")

        # Make sure that in case of error the device sends verbose error strings, not just the
        # status code.
        self._command("set-verbose-errors", "on")
        # Disable headers in responses.
        self._command("set-headers", "off")

        # Clear all the EESR trigger conditions.
        for name in self._eesr_bits:
            self._command("set-eesr-filter-%s" % name, "never")

    def __init__(self, transport):
        """The class constructor. The 'transport' argument is the power meter transport object."""

        self._transport = transport
        self._eesr_bits = _EESR_BITS

        # The data items translation table.
        self._ditt = None
        # Create the user-visible commands dictionary.
        self.commands = COMMANDS
        # The private commands dictionary.
        self._commands = {}
        # List of items configured to be read by 'configure-data-items'.
        self._items_to_read = []
        # Indexes of the data items that we are reading.
        self._item_indexes = None
        # All the supported data items, including the virtual ones.
        self._data_items = None
        # Virtual data items.
        self._vdata_items = _VDATA_ITEMS
        # Maximum count of data items that can be read at the same time.
        self.max_data_items = None
        # Saved value of the power meter data update interval.
        self._interval = None
        # Messages and actions in case power meter reports and error.
        self._errors_map = None

    def close(self):
        """Close the communication interface with the power meter."""

        if self._transport:
            self._transport.close()
            self._transport = None
