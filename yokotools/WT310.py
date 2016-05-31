#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (c) 2013-2016 Intel, Inc.
# License: GPLv2
# Authors: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
#          Andy Shevchenko <andriy.shevchenko@linux.intel.com>
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
This module allows accessing and controlling Yokogawa power meters. We currently only implement the
support of WT310 power meters series but the module is designed to allow supporting other similar
power meters, e.g., WT210.
"""

import re
from yokotools import PowerMeter

_MAX_DATA_ITEMS = 10
_ELEMENTS_COUNT = 1

#
# The possible values for various power meter commands, referred to as 'assortments' in this code.
#

_ELECTRICAL_QUANTITIES = (
    ('V', 'voltage'),
    ('I', 'current'),
    ('P', 'active power'),
    ('S', 'apparent power'),
    ('Q', 'reactive power'),
    ('Lambda', 'power factor (λ)'),
    ('Phi', 'phase difference (Φ)'),
    ('Fv', 'voltage frequency'),
    ('Fi', 'current frequency'),
    ('Vppeak', 'peak voltage'),
    ('Vmpeak', 'minimum voltage'),
    ('Ippeak', 'peak current'),
    ('Impeak', 'minimum current'),
    ('Pppeak', 'peak power'),
    ('Pmpeak', 'minimum power'),
    ('Time', 'integration time'),
    ('Wh', 'watt-hours'),
    ('Whp', 'positive watt-hours'),
    ('Whm', 'negative watt-hours'),
    ('Ah', 'ampere-hours'),
    ('Ahp', 'positive ampere hours'),
    ('Ahm', 'negative ampere hours'),
    ('Math', 'a value computed during integration '
             '(e.g., average active power)'),
    ('Vrange', 'voltage range'),
    ('Irange', 'current range'),
)

# Column[0]: human name of electrical quantity (as most commonly used in physics literature,
#            documentation, etc)
# Column[1]: WT310 protocol's name of electrical quantity
_HUMAN_TO_PROTOCOL_ELEC_QTY = (
    ('V', 'U'),
    ('Fv', 'Fu'),
    ('Vppeak', 'Uppeak'),
    ('Vmpeak', 'Umpeak'),
    ('Vrange', 'Urange'),
)

_VALID_MATH_NAMES = (
    'cfu', 'cfi', 'add', 'sub', 'mul', 'div', 'diva', 'divb', 'avw',
)

_MATH_NAMES_WITH_ELEMENTS = (
    'cfu', 'cfi', 'avw',
)

# The EESR register bits. It is important to keep this list ordered correctly.
_EESR_BITS = (
    "upd",  # Measurement data is being updated
    "itg",  # Integration started
    "itm",  # Integration timer started
    "ovrs", # Computation result overflow
    "fov",  # Frequency is out of range
    "str",  # 'storage' is ongoing
    "ovr1", # Voltage or current on the 1st element is out of range
    "pov1", # Peak voltage on the 1st element is out of range
    "poa1", # Peak current on the 1st element is out of range
    "ovr2", # Voltage or current on the 2nd element is out of range
    "pov2", # Peak voltage on the 2nd element is out of range
    "poa2", # Peak current on the 2nd element is out of range
    "ovr3", # Voltage or current on the 3rd element is out of range
    "pov3", # Peak voltage on the 3rd element is out of range
    "poa3", # Peak current on the 3rd element is out of range
)

#
# Power meter's input and output values are not always very human-friendly. Below set of functions,
# referred to as 'tweaks', transform these values into a human-friendly format, and vice-versa, they
# also transform human-friendly notations into power meter's format.
#

def _on_off_tweak(value):
    """A tweak which translates 0 and non-zero values to 'off' and 'on' strings."""

    if value == "0":
        return "off"
    return "on"

def _success_failure_tweak(value):
    """A tweak which translates 0 and non-zero values to 'success' and 'failure' strings."""

    if value == "0":
        return "success"
    return "failure"

def _first_data_element_tweak(value):
    """A tweak which removes the ',1' part from a data item."""

    if value.endswith(",1"):
        return value[:-2]
    return value

def _to_human_notation_tweak(value):
    """
    A tweak which converts the human notation of electrical quantities to the WT310 protocol
    notation. Right now, the only difference between both notations is that the protocol uses 'U' to
    denote the voltage whereas the human notation is 'V'.
    """

    for data in _HUMAN_TO_PROTOCOL_ELEC_QTY:
        if value == data[1]:
            value = data[0]
            break
    return value

def _to_protocol_notation_tweak(value):
    """A tweak which does the opposite of '_to_human_notation_tweak()' function."""

    for data in _HUMAN_TO_PROTOCOL_ELEC_QTY:
        if value == data[0]:
            value = data[1]
            break
    return value

def _wt310_measurement_data_tweak(data):
    """A tweak which converts the measurement data read from WT310 to a human-friendly format."""
    return ", ".join([str(float(v)) for v in data.split(",")])

def _csv_to_seconds_tweak(value):
    """A tweak which converts time from 'h,m,s' CSV format to seconds."""

    seconds = 0
    for item in value.split(','):
        seconds = seconds * 60 + int(item)
    return str(seconds)

def _seconds_to_csv_tweak(value):
    """A tweak which converts time from seconds to 'h,m,s' CSV format."""

    minutes, seconds = divmod(int(value), 60)
    hours, minutes = divmod(minutes, 60)
    return "%d,%d,%d" % (hours, minutes, seconds)

def _math_response_tweak(value):
    """
    A tweak which removes the '1' part from a math function name. Additionally, it adds a comma
    between the math function name and the element number which makes math functions look consistent
    with data item names.
    """

    match = re.search(r"([^\d]*)(\d+)$", value)
    if match and match.group(2) == "1":
        return match.group(1)
    elif value in _MATH_NAMES_WITH_ELEMENTS:
        return match.group(1) + "," + match.group(2)

def _math_input_tweak(value):
    """
    A tweak which does the opposite of '_math_response_tweak()' function since it appends
    '1' to the math function names that do not end with an element number but require it.
    """

    if value in _MATH_NAMES_WITH_ELEMENTS:
        value = value + "1"

    return value

#
# Verify functions
#

def _is_in_range(value, range_min=0, range_max=0):
    """Verify whether or not 'value' is an integer in the [min, max] range."""

    try:
        value = int(value)
    except (ValueError, TypeError):
        return False

    if value < range_min or value > range_max:
        return False

    return True

def _verify_integration_time(value):
    """
    Verify whether or not the input value for integration time is an integer representing seconds,
    and if it is lower or equal to 10000 hours.
    """
    return _is_in_range(value, 0, 10000 * 60 * 60)

def _verify_data_items_count(item):
    """Verify whether or not the amount of data items range from 1 to '_MAX_DATA_ITEMS'."""
    return _is_in_range(item, 1, _MAX_DATA_ITEMS)

def _verify_data_item_name(item):
    """
    Verify whether of not 'item' argument is a valid electrical quantity. Please, see the
    'WT310/WT310HC/WT330 Digital Power Meter Communication Interface User's Manual', page 6-23
    'Numeric data functions' table.
    """

    # Cut off the 'element' part part from the data item
    split = item.rsplit(",", 1)

    # Make sure the element is a number between 1 and '_ELEMENTS_COUNT'
    if len(split) > 1 and not _is_in_range(split[1], 1, _ELEMENTS_COUNT):
        return False

    # Make sure the element is a valid electrical quantity
    if split[0] not in [element[0] for element in _ELECTRICAL_QUANTITIES]:
        return False

    return True

def _verify_math_name(name):
    """
    Verify whether of not 'name' argument is a valid math function. Please, see the
    'WT310/WT310HC/WT330 Digital Power Meter Communication Interface User's Manual', page 6-16.
    """

    match = re.search(r"([^\d]*)(\d+)$", name)
    if match:
        if not _is_in_range(match.group(2), 1, _ELEMENTS_COUNT):
            return False

        name = match.group(1)
        if name not in _MATH_NAMES_WITH_ELEMENTS:
            return False

    if name not in _VALID_MATH_NAMES:
        return False

    return True

#
# Commands
#

_WT310_COMMANDS = {
    '*IDN?': 'get-id',
    '*OPT?': 'get-installed-opts',
    ':RATE?': 'get-interval',
    ':RATE': 'set-interval',
    ':INP:FILT:LINE?': 'get-line-filter',
    ':INP:FILT:LINE': 'set-line-filter',
    ':INP:FILT:FREQ?': 'get-freq-filter',
    ':INP:FILT:FREQ': 'set-freq-filter',
    ':INP:CURR:AUTO?': 'get-current-auto-range',
    ':INP:CURR:AUTO': 'set-current-auto-range',
    ':INP:CURR:RANG?': 'get-current-range',
    ':INP:CURR:RANG': 'set-current-range',
    ':INP:VOLT:AUTO?': 'get-voltage-auto-range',
    ':INP:VOLT:AUTO': 'set-voltage-auto-range',
    ':INP:VOLT:RANG?': 'get-voltage-range',
    ':INP:VOLT:RANG': 'set-voltage-range',
    ':HOLD?': 'get-hold',
    ':HOLD': 'set-hold',
    ':MEAS:MHOL?': 'get-max-hold',
    ':MEAS:MHOL': 'set-max-hold',
    ':SYST:KLOC?': 'get-keys-locking',
    ':SYST:KLOC': 'set-keys-locking',
    ':INP:MODE?': 'get-measurement-mode',
    ':INP:MODE': 'set-measurement-mode',
    ':INP:SYNC?': 'get-sync-source',
    ':INP:SYNC': 'set-sync-source',
    ':INP:CFAC?': 'get-crest-factor',
    ':INP:CFAC': 'set-crest-factor',
    ':INP:WIR?': 'get-wiring-system',
    ':MEAS:AVER:STATE?': 'get-smoothing-status',
    ':MEAS:AVER:STATE': 'set-smoothing-status',
    ':MEAS:AVER:TYPE?': 'get-smoothing-type',
    ':MEAS:AVER:TYPE': 'set-smoothing-type',
    ':MEAS:AVER:COUN?': 'get-smoothing-factor',
    ':MEAS:AVER:COUN': 'set-smoothing-factor',
    ':INTEG:STAT?': 'get-integration-state',
    ':INTEG:MODE?': 'get-integration-mode',
    ':INTEG:MODE': 'set-integration-mode',
    ':INTEG:TIM?': 'get-integration-timer',
    ':INTEG:TIM': 'set-integration-timer',
    ':INTEG:STAR': 'start-integration',
    ':INTEG:STOP': 'stop-integration',
    ':INTEG:RES': 'reset-integration',
    ':NUM:FORM?': 'get-data-format',
    ':NUM:FORM': 'set-data-format',
    ':NUM:NORM:NUM?': 'get-data-items-count',
    ':NUM:NORM:NUM': 'set-data-items-count',
    ':NUM:NORM:VAL?': 'get-data',
    ':MATH?': 'get-math',
    ':MATH': 'set-math',
    ':SYST:RES?': 'get-display-digits',
    ':SYST:RES': 'set-display-digits',
    ':COMM:REM?': 'get-remote-mode',
    ':COMM:REM': 'set-remote-mode',
    '*RST': 'factory-reset',
    '*CAL?': 'calibrate',
    ':STAT:ERR?': 'get-error-status',
    # The '\n' symbol makes the *CLS command also clear the output queue, see
    # "WT310/WT310HC/WT330 Digital Power Meter Communication Interface User's
    # Manual", page 7-3.
    '\n*CLS': 'clear',

    # Below commands are not in "self.commands", so they are not
    # supposed to be used from outside of this module.
    ':STAT:QMES': 'set-verbose-errors',
    ':COMM:HEAD': 'set-headers',
    ':COMM:VERB': 'set-verbose-mode',
    ':SYST:COMM:COMM': 'set-compat-mode',
    ':STAT:EESR?': 'get-eesr'
}

class WT310(PowerMeter.PowerMeter):
    """
    This class implements Yokogawa WT310 specialization of the "PowerMeter"
    class. Basically, we implement the command map, and the assortments,
    tweaks, and state checks dictionaries.
    """

    def __init__(self, transport_obj):
        """The class constructor."""

        # Call the base class constructor first
        super(WT310, self).__init__(transport_obj, _MAX_DATA_ITEMS)

        self._define_command_map()
        self._define_assortments()
        self._define_tweaks()
        self._define_state_checks()

        # Clear the output and error queues of the power meter. The first
        # command may fail with the "interrupted" error if the power meter is
        # currently expencting the results of the previous command to be read,
        # so clear 2 times.
        try:
            self._command("clear")
        except PowerMeter.Error:
            pass
        self._command("clear")

        # Set data format to ascii
        self._command("set-data-format", "ascii")

        # Enable WT310 commands
        self._command("set-compat-mode", "WT300")

        # Make sure that in case of error the device sends verbose error
        # strings, not just the status code.
        self._command("set-verbose-errors", "on")

        # Disable headers in responses
        self._command("set-headers", "off")

        # Enable verbose mode which makes the power meter reply with full
        # strings instead of cut ones.
        self._command("set-verbose-mode", "on")

    def _wait_for_data_update(self, dummy_cmd, dummy_arg):
        """Wait until WT310 updates the data."""

        # Clear all the EESR trigger conditions
        for bit in range(0, len(_EESR_BITS)):
            self._command("set-eesr-trigger%d" % bit, "never")

        # Clear EESR by reading it
        self._command("get-eesr", has_response=True)

        # Configure a trigger for the "UPD" bit changing from 1 to 0, which
        # happens when data update finishes.
        self._command("set-eesr-trigger%d" % _EESR_BITS.index('upd'), "fall")

        # Wait for the event
        self._command("eesr-wait%d" % _EESR_BITS.index('upd'))

    def _define_command_map(self):
        """
        Define the WT310 command map which translates the user-visible commands
        to WT310 commands.
        """

        self._command_map.update(PowerMeter.populate(_WT310_COMMANDS))
        self._command_map.update({
            "wait-for-data-update"   : self._wait_for_data_update,
        })

        # Add mappings for data item commands
        for item in range(1, self.max_data_items + 1):
            cmd = "get-data-item%d" % item
            self._command_map[cmd] = ":NUM:NORM:ITEM%d?" % item

            cmd = "set-data-item%d" % item
            self._command_map[cmd] = ":NUM:NORM:ITEM%d" % item

        # Add mappings for EESR-related commands (one command per a EESR bit)
        for bit in range(1, len(_EESR_BITS) + 1):
            cmd = "set-eesr-trigger%d" % (bit - 1)
            self._command_map[cmd] = ":STAT:FILT%d" % bit

            cmd = "eesr-wait%d" % (bit - 1)
            self._command_map[cmd] = ":COMM:WAIT %d" % bit

    def _define_assortments(self):
        """
        This class defines which values are valid for various properties of the
        Yokogawa WT310 power meter. Simple values are defined as an array of
        possible choices, and in more complex cases there is a specific
        verification function.
        """

        self._assortments = {
            "set-current-range" : {
                "assortment" : (
                    "0.005",
                    "0.01",
                    "0.02",
                    "0.05",
                    "0.1",
                    "0.2",
                    "0.5",
                    "1",
                    "2",
                    "5",
                    "10",
                    "20",
                ),
            },
            "set-voltage-range" : {
                "assortment" : (
                    "7.5",
                    "15",
                    "30",
                    "60",
                    "75",
                    "150",
                    "300",
                    "600",
                ),
            },
            "set-current-auto-range" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-voltage-auto-range" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-crest-factor" : {
                "assortment" : (
                    "3",
                    "6",
                ),
            },
            "set-interval" : {
                "assortment" : (
                    "0.1",
                    "0.25",
                    "0.5",
                    "1",
                    "2",
                    "5"
                ),
            },
            "set-line-filter" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-freq-filter" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-smoothing-status" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-smoothing-type" : {
                "assortment" : (
                    "linear",
                    "exponent",
                ),
            },
            "set-smoothing-factor" : {
                "assortment" : (
                    "8",
                    "16",
                    "32",
                    "64",
                ),
            },
            "set-integration-mode" : {
                "assortment" : (
                    "normal",
                    "continuous",
                ),
            },
            "set-data-format" : {
                "assortment" : (
                    "ascii",
                    "float",
                ),
            },
            "set-measurement-mode" : {
                "assortment" : (
                    "rms",
                    "vmean",
                    "dc",
                ),
            },
            "set-sync-source" : {
                "assortment" : (
                    "voltage",
                    "current",
                    "off",
                ),
            },
            "set-hold" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-max-hold" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-keys-locking" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-display-digits" : {
                "assortment" : (
                    "4",
                    "5",
                ),
            },
            "set-remote-mode" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-compat-mode" : {
                "assortment" : (
                    "WT200",
                    "WT300",
                ),
            },
            "set-verbose-errors" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-headers" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-verbose-mode" : {
                "assortment" : PowerMeter.ON_OFF_RANGE,
            },
            "set-integration-timer" : {
                "verify-func" : _verify_integration_time,
                "text-descr"  : "integer amount of seconds (0-10000 hours)",
            },
            "set-data-items-count" : {
                "verify-func" : _verify_data_items_count,
                "text-descr"  : "an integer from 1 to %d" \
                                % self.max_data_items,
            },
        }

        # Add the math verification function
        self._assortments["set-math"] = {
            "verify-func" : _verify_math_name,
            "text-descr"  : ", ".join(_VALID_MATH_NAMES)
        }

        # Add verification functions for data item commands
        for item in range(1, self.max_data_items + 1):
            cmd = "set-data-item%d" % item
            # test_descr stores the list of human electrical quantities
            # that is displayed to user, as help message.
            # Add an initial new line character to improve both
            # formatting and readability.
            text_descr = "\n"
            for elec_qty, descr in _ELECTRICAL_QUANTITIES:
                text_descr += "%s - %s\n" % (elec_qty, descr)
            self._assortments[cmd] = {
                "verify-func" : _verify_data_item_name,
                "text-descr"  : text_descr,
            }

    def _define_tweaks(self):
        """Apply necessary tweaks to the commands."""

        self._tweaks = {
            "get-voltage-auto-range" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-current-auto-range" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-hold" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-max-hold" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-keys-locking" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-line-filter" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-freq-filter" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-smoothing-status" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            "get-smoothing-type" : {
                "response-tweaks" : (lambda x: x.lower(), ),
            },
            "get-data-format" : {
                "response-tweaks" : (lambda x: x.lower(), ),
            },
            "get-data" : {
                "response-tweaks" : (_wt310_measurement_data_tweak, ),
            },
            "get-math" : {
                "response-tweaks" : (lambda x: x.lower(),
                                     _math_response_tweak),
            },
            "set-math" : {
                "input-tweaks"    : (lambda x: x.lower(),
                                     _math_input_tweak, ),
            },
            "get-sync-source" : {
                "response-tweaks" : (lambda x: x.lower(), ),
            },
            "get-measurement-mode" : {
                "response-tweaks" : (lambda x: x.lower(), ),
            },
            "get-remote-mode" : {
                "response-tweaks" : (_on_off_tweak, ),
            },
            # TODO: when auto-range happens, a hyphen is added to measurement
            # range, and we need to handle this, see Users' manual, page 5-12
            "get-voltage-range" : {
                "response-tweaks" : (float, ),
            },
            "get-current-range" : {
                "response-tweaks" : (float, ),
            },
            "get-interval" : {
                "response-tweaks" : (float, ),
            },
            "calibrate" : {
                "response-tweaks" : (_success_failure_tweak, ),
            },
            "get-integration-state" : {
                "response-tweaks" : (lambda x: x.lower(), ),
            },
            "get-integration-mode" : {
                "response-tweaks" : (lambda x: x.lower(), ),
            },
            "get-integration-timer" : {
                "response-tweaks" : (_csv_to_seconds_tweak, ),
            },
            "set-integration-timer" : {
                "input-tweaks" : (_seconds_to_csv_tweak, ),
            },
        }

        # Add tweaks fo data item commands
        for item in range(1, self.max_data_items + 1):
            cmd = "get-data-item%d" % item
            self._tweaks[cmd] = {
                "response-tweaks" : (lambda x: x.lower().capitalize(),
                                     _first_data_element_tweak,
                                     _to_human_notation_tweak),
            }

            cmd = "set-data-item%d" % item
            self._tweaks[cmd] = {
                "input-tweaks" : (lambda x: x.lower().capitalize(),
                                  _to_protocol_notation_tweak)
            }

    def _integration_states_check(self, cmd, allowed_states):
        """
        This function checks that the current integration state is OK for a
        command to be executed.
        """

        integ_state = self.command("get-integration-state")
        if integ_state not in allowed_states:
            raise PowerMeter.Error("current integration state is \"%s\", "
                                   "but \"%s\" can only be executed in the "
                                   "following state(s): %s"
                        % (integ_state, cmd, ", ".join(allowed_states)))

    def _ongoing_integration_check(self, cmd):
        """
        This function is executed for those commands which require integration
        to be reset.
        """
        self._integration_states_check(cmd, ("reset", ))

    def _start_integration_check(self, cmd):
        """A tweak for the "start-integration" command."""
        self._integration_states_check(cmd, ("reset", "stop"))

    def _stop_integration_check(self, cmd):
        """A tweak for the "stop-integration" command."""
        self._integration_states_check(cmd, ("start",))

    def _reset_integration_check(self, cmd):
        """A tweak for the "stop-integration" command."""

        self._integration_states_check(cmd, ("reset", "stop", "timeup", "error"))

    def _define_state_checks(self):
        """
        This function define "state checks" for various commands. The state
        check of a command is executed before the command and it is supposed to
        check if the power meter is in a state which allows the command to be
        executed.
        """

        self._state_checks = {
            "set-line-filter"       : self._ongoing_integration_check,
            "set-freq-filter"       : self._ongoing_integration_check,
            "set-measurement-mode"  : self._ongoing_integration_check,
            "set-interval"          : self._ongoing_integration_check,
            "calibrate"             : self._ongoing_integration_check,
            "set-crest-factor"      : self._ongoing_integration_check,
            "set-integration-mode"  : self._ongoing_integration_check,
            "set-integration-timer" : self._ongoing_integration_check,
            "start-integration"     : self._start_integration_check,
            "stop-integration"      : self._stop_integration_check,
            "reset-integration"     : self._reset_integration_check,
        }
