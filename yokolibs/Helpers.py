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
Misc. helper functions.
"""

from yokolibs._exceptions import Error

def is_int(value):
    """
    Return 'True' if 'value' can be converted into integer using 'int()' and 'False' otherwise.
    """

    try:
        value = int(value)
    except (ValueError, TypeError):
        return False
    return True

def parse_duration(htime, default_unit="s"):
    """
    This function does the opposite to what human_time does - parses the human time string and
    returns integer number of seconds. However, this function does not support milliseconds. Default
    unit can be passed to handle cases where 'htime' is an integer. So for example, 'htime' could
    simply '1', and if 'default_unit' is 's', then this will be interpreted as '1s'.
    """

    htime = htime.strip()

    if htime.isdigit():
        htime += default_unit

    keys = ["hours", "minutes", "seconds"]
    tokens = {}

    rest = htime.lower()
    for spec, key in zip(list("hms"), keys):
        split = rest.split(spec, 1)
        if len(split) > 1:
            tokens[key] = split[0]
            rest = split[1]
        else:
            rest = split[0]

    if rest.strip():
        if not tokens and is_int(rest):
            # This is the case when no "hms" specifiers were given, in which case we assume the
            # given integer is the amount of seconds.
            tokens["seconds"] = rest
        else:
            raise Error("bad time length specification '%s', cannot parse this part: %s"
                        % (htime, rest))

    for key, val in tokens.items():
        if not is_int(val):
            raise Error("bad amount of %s '%s' in time length specification '%s'"
                        % (key, val, htime))

    hours = int(tokens.get("hours", 0))
    mins = int(tokens.get("minutes", 0))
    secs = int(tokens.get("seconds", 0))
    return hours * 60 * 60 + mins * 60 + secs
