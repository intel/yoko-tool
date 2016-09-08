#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Copyright (c) 2013-2016 Intel, Inc.
# License: GPLv2
# Author: Andy Shevchenko <andriy.shevchenko@linux.intel.com>
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
Transport interface class to an instrument. This layer provides basic functions to communicate with
the instrument, such as 'read()' and 'write()'.

Currently, only the USBTMC transport is supported.
"""

import os
import logging
import threading
from fcntl import ioctl

from yokolibs._exceptions import Error

class _Transport(object):
    """Virtual base class for the transport interface."""

    def __init__(self, devnode):
        """The virtual base class constructor."""

        self._name = self.__class__.__name__
        self._log = logging.getLogger(self._name)
        self._devnode = devnode

    def _dbg(self, message): # pylint: disable=no-self-use
        """Print a debug message."""
        self._log.debug("%s: %s", self._devnode, message.rstrip())

    def read(self, size):
        """Abstract method to be implemented in child classes."""
        pass

    def write(self, data):
        """Abstract method to be implemented in child classes."""
        pass

    def query(self, command, size=4096):
        """Write 'command' and return the read response."""

        self.write(command)
        return self.read(size)

    def queryline(self, command):
        """
        Write 'command' and return the read response split per lines, excluding the line break.
        """

        result = self.query(command)
        if result:
            return result.splitlines()[0]
        return ''

    def ioctl(self, fobj, operation):
        """
        Execute specific IOCTL to ensure that we are dealing with the expected type of character
        device.
        """

        try:
            ioctl(fobj, operation)
        except IOError as err:
            if err.errno == os.errno.ENOTTY:
                raise Error("\"{}\" is not a {} device".format(self._devnode, self._name))
            raise Error("ioctl \"{}\" for device \"{}\" failed: {}".format(operation, self._devnode,
                                                                           err))


# Clear the device's input and output buffers
_USBTMC_IOCTL_CLEAR = 0x5b02

class USBTMC(_Transport):
    """
    Simple implementation of a USBTMC device interface using the Linux kernel USBTMC character
    device driver.
    """

    def __init__(self, devnode='/dev/usbtmc0'):
        """
        The class constructor. The 'devnode' argument is the USBTMC device node to use as a
        transport.
        """

        self._fd = None
        self._close_mutex = threading.Lock()

        super().__init__(devnode)

        try:
            self._fd = os.open(self._devnode, os.O_RDWR)
        except OSError as err:
            raise Error("error opening device \"{}\": {}".format(self._devnode, err))

        # Make sure the device is a USBTMC device by invoking a USBTMC-specific IOCTL and checking
        # that it is supported.
        super().ioctl(self._fd, _USBTMC_IOCTL_CLEAR)

    def __del__(self):
        """The class destructor."""
        self.close()

    def write(self, data):
        """Write command directly to the device."""

        try:
            os.write(self._fd, bytes(data, 'utf-8'))
        except OSError as err:
            raise Error("error while writing to device \"{}\": {}".format(self._devnode, err))

        self._dbg("sent: {}".format(data))

    def read(self, size=4096):
        """Read an arbitrary amount of data directly from the device."""

        try:
            data = os.read(self._fd, size).decode("utf-8")
        except OSError as err:
            raise Error("error while reading from device \"{}\": \"{}\"".format(self._devnode, err))

        self._dbg("received: {}".format(data))

        return data

    def close(self):
        """Close the power meter transport and free the resources."""

        self._close_mutex.acquire()
        if self._fd:
            os.close(self._fd)
            self._fd = None
        self._close_mutex.release()
