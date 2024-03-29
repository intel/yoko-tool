#!/usr/bin/env python
#
# Copyright (C) 2016-2023 Intel Corporation
# SPDX-License-Identifier: GPL-2.0-only
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Author: Helia Correia <helia.correia@linux.intel.com>

"""This module defines the exception types used in this project."""

class Error(Exception):
    """Most of the error conditions of the project cause exceptions of this type."""

    def __init__(self, msg):
        """The class constructor."""

        super(Error, self).__init__(msg)

        assert isinstance(msg, str)
        self.msg = msg

    def __str__(self):
        """The string representation of the exception."""
        return self.msg

class ErrorBadArgument(Error):
    """This exception is thrown when the argument for a command is incorrect."""

    def __init__(self, cmd, arg, msg=None):
        """The class constructor."""

        if not msg:
            msg = "unacceptable argument '%s' for command '%s'" % (arg, cmd)
        super(ErrorBadArgument, self).__init__(msg)
        self.cmd = cmd
        self.arg = arg

class ErrorBadResponse(Error):
    """This exception is thrown when power beter response is different from what we expected."""

    def __init__(self, raw_cmd=None, response=None, msg=None):
        """The class constructor."""

        if not msg and raw_cmd and response:
            msg = "unexpected power meter response '%s' to the '%s' command" % (response, raw_cmd)
        super(ErrorBadResponse, self).__init__(msg)

class ErrorDeviceNotFound(Error):
    """This exception is thrown when the requested device doesn't exist in any config file."""

    def __init__(self, devnode=None, paths=None, msg=None):
        """The class constructor."""

        if not msg and devnode and paths:
            msg = "device '%s' was not found in any of these configuration files:\n* %s" \
                    % (devnode, "\n* ".join(paths))
        super(ErrorDeviceNotFound, self).__init__(msg)
        self.devnode = devnode
        self.paths = paths

class TransportError(Error):
    """A class for all errors raised by the 'Transport' module."""
