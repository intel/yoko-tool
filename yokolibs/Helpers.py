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
Misc. helper functions.
"""

from yokolibs.Exceptions import Error

def is_int(value):
    """
    Return 'True' if 'value' can be converted into integer using 'int()' and 'False' otherwise.
    """

    try:
        value = int(value)
    except (ValueError, TypeError):
        return False
    return True

def is_dict(obj):
    """
    Return 'True' if 'obj' is a dictionary (works for 'OrderedDicts' too) and 'False' otherwise.
    """

    try:
        obj = obj.keys()
    except AttributeError:
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
