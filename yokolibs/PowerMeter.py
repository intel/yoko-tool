#!/usr/bin/env python
#
# Copyright (C) 2016-2020 Intel Corporation
# SPDX-License-Identifier: GPL-2.0-only
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Authors: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
#          Helia Correia <helia.correia@linux.intel.com>

"""
This module provides API for controlling Yokogawa power meters.
"""

# pylint: disable=too-many-instance-attributes

from __future__ import absolute_import, division, print_function

import logging
import textwrap
from collections import OrderedDict

from yokolibs import Transport, _wt310, _wt210
from yokolibs.Config import CONFIG_OPTIONS as _KWARGS
# pylint: disable=unused-import
from yokolibs.Exceptions import Error, ErrorBadArgument, ErrorBadResponse
from yokolibs._yokobase import COMMANDS
# pylint: enable=unused-import

# Class objects for the supported power meters.
_PMTYPE_CLASSES = OrderedDict([(_wt310.WT310.pmtypes, _wt310.WT310),
                               (_wt210.WT210.pmtypes, _wt210.WT210)])

_LOG = logging.getLogger("PowerMeter")

# This makes sure all classes are the new-style classes by default.
__metaclass__ = type # pylint: disable=invalid-name

class PowerMeter:
    """This class extends the capabilities of 'WT310' class."""

    def get_argument_help(self, cmd):
        """Return a user-friendly help message for the power meter command 'cmd'."""

        if cmd not in self.commands:
            raise Error("command '%s' does not support arguments" % cmd)

        if self.commands[cmd]["value-descr"]:
            return self.commands[cmd]["value-descr"]
        if self.commands[cmd]["choices"]:
            return ", ".join(self.commands[cmd]["choices"])

        raise Error("no help text for '%s'" % cmd)

    def close(self):
        """Close the communication interface with the power meter."""

        if self._pmeter:
            self._pmeter.close()
            self._pmeter = None

    def command(self, cmd, arg=None):
        """
        Execute the power meter command 'cmd' with argument 'arg'. Return the command response or
        'None' if the command has no response. 'cmd' should be a string, 'arg' should be of the type
        the specific command expects. In most of the cases 'arg' is a string or 'None', but it may
        also be a list in case of the 'configure-data-items' command.
        """

        try:
            return self._pmeter.command(cmd, arg)
        except ErrorBadArgument:
            raise Error("bad argument '%s' for command '%s', use:\n%s"
                        % (arg, cmd, self.get_argument_help(cmd)))

    def _probe_error(self, errors):
        """TODO"""

        wrapper = textwrap.TextWrapper(width=79)

        msg = "unknown type of the device '%s'. Here is the log of all the attempts to recognize " \
              "the device type." % self._transport.devnode
        lines = wrapper.wrap(msg)

        wrapper.initial_indent = " * "
        wrapper. subsequent_indent = "   "
        for pmtype, cls, err in errors:
            msg = "%s (%s): %s" % (pmtype, cls, err)
            lines += wrapper.wrap(msg)

        raise Error("\n".join(lines))

    def __init__(self, transport=None, **kwargs):
        """
        The class constructor. The optional 'transport' argument specifies the transport object to
        use. If it is not provided, the rest of the arguments are used to create the transport. The
        allowed keys in 'kwargs' are the same as the configuration file options (e.g., 'devnode',
        etc).
        """

        # Validate kwargs.
        for kwarg in kwargs:
            if kwarg not in _KWARGS:
                raise Error("unknown keyword argument '%s'" % kwargs)

        self._transport = transport
        if not transport:
            self._transport = Transport.Transport(**kwargs)

        pmtype = kwargs.get("pmtype", None)
        if pmtype:
            pmtype = pmtype.lower()
            for pmtypes, cls in _PMTYPE_CLASSES.items():
                if pmtype in pmtypes:
                    self._pmeter = cls(self._transport)
                    break
            else:
                msg = []
                for pmtypes, pmclass in _PMTYPE_CLASSES.items():
                    msg.append("* %s - %s" % (", ".join(pmtypes), pmclass.name))
                raise Error("unsupported power meter type '%s', supported power meter types "
                            "are:\n%s" % (pmtype, "\n".join(msg)))
        else:
            errors = []
            self._pmeter = None
            for pmtypes, cls in _PMTYPE_CLASSES.items():
                pmtype = "/".join(pmtypes)
                try:
                    _LOG.debug("probing '%s'", pmtype)
                    self._pmeter = cls(self._transport)
                    break
                except Error as err:
                    errors.append((pmtype, cls, err))

            if not self._pmeter:
                self._probe_error(errors)

    def __getattr__(self, name):
        """
        If an attribute is not found in PowerMeter, then it is searched for in 'self._pmeter', the
        object representing a specific power meter model (eg., WT310).
        """
        return getattr(self._pmeter, name)

    def __enter__(self):
        """Enter the runtime context."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Exit the runtime context."""
        self.close()
