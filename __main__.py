#!/usr/bin/python
#
# Copyright (C) 2013-2020 Intel Corporation
# SPDX-License-Identifier: GPL-2.0-only
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

import re
import sys
from yokolibs.yokotool import main

if __name__ == '__main__':
    sys.argv[0] = re.sub(r'(-script\.pyw|\.exe|\.pyz)?$', '', sys.argv[0])
    sys.exit(main())
