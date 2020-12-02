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
This is an internal module that parses the yokotool configuration file.
"""

import os
import pprint
import logging
try:
    import ConfigParser as configparser
except ImportError:
    import configparser
from yokolibs import Helpers
from yokolibs.Exceptions import Error

SYSTEM_CFG_FILE = "/etc/yokotool.conf"
USER_CFG_FILE_NAME = ".yokotool.conf"

_LOG = logging.getLogger("main")

# The yokotool configuration options.
CONFIG_OPTIONS = {
    "devnode"  : {"type" : str},
    "baudrate" : {"type" : int},
    "pmtype"   : {"type" : str},
}

def _process_config_file(cfgfile, secname, config):
    """
    Process a configuration file 'cfcfile' and update the 'config' dictionary with the contents of
    the 'secname' section.
    """

    if not secname:
        secname = "default"

    if not cfgfile.has_section(secname):
        return

    # Merge the found configuration file section into 'config'.
    for name, val in cfgfile.items(secname):
        if name not in CONFIG_OPTIONS:
            raise Error("unknown configuration option '%s' in section '%s' of '%s'"
                        % (name, secname, cfgfile.path))

        try:
            val = CONFIG_OPTIONS[name]["type"](val)
        except (ValueError, TypeError):
            raise Error("bad value for the '%s option in section '%s' of '%s':\n"
                        "cannot translate the value to the '%s' type"
                        % (name, secname, cfgfile.path, CONFIG_OPTIONS[name]["type"].__name__))

        config[name] = val

def _iteratate_configs():
    """
    For every existing yokotool configuration file, build and yield the 'configparser' object.
    """

    user_cfgfile = os.path.join(os.path.expanduser("~"), USER_CFG_FILE_NAME)
    for path in (SYSTEM_CFG_FILE, user_cfgfile):
        if os.path.isfile(path):
            try:
                cfgfile = configparser.ConfigParser()
                cfgfile.read(path)
            except configparser.Error as err:
                raise Error("faled to parse configuration file '%s':\n%s" % (path, err))
            cfgfile.path = path
            yield cfgfile

def process_config(secname=None, overrides=None):
    """
    Load and process yokotool configuration files. First the '/etc/yokotool.conf' file is processed,
    then the '$HOME/.yokotool.conf' file. The optional 'secname' argument specifies the section of
    the configuration files to process. If the argument is not provided, the "default" section is
    processed instead.

    The 'overrides' argument, if provided, may include yokotool configuration options that will
    override the options from the configuration files. Here is an example.

    Configuration file: devnode=/dev/abc
    Overrides: devnode=/dev/xyz

    The resulting dictionary will contain 'devnode=/dev/xyz'. The 'overrides' argument may both be
    dictionary (e.g., include 'overrides["devnode"]') or any other object including configuration
    options as attributes (e.g., 'overrides.devnode').
    """

    config = {}
    paths = []
    for cfgfile in _iteratate_configs():
        paths.append(cfgfile.path)
        _process_config_file(cfgfile, secname, config)

    if not config and paths and secname:
        raise Error("section '%s' was not found in any for these configuration files:\n* %s" \
                    % (secname, "\n* ".join(paths)))

    if overrides:
        for name in CONFIG_OPTIONS:
            val = getattr(overrides, name, None)
            if not val and Helpers.is_dict(overrides):
                val = overrides.get(name)
            if val:
                config[name] = val

    if _LOG.getEffectiveLevel() == logging.DEBUG:
        _LOG.debug("the final configuration:\n%s", pprint.pformat(config, indent=4))

    return config

def get_section_names():
    """Returns all section names found in all configuration files."""

    sections = set()
    for cfgfile in _iteratate_configs():
        sections.update(cfgfile.sections())
    return list(sections)
