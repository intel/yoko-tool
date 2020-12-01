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
Transport interface class to an instrument. This layer provides basic functions to communicate with
the instrument, such as 'readline()' and 'writeline()'.
"""

from __future__ import absolute_import, division, print_function
import os
import stat
import errno
import logging
import textwrap
from fcntl import ioctl

from yokolibs.Exceptions import Error, TransportError

try:
    import serial
except ImportError:
    raise TransportError("the serial transport is not supported on this system because it is "
                         "missing the 'serial' Python module. Please, install it. It usually comes "
                         "from the 'pyserial' package.")

class _BadInput(Error):
    """
    We use this exception internally in this module do disctinguish between situations when the
    device type may be not what we assume (e.g., USB vs Serial) and a situation when the input
    arguments are incorrect.
    """

# This makes sure all classes are the new-style classes by default.
__metaclass__ = type # pylint: disable=invalid-name

class _TransportBase():
    """The base class all transport classes inherit from."""

    # Name of this transport.
    name = None

    def _dbg(self, message):
        """Print a debug message."""
        self._log.debug("%s: %s", self.devnode, message.rstrip())

    def readline(self):
        """Abstract method to be implemented in child classes."""

    def writeline(self, data):
        """Abstract method to be implemented in child classes."""

    def queryline(self, command):
        """Write 'command' and return the read response."""

        self.writeline(command)
        return self.readline()

    def ioctl(self, fobj, operation):
        """
        Execute specific IOCTL to ensure that we are dealing with the expected type of character
        device.
        """

        try:
            ioctl(fobj, operation)
        except IOError as err:
            if err.errno == errno.ENOTTY:
                raise Error("'%s' is not a '%s' device" % (self.devnode, self.name))
            raise TransportError("ioctl '%#X' for device '%s' failed:\n%s"
                                 % (operation, self.devnode, err))

    def __init__(self, devnode, **kwargs): # pylint: disable=unused-argument
        """The base class constructor."""

        if not os.path.exists(devnode):
            raise _BadInput("device node '%s' does not exist" % devnode)

        try:
            stat_data = os.stat(devnode)
        except OSError as err:
            raise _BadInput("failed access device '%s':\n%s" % (devnode, err))

        if not stat.S_ISCHR(stat_data.st_mode):
            raise _BadInput("device node '%s' is not a character device" % devnode)

        self._log = logging.getLogger(self.name)
        self.devnode = devnode

class _USBTMC(_TransportBase):
    """
    The USB TMC device transport (e.g., the Yokogawa WT310 power meter connected via the USB
    interface is a USB TMC device from the host system point of view).
    """

    name = "usbtmc"

    # IOCTL number for clearing the device's input and output buffers.
    _clear_ioctl = 0x5b02

    def writeline(self, data):
        """Write a line to the device."""

        assert not data.endswith("\n")
        data += "\n"

        try:
            os.write(self._fd, data.encode('utf-8'))
        except OSError as err:
            raise TransportError("error while writing to device '%s':\n%s" % (self.devnode, err))

        self._dbg("sent: %s" % data)

    def readline(self):
        """Read a line from the device."""

        try:
            data = os.read(self._fd, 4096).decode("utf-8")
        except OSError as err:
            raise TransportError("error while reading from device '%s':\n%s" % (self.devnode, err))

        if not isinstance(data, str):
            try:
                data = str(data.decode("utf-8"))
            except UnicodeError as err:
                raise TransportError("failed to decode unicode response:\n%s" % err)

        data = data.strip()
        self._dbg("received: %s" % data)
        return data

    def close(self):
        """Close the transport object and free the resources."""

        if self._fd:
            os.close(self._fd)
            self._fd = None

    def __init__(self, devnode, **kwargs):
        """
        The class constructor. The 'devnode' argument is the USBTMC device node to use as
        transport.
        """

        self._fd = None
        super(_USBTMC, self).__init__(devnode)

        try:
            self._fd = os.open(self.devnode, os.O_RDWR)
        except OSError as err:
            raise _BadInput("error opening device '%s':\n%s" % (self.devnode, err))

        # Make sure the device is a USBTMC device by invoking a USBTMC-specific IOCTL and checking
        # that it is supported.
        super(_USBTMC, self).ioctl(self._fd, self._clear_ioctl)

    def __del__(self):
        """The class destructor."""
        self.close()

class _Serial(_TransportBase):
    """The RS-232 device transport."""

    name = "serial"

    def writeline(self, data):
        """Write a line to the device."""

        assert not data.endswith("\n")
        data += "\n"

        try:
            self._ser.write(data.encode("utf-8"))
        except self._serial.SerialException as err:
            raise TransportError("error while writing to device '%s':\n%s" % (self.devnode, err))

        self._dbg("sent: %s" % data)

    def readline(self):
        """Read a line from the device."""

        try:
            data = self._ser.readline()
            if not data:
                raise TransportError("time out while reading from device '%s'" % self.devnode)
        except self._serial.SerialException as err:
            raise TransportError("error while reading from device '%s':\n%s" % (self.devnode, err))

        if not isinstance(data, str):
            try:
                data = str(data.decode("utf-8"))
            except UnicodeError as err:
                raise TransportError("failed to decode unicode response:\n%s" % err)

        data = data.strip()
        self._dbg("received: %s" % data)
        return data

    def close(self):
        """Close the power meter transport and free the resources."""

        if self._ser:
            self._ser.close()
            self._ser = None

    def __init__(self, devnode, **kwargs):
        """
        The class constructor. The 'devnode' argument is the serial device node to use as
        transport.
        """

        super(_Serial, self).__init__(devnode)

        self._ser = None
        self._serial = serial
        try:
            self._ser = serial.Serial()
        except serial.SerialException as err:
            raise TransportError("cannot initialize the serial device '%s':\n%s" % (devnode, err))

        self._ser.port = devnode
        self._ser.timeout = self._ser.write_timeout = 5
        if "baudrate" in kwargs and kwargs["baudrate"] is not None:
            bauds = [1200, 2400, 4800, 9600, 19200, 38400, 57600]
            if kwargs["baudrate"] and kwargs["baudrate"] not in bauds:
                raise _BadInput("bad baud rate '%d'" % kwargs["baudrate"])
        else:
            kwargs["baudrate"] = 9600

        self._log.debug("using baud rate %d for '%s'", kwargs["baudrate"], devnode)
        self._ser.baudrate = kwargs["baudrate"]

        try:
            self._ser.open()
        except serial.SerialException as err:
            raise TransportError("cannot initialize the serial device '%s':\n%s" % (devnode, err))

    def __del__(self):
        """The class destructor."""
        self.close()

class Transport(): # pylint: disable=too-few-public-methods
    """
    This class is what end users are supposed to be using. It hides the transport differences and
    provides a uniform API for talking to the device.
    """

    def __new__(cls, devnode, **kwargs):
        """
        The class constructor. The 'devnode' argument is a device node that should be used to use as
        the transport.
        """

        tclasses = (_USBTMC, _Serial)
        errors = []
        for tclass in tclasses:
            try:
                transport = tclass(devnode, **kwargs)
                return transport
            except _BadInput as err:
                raise
            except Error as err:
                errors.append((tclass, err))

        wrapper = textwrap.TextWrapper(width=79)

        msg = "unknown type of the device '%s'. Here is the log of all the attempts to recognize " \
              "the device type." % devnode
        lines = wrapper.wrap(msg)

        wrapper.initial_indent = " * "
        wrapper. subsequent_indent = "   "
        for tclass, err in errors:
            msg = "%s: %s" % (tclass.name, err)
            lines += wrapper.wrap(msg)

        raise TransportError("\n".join(lines))
