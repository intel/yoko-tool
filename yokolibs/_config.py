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
import logging
try:
    import ConfigParser as configparser
except ImportError:
    import configparser
from yokolibs._exceptions import Error

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

def iteratate_configs():
    """
    Iterate over configuration files and yied the 'configparser' objects.
    """

    user_cfgfile = os.path.join(os.path.expanduser("~"), USER_CFG_FILE_NAME)
    for path in (SYSTEM_CFG_FILE, user_cfgfile):
        if os.path.isfile(path):
            try:
                cfgfile = configparser.ConfigParser()
                cfgfile.read(path)
            except configparser.Error as err:
                raise Error("failed to parse configuration file '%s':\n%s" % (path, err))
            cfgfile.path = path
            yield cfgfile

def process_config(secname=None, args=None):
    """
    Load and process the configuration files. First the '/etc/yokotool.conf' file is processed, then
    the '$HOME/.yokotool.conf' file. The optional 'secname' argument specifies the section of the
    configuration files to process. If the argument is not provided, the "default" section is
    processed instead.

    Once the configuration files are process the (supposedly) command-line arguments 'args' are
    merged into the resulting configuration dictionary. In case of a conflict the command-line
    arguments win. The configuration dictionary is returned at the end.
    """

    config = {}
    paths = []
    for cfgfile in iteratate_configs():
        paths.append(cfgfile.path)
        _process_config_file(cfgfile, secname, config)

    if not config and paths and secname:
        raise Error("section '%s' was not found in any for these configuration files:\n* %s" \
                    % (secname, "\n* ".join(paths)))

    if args:
        for name in CONFIG_OPTIONS:
            if hasattr(args, name) and getattr(args, name) is not None:
                config[name] = getattr(args, name)

    if _LOG.getEffectiveLevel() == logging.DEBUG:
        import pprint
        _LOG.debug("the final configuration:\n%s", pprint.pformat(config, indent=4))

    return config

def get_section_names():
    """Returns all section names found in all configuration files."""

    sections = set()
    for cfgfile in iteratate_configs():
        sections.update(cfgfile.sections())
    return list(sections)
