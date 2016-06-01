#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (c) 2013-2016 Intel, Inc.
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

"""This module allows accessing and controlling power meters."""

from yokotools import transport

class ErrorBadArgument(Exception):
    """
    This exception is thrown when the argument for a command is incorrect. The 'Exception' object
    provides the 'hint' attribute which is a string describing what would be the correct argument.
    """

    def __init__(self, arg, hint):
        # Call the class constructor first
        super(ErrorBadArgument, self).__init__(arg, hint)

        self._arg = arg
        self.hint = hint

    def __str__(self):
        return "unacceptable argument \"%s\", use: %s" % (self._arg, self.hint)

class Error(Exception):
    """All the other error conditions cause exceptions of this type."""
    pass

# The power meter commands supported by this module and their properties
#    * has-response: whether or not the power meter responds with a message to the command
#    * has-argument: whether or not the command requires an argument
_COMMANDS = {
    "get-id" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "get-installed-opts" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "get-measurement-mode" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-measurement-mode" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-sync-source" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-sync-source" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-current-auto-range" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-current-auto-range" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-current-range" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-current-range" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-voltage-auto-range" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-voltage-auto-range" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-voltage-range" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-voltage-range" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-crest-factor" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-crest-factor" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-hold" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-hold" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-max-hold" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-max-hold" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-keys-locking" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-keys-locking" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-interval" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-interval" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-line-filter" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-line-filter" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-freq-filter" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-freq-filter" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-smoothing-status" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-smoothing-status" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-smoothing-type" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-smoothing-type" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-smoothing-factor" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-smoothing-factor" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-integration-state" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "get-integration-mode" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-integration-mode" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-integration-timer" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-integration-timer" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "start-integration" : {
        "has-response" : False,
        "has-argument" : False,
    },
    "stop-integration" : {
        "has-response" : False,
        "has-argument" : False,
    },
    "reset-integration" : {
        "has-response" : False,
        "has-argument" : False,
    },
    "get-data-format" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-data-format" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-data-items-count" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-data-items-count" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-data" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "wait-for-data-update" : {
        "has-response" : False,
        "has-argument" : False,
    },
    "get-math" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-math" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-display-digits" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-display-digits" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-remote-mode" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "set-remote-mode" : {
        "has-response" : False,
        "has-argument" : True,
    },
    "get-wiring-system" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "factory-reset" : {
        "has-response" : False,
        "has-argument" : False,
    },
    "calibrate" : {
        "has-response" : True,
        "has-argument" : False,
    },
    "clear" : {
        "has-response" : False,
        "has-argument" : False,
    },
    "get-error-status" : {
        "has-response" : True,
        "has-argument" : False,
    },
}

class PowerMeter(object):
    """
    This is the base class for all power meters. Each specific type of power meter should be derived
    from this class.
    """

    def __init__(self, transport_obj, max_data_items=10):
        """
        The class constructor. The 'transport_obj' argument is the power meter transport object. The
        'max_data_items' argument sets the default number of data items that should be transmitted
        while getting data.
        """

        self.commands = _COMMANDS
        self.max_data_items = max_data_items

        # Add commands for getting and setting data items
        for item in range(1, self.max_data_items + 1):
            cmd = "get-data-item%d" % item
            self.commands[cmd] = {
                "has-response" : True,
                "has-argument" : False,
            }

            cmd = "set-data-item%d" % item
            self.commands[cmd] = {
                "has-response" : False,
                "has-argument" : True,
            }

        self._transport = transport_obj

        # Child classes have to define the below
        self._command_map = {}
        self._assortments = {}
        self._tweaks = {}
        self._state_checks = {}

    def _apply_response_tweaks(self, cmd, response):
        """
        Tweak 'response' as defined within a specific type of power meter, then return the
        tweaked argument.
        """

        if cmd in self._tweaks and "response-tweaks" in self._tweaks[cmd]:
            for tweak_func in self._tweaks[cmd]["response-tweaks"]:
                response = tweak_func(response)

        return response

    def _apply_input_tweaks(self, cmd, arg):
        """
        Tweak 'input' as defined within a specific type of power meter, then return the
        tweaked argument.
        """

        if cmd in self._tweaks and "input-tweaks" in self._tweaks[cmd]:
            for tweak_func in self._tweaks[cmd]["input-tweaks"]:
                arg = tweak_func(arg)

        return arg

    def _command(self, cmd, arg=None, has_response=False):
        """
        A helper function for the 'command()' method. Execute the input tweak function (if 'arg' is
        not null) and the state checks. Send 'cmd' to the power meter. If 'cmd' implies a response,
        execute the reponse tweak function. Finally, verify the status of the power meter and return
        the response string.
        """

        raw_cmd = self._command_map[cmd]

        if arg is not None:
            arg = self._apply_input_tweaks(cmd, arg)

        if cmd in self._state_checks:
            self._state_checks[cmd](cmd)

        if not isinstance(raw_cmd, basestring):
            return raw_cmd(cmd, arg)

        # Send the command to the power meter
        if arg is not None:
            sent_cmd = raw_cmd + " " + arg
        else:
            sent_cmd = raw_cmd

        if has_response:
            try:
                response = self._query(sent_cmd)
            except transport.Error as err:
                raise Error("sent command \"%s\" but failed to read the power meter's response:\n%s"
                            % (sent_cmd.lstrip(), err))

            response = self._apply_response_tweaks(cmd, response)
        else:
            try:
                self._transport.write(sent_cmd + "\n")
            except transport.Error as err:
                raise Error("failed to write command \"%s\" to the power meter:\n%s"
                            % (sent_cmd.lstrip(), err))
            response = None

        # Read and check the status
        raw_cmd = self._command_map["get-error-status"]
        status = self._query(raw_cmd)
        if status.split(',')[0] != '0':
            raise Error("command \"%s\" failed:\n%s" % (sent_cmd.lstrip(), status))

        return response

    def _verify_argument(self, cmd, arg):
        """Verify whether or not 'arg' argument is valid for 'cmd' command."""

        if cmd not in self._assortments:
            return True

        if "assortment" in self._assortments[cmd]:
            assortment = self._assortments[cmd]["assortment"]
            if arg not in assortment:
                raise ErrorBadArgument(arg, ", ".join(assortment))

        if "verify-func" in self._assortments[cmd]:
            func = self._assortments[cmd]["verify-func"]
            if not isinstance(arg, basestring) or not func(arg):
                raise ErrorBadArgument(arg, self._assortments[cmd]["text-descr"])

        return True

    def _query(self, data):
        """Wrapper around 'transport.queryline()' method to simplify our code."""
        return self._transport.queryline(data + "\n").strip()

    def command(self, cmd, arg=None):
        """
        Execute the power meter command 'cmd' with argument 'arg' if it is not null. Return the
        command response or 'None' if the command has no response. 'cmd' should be a string, 'arg'
        can be of any type since 'command()' handles the typecast to string.
        """

        if not isinstance(cmd, basestring) or cmd not in self.commands:
            raise Error("bad command \"%s\"" % cmd)

        # We allow 'arg' to be of different types and convert it into a string
        if arg != None and not isinstance(arg, basestring):
            arg = str(arg)

        cmd_dict = self.commands[cmd]

        # Sanity checks
        if cmd_dict["has-argument"]:
            self._verify_argument(cmd, arg)
        elif arg is not None:
            raise Error("command \"%s\" does not need argument \"%s\"" % (cmd, arg))

        return self._command(cmd, arg, cmd_dict["has-response"])

    def get_argument_help(self, cmd):
        """Return a user-friendly help message for the power meter command 'cmd'."""

        if cmd not in self._assortments:
            raise Error("command \"%s\" does not support arguments" % cmd)

        if "text-descr" in self._assortments[cmd]:
            return self._assortments[cmd]["text-descr"]
        elif "assortment" in self._assortments[cmd]:
            return ", ".join(self._assortments[cmd]["assortment"])
        else:
            return "no help text for \"%s\", please report a bug" % cmd

#
# Constants used by children of the PowerMeter class
#

ON_OFF_RANGE = (
    'off',
    'on',
)

#
# Exported functions
#

def populate(commands):
    """Populate the power meter commands supported by this module."""

    result = {}
    for cmd in commands:
        result[commands[cmd]] = cmd
    return result
