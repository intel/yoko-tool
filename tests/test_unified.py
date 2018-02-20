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
This is a 'py.test' test for the PowerMeter module.
"""

# pylint: disable=redefined-outer-name
# pylint: disable=too-few-public-methods

from __future__ import absolute_import, division, print_function
import os
import time
import random
import logging
import subprocess

import pytest
from yokolibs import PowerMeter, _config, _logging

class CmdLineArgs(object):
    """A dummy command-line arguments class."""
    devnode = None

_LOG = logging.getLogger()
_logging.setup_logger(_LOG, getattr(logging, pytest.config.getoption("--loglevel").upper()))

class YokotoolPowerMeter():
    """
    This class emulated the 'PowerMeter' class but uses yokotool underneath. This way we can test
    yokotool and the PowerMeter class API the same way.
    """

    def command(self, cmd, arg=None):
        """The 'command' method which ends up running the tool."""

        if cmd == "wait-data-update":
            return

        if cmd == "configure-data-items":
            self._data_items = arg
            return

        if cmd == "read-data":
            ycmd = ["read", "--count=1", ",".join(self._data_items)]
        elif "integration" in cmd:
            if cmd.startswith("get-") or cmd.startswith("set-"):
                ycmd = cmd.split("-")[-1]
            else:
                ycmd = cmd.split("-")[0]
            ycmd = ["integration", ycmd]
        else:
            ycmd = cmd.split("-", 1)

        ycmd = self._ycmd_prefix + ycmd
        if arg:
            ycmd.append(str(arg))

        try:
            _LOG.info("%s", " ".join(ycmd))
            result = subprocess.check_output(ycmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            raise PowerMeter.Error(str(err))

        if not result:
            return None

        result = str(result.decode("utf-8").strip())
        if cmd == "read-data":
            result = result.splitlines()[-1].split(",")
        return result

    def close(self):
        """Nothing to do on close."""
        pass

    def __init__(self, **kwargs):
        """The constructuor."""

        self._data_items = None

        basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self._yokotool_path = os.path.join(basedir, "yokotool")
        assert os.path.exists(self._yokotool_path)

        self._ycmd_prefix = [self._yokotool_path]
        for name, val in kwargs.items():
            if name == "devnode":
                self._ycmd_prefix.append(kwargs["devnode"])
            else:
                self._ycmd_prefix.append("--%s=%s" % (name, val))

        # Fake the "PowerMeter" commands dictionary.
        pmeter = PowerMeter.PowerMeter(**kwargs)
        self.commands = pmeter.commands
        self.max_data_items = pmeter.max_data_items
        pmeter.close()

def prepare_pmeter(pmeter):
    """Prepare the power meter for testing."""

    # Reset the integration.
    try:
        pmeter.command("stop-integration")
    except PowerMeter.Error:
        pass
    try:
        pmeter.command("reset-integration")
    except PowerMeter.Error:
        pass

    pmeter.command("set-integration-mode", "normal")
    pmeter.command("set-integration-timer", "0")

    assert pmeter.command("get-integration-state") == "reset"
    assert pmeter.command("set-smoothing-status", "off") is None

@pytest.fixture(params=[PowerMeter.PowerMeter, YokotoolPowerMeter])
def pmeter(devspec, request):
    """Returns a 'PowerMeter' class instance for the given device node."""

    args = CmdLineArgs()
    secname = None
    if "/" in devspec or os.path.exists(devspec):
        args.devnode = devspec
    else:
        secname = devspec

    config = _config.process_config(secname=secname, args=args)
    pmeter = request.param(**config)
    prepare_pmeter(pmeter)
    yield pmeter
    pmeter.close()

def test_get(pmeter):
    """Verify all the "get something" commands."""

    for cmd in pmeter.commands:
        if cmd.startswith("get-"):
            result = pmeter.command(cmd)
            assert result
            if "choices" in cmd:
                assert result in cmd["choices"]

def set_every_choice(pmeter, cmd, verify):
    """Go through each possible value of a command and set it."""

    get_cmd = "get-%s" % cmd
    set_cmd = "set-%s" % cmd

    if set_cmd not in pmeter.commands or not pmeter.commands[set_cmd]["choices-set"]:
        return

    orig = pmeter.command(get_cmd)

    for val in pmeter.commands[set_cmd]["choices"]:
        pmeter.command(set_cmd, val)
        if verify:
            assert pmeter.command(get_cmd) == val

    pmeter.command(set_cmd, orig)
    if verify:
        assert pmeter.command(get_cmd) == orig

def test_set(pmeter):
    """Verify some of the the "get something" commands."""

    for cmd in pmeter.commands:
        verify = True
        if not cmd.startswith("set-"):
            continue
        # Skip the range-related commands, they are potentially unsafe to randomly change.
        if "-range" in cmd:
            continue
        # On WT210 remote mode gets enabled when any command is sent, so disable validation.
        if cmd == "set-remote-mode":
            verify = False
        set_every_choice(pmeter, cmd[4:], verify)

    # Set ranges to the max. possible values.
    value = pmeter.commands["get-current-range"]["choices"][-1]
    pmeter.command("set-current-range", value)
    assert pmeter.command("get-current-range") == value
    value = pmeter.commands["get-voltage-range"]["choices"][-1]
    pmeter.command("set-voltage-range", value)
    assert pmeter.command("get-voltage-range") == value
    # Enable auto-range to make sure power meter selects the reasonable one.
    pmeter.command("set-current-auto-range", "on")
    pmeter.command("set-voltage-auto-range", "on")

def test_read(pmeter):
    """Test measurement data reading functionality."""

    data_items = pmeter.commands["read-data"]["choices"]
    max_items = pmeter.max_data_items

    # Run several test with random data items.
    for _ in range(16):
        items = []
        for idx in random.sample(range(0, len(data_items)), random.randint(1, max_items)):
            items.append(data_items[idx])

        pmeter.command("configure-data-items", items)
        data = pmeter.command("read-data")
        assert len(data) == len(items)
        pmeter.command("wait-data-update")
        data = pmeter.command("read-data")
        assert len(data) == len(items)

def test_integration(pmeter):
    """Test the integration functionality."""

    modes = pmeter.commands["get-integration-mode"]["choices"]

    # Go through every mode.
    for mode in modes:
        if mode == "continuous":
            timer = "100"
            pmeter.command("set-integration-timer", timer)
            assert pmeter.command("get-integration-timer") == timer

        pmeter.command("set-integration-mode", mode)
        assert pmeter.command("get-integration-mode") == mode

        # Read 4 data items with integration.
        pmeter.command("start-integration")
        assert "start" in pmeter.command("get-integration-state")

        pmeter.command("configure-data-items", ["P", "I", "V"])
        for _ in range(4):
            pmeter.command("wait-data-update")
            data = pmeter.command("read-data")
            assert len(data) == 3

        # And without integration.
        pmeter.command("stop-integration")
        assert "stop" in pmeter.command("get-integration-state")

        pmeter.command("configure-data-items", ["P", "I", "V"])
        for _ in range(4):
            pmeter.command("wait-data-update")
            data = pmeter.command("read-data")
            assert len(data) == 3

        # And again with integration.
        pmeter.command("start-integration")
        assert "start" in pmeter.command("get-integration-state")
        for _ in range(4):
            pmeter.command("wait-data-update")
            data = pmeter.command("read-data")
            assert len(data) == 3

        pmeter.command("stop-integration")
        assert "stop" in pmeter.command("get-integration-state")
        pmeter.command("reset-integration")
        assert pmeter.command("get-integration-state") == "reset"

def test_bad_command(pmeter):
    """Verify that bad power meter commands raise an exception."""

    with pytest.raises(PowerMeter.Error):
        pmeter.command(" get-id")
        pmeter.command("get-id ")
        pmeter.command("get-id_")
        pmeter.command("set-current-range", None)
        pmeter.command("set-current-range", "")
        pmeter.command("set-current-range", -1)
        pmeter.command("set-current-range", 0)
        pmeter.command("set-current-range", float(0))
        pmeter.command("set-current-range", "0")
