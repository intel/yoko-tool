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

"""This module implements the exception types used by all the modules in this project."""

class Error(Exception):
    """Most of the error conditions of this project cause exceptions of this type."""
    pass

class ErrorBadArgument(Exception):
    """
    This exception is thrown when the argument for a command is incorrect. The 'Exception' object
    provides the 'hint' attribute which is a string describing what would be the correct argument.
    """

    def __init__(self, arg, hint):
        """The class constructor."""

        # Call the class constructor first
        super(ErrorBadArgument, self).__init__(arg, hint)

        self._arg = arg
        self.hint = hint

    def __str__(self):
        """Return a formatted error message."""
        return "unacceptable argument \"%s\", use: %s" % (self._arg, self.hint)
