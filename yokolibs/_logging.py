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
Configure the logger.
"""

# pylint: disable=too-few-public-methods

import sys
import logging

def setup_logger(logobj, loglevel, info_stream=sys.stdout, error_stream=sys.stderr):
    """
    A helper function which sets up and configures the 'logobj' logger. The log level is initialized
    to 'loglevel'. The default is that 'info' messages go to the standard output stream while
    'debug', 'warning' and 'error' messages go to the standard error stream. However, 'info_stream'
    and 'error_stream' parameters can be used to define custom streams for the messages.
    """

    logobj.info_stream = info_stream
    logobj.error_stream = error_stream

    # Esc-sequences for coloured output if stderr is a terminal.
    if logobj.error_stream.isatty():
        logobj.esc_red = '\033[31m'
        logobj.esc_yellow = '\033[33m'
        logobj.esc_green = '\033[32m'
        logobj.esc_bright_green = '\033[32m\033[1m'
        logobj.esc_bright_white = '\033[37m\033[1m'
        logobj.esc_end = '\033[0m'
    else:
        logobj.esc_red = logobj.esc_yellow = logobj.esc_green = logobj.esc_bright_green = ""
        logobj.esc_bright_white = logobj.esc_end = ""

    class MyFormatter(logging.Formatter):
        """
        A custom formatter for logging messages handling different formats for different log levels.
        """

        def _get_fmt(self):
            """This helper is needed for Python 2 and Python 3 compatibility."""

            if hasattr(self, "_style"):
                return self._style._fmt # pylint: disable=protected-access
            return self._fmt

        def _set_fmt(self, fmt):
            """This helper is needed for Python 2 and Python 3 compatibility."""

            if hasattr(self, "_style"):
                self._style._fmt = fmt # pylint: disable=protected-access
            else:
                self._fmt = fmt

        def format(self, record):
            """
            The formatter which simply prefixes all debugging messages with a time-stamp and makes
            sure the info messages stay intact.
            """

            # Add a time-stamp to debug messages.
            if record.levelno == logging.DEBUG:
                self._set_fmt(self._dbg_fmt)

            # Leave the info messages without any formatting.
            if record.levelno == logging.INFO:
                self._set_fmt("%(message)s")

            result = logging.Formatter.format(self, record)
            self._set_fmt(self._orig_fmt)
            return result

        def __init__(self, fmt=None, datefmt=None):
            """The constructor."""

            logging.Formatter.__init__(self, fmt, datefmt)

            self._orig_fmt = self._get_fmt()
            # Prefix with green-colored time-stamp, module name and line number.
            self._dbg_fmt = "[" + logobj.esc_green + "%(asctime)s" + logobj.esc_end + \
                            "] [%(module)s,%(lineno)d] " + self._get_fmt()

    class MyFilter(logging.Filter):
        """A custom filter which allows only certain log levels to go through."""

        def filter(self, record):
            """Filter out all log levels except the ones user specified."""

            if record.levelno in self._let_go:
                return True
            return False

        def __init__(self, let_go):
            """The constructor."""

            logging.Filter.__init__(self)
            self._let_go = let_go

    # Change log level names to something nicer than the default all-capital 'INFO', etc.
    logging.addLevelName(logging.ERROR, logobj.esc_red + "ERROR" + logobj.esc_end)
    logging.addLevelName(logging.WARNING, logobj.esc_yellow + "WARNING" + logobj.esc_end)
    logging.addLevelName(logging.DEBUG, "debug")
    logging.addLevelName(logging.INFO, "info")
    logobj.setLevel(loglevel)

    # Remove existing handlers.
    logobj.handlers = []

    # Install our handlers.
    formatter = MyFormatter("yokotool: %(levelname)s: %(message)s", "%H:%M:%S")
    where = logging.StreamHandler(logobj.error_stream)
    where.setFormatter(formatter)
    where.addFilter(MyFilter((logging.ERROR, logging.WARNING, logging.DEBUG)))
    logobj.addHandler(where)

    where = logging.StreamHandler(logobj.info_stream)
    where.setFormatter(formatter)
    where.addFilter(MyFilter((logging.INFO,)))
    logobj.addHandler(where)
