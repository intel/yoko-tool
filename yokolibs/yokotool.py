#!/usr/bin/python
#
# Copyright (C) 2013-2023 Intel Corporation
# SPDX-License-Identifier: GPL-2.0-only
#
# -*- coding: utf-8 -*-
# vim: ts=4 sw=4 tw=100 et ai si
#
# Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>

"""
A tool for controlling the Yokogawa power meters.
"""

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-statements
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=no-member

from __future__ import absolute_import, division, print_function
import os
import sys
import time
import logging
import argparse
import textwrap
import subprocess

try:
    import argcomplete
except ImportError:
    argcomplete = None

from yokolibs import Transport, PowerMeter, Helpers, Config, Logging
from yokolibs.Exceptions import Error, ErrorDeviceNotFound, TransportError

VERSION = "2.2"
OWN_NAME = "yokotool"

LOG = logging.getLogger()

# The commands supported by this tool.
CMDLINE_COMMANDS = ("info", "read", "get", "set", "integration", "calibrate", "factory-reset")

# The sub-commands of the 'get' command that map directly to a "raw" command.
GET_SUBCOMMANDS = ("id", "installed-opts", "wiring-system")

# The sub-commands of the 'set' and 'get' commands that map directly to a "raw" command.
GETSET_SUBCOMMANDS = ("current-range", "voltage-range", "interval", "current-auto-range",
                      "voltage-auto-range", "crest-factor", "measurement-mode", "smoothing-status",
                      "smoothing-type", "smoothing-factor", "math", "line-filter", "freq-filter",
                      "sync-source", "max-hold", "hold", "remote-mode", "local-mode")

# This data structure describes the subcommands of 'integration' command.
# * name - name of the subcommand.
# * command - corresponding power meter's command (if any).
# * help - short/one line subcommand description.
# * descr - description of the subcommand.
INTEGRATION_SUBCMDS = (
    {
        "name"    : "wait",
        "command" : "start-integration",
        "descr"   : "Wait for integration to finish.",
    },
    {
        "name"    : "start",
        "command" : "start-integration",
        "descr"   : "Start integration.",
    },
    {
        "name"    : "stop",
        "command" : "stop-integration",
        "descr"   : "Stop integration.",
    },
    {
        "name"    : "reset",
        "command" : "reset-integration",
        "descr"   : "Reset integration.",
    },
)

# This data structure describes the properties of 'integration' command.
# * name - name of the property.
# * get-cmd - power meter's command to get the property.
# * set-cmd - power meter's command to set the property.
# * help - short/one line property description.
# * descr - description of the property.
INTEGRATION_PROPERTIES = (
    {
        "name"     : "state",
        "get-cmd"  : "get-integration-state",
        "descr"    : "Get integration state.",
    },
    {
        "name"     : "mode",
        "get-cmd"  : "get-integration-mode",
        "set-cmd"  : "set-integration-mode",
        "descr"    : "Get or set integration mode.",
    },
    {
        "name"     : "timer",
        "get-cmd"  : "get-integration-timer",
        "set-cmd"  : "set-integration-timer",
        "descr"    : "Get or set an integration timer value.",
    },
)

class ArgsParser(argparse.ArgumentParser):
    """
    This class re-defines the 'error()' method of the 'argparse.ArgumentParser' class in order to
    make it always print a hint about the '-h' option. It also overrides the 'add_argument()' method
    to include the '-d' option.
    """

    def __init__(self, *args, **kwargs):
        """Add '-d' to the 'parser' argument parser object."""

        kwargs["add_help"] = False
        super(ArgsParser, self).__init__(*args, **kwargs)

        text = "Show this help message and exit."
        self.add_argument("-h", action="help", help=text, dest="help")
        text = "Print debugging messages."
        self.add_argument("-d", action="store_true", help=text, dest="debug")

    def error(self, message):
        """Print the error message and exit."""

        message += "\nUse -h for help."
        super(ArgsParser, self).error(message)

def inject_default_subparser(subname, where, choices, anyway=False):
    """
    Python 'argparse' module does not support optional subcommands, but we often need them. For
    example, we often support a number of subcommands providing a choice of standard components A
    and B:
        $ mytool start consume A
        $ mytool start consume B
    And at the same time we want to allow users specifying a non-standard component, like a file
    with an arbitrary name:
        $ mytool start consume filename
    The standard 'argparse' module does not allow creating the default subparser which will be used
    for arbitrary file names, and this function helps solving the problem by injecting the 'subname'
    subcommand:
        $ mytool start consume subname filename
    which will handle the files. But 'subname' will be hidden from the users and they won't need to
    type it. Use 'argparse.SUPPRESS' to also hide it from the help output.

    The 'where' argument specifies where to insert the default 'subname' subcommand to. In our
    example 'where' would be '["start", "consume"]'. The 'choices' argument tells about the
    situations when the default subcommand must NOT be inserted at all. In our example if 'where'
    follows with 'A' or 'B', the default subcommand must not be inserted. In other words, 'choices'
    should be a collection of the standard subcommand names that can follow 'where'.

    The 'anyway' function argument is about how to handle something like this:
        $ mytool start consume [--options]
    No positional argument follows 'where' at all, so there is nothing to compare against 'choices'.
    If 'anyway' is 'True', 'subname' will be injected in this situation, otherwise it won't be
    injected.
    """

    if "-h" in sys.argv:
        return

    idx = argv_idx = where_idx = 0
    found = False
    for idx, arg in enumerate(sys.argv):
        # Skip options, we are only interested in positional arguments.
        if arg.startswith("-"):
            continue
        if where_idx < len(where):
            if arg == where[where_idx]:
                where_idx += 1
                argv_idx = idx
            elif where_idx != 0:
                return
        elif arg in choices or arg == subname:
            return
        else:
            found = True
            break

    if anyway and where_idx >= len(where):
        found = True

    if not found:
        return

    sys.argv.insert(argv_idx + 1, subname)
    LOG.debug("changed cmdline: %s", " ".join(sys.argv))

def parse_arguments():
    """Parse the input arguments."""

    text = """A tool to configure and control the Yokogawa WT310 power meter. Use one of the three
    methods of specifying the device: 1 - device node as the first argument, 2 - configuration file
    section name as the first argument, 3 - just add the '[default]' section to the configuration
    file. Refer to the online documentation for details."""
    pars = ArgsParser(description=text, prog=OWN_NAME)

    if "_ARGCOMPLETE" in os.environ:
        text = "The power meter device node specification."
        pars.add_argument("devspec", help=text, choices=Config.get_section_names())

    text = "Print version and exit."
    pars.add_argument("--version", action="version", help=text, version=VERSION)

    text = f"""The power meter type. Even though {OWN_NAME} tries to auto-detect the power meter
               type, it is recommended to specify it with this option or in the configuration file.
               """
    pars.add_argument("--pmtype", help=text)

    text = "Baud rate (RS-232 connection only)."
    pars.add_argument("--baudrate", type=int, help=text)

    text = "Redirect the output to a file instead of the standard output stream."
    pars.add_argument("-o", "--outfile", help=text)

    subpars = pars.add_subparsers(title="supported commands", metavar="")
    subpars.required = True

    # Create a parser for the 'info' command.
    text = "Print device information."
    descr = "Print information about the power meter."
    pars1 = subpars.add_parser("info", help=text, description=descr)
    pars1.set_defaults(func=info_command)

    # Create a parser for the 'read' command.
    text = "Read measurement data."
    descr = "Read measurement data like power (P) or current (I) and output them in a CSV format."
    pars1 = subpars.add_parser("read", help=text, description=descr)
    pars1.set_defaults(func=read_command)
    text = "Comma-separated list of data items to read."
    pars1.add_argument("value", nargs="?", metavar="items", help=text)
    text = "Redirect the output to a file instead of the standard output stream."
    pars1.add_argument("-o", "--outfile", help=text)
    text = "The maximum count of measurements to read. The default is to never stop reading."
    pars1.add_argument("--count", type=int, help=text)
    text = """For how long time to read. Use 'h', 'm', and 's' for 'hours', 'minutes' and 'seconds'.
              The default unit is seconds. Example: 4m30s means 4 minutes and 30 seconds. If used
              with '--count' then reading will stops when any of the conditions is met."""
    pars1.add_argument("--time", help=text)
    text = """If the power meter is integratin, then by default reading stops when integration
           stops. This option disables this behavior and reading will continue beyond the
           integration timer."""
    pars1.add_argument("--ignore-integration", action="store_true", help=text)
    text = "Do not print the CSV header (the first line with the data items)."
    pars1.add_argument("--no-header", action="store_true", help=text)
    text = """By default this tool tries to align the read data by inserting blanks between read
              items to improve readability. This option disables the alignement."""
    pars1.add_argument("--no-align", action="store_true", help=text)
    text = "Everything going after this option is considered to be the optional command to " \
           "execute. The measurement data reading will continue until the command finishes. " \
           "If '--count' or '--time' are used as well, then reading will stop when any of " \
           "the conditions are met."
    pars1.add_argument("-c", "--command", dest="command", nargs=argparse.REMAINDER, help=text)

    # Create a parser for the 'get' command.
    text = "Get a property."
    descr = """Get a power meter property like the voltage range, etc. Note, there are more
               properties than listed here, use '--list' to get all the available properties as well
               as the possible property values."""
    pars1 = subpars.add_parser("get", help=text, description=descr)
    subpars1 = pars1.add_subparsers(title="properties", metavar="")
    subpars1.required = True

    for name in GETSET_SUBCOMMANDS + GET_SUBCOMMANDS:
        info = PowerMeter.COMMANDS["get-%s" % name]
        text = info["property-descr"].capitalize() + "."
        descr = info["descr"].capitalize() + "."
        pars2 = subpars1.add_parser(name, help=text, description=descr)
        pars2.set_defaults(name=name)
        pars2.set_defaults(func=get_command)

    # Other properties. We add the "other" subcommand, but it is hidden from the users.
    choices = GETSET_SUBCOMMANDS + GET_SUBCOMMANDS + ("current-range", "voltage-range")
    inject_default_subparser("other", ["get"], choices, anyway=True)
    pars2 = subpars1.add_parser("other")
    text = "Print full list of available properties."
    pars2.add_argument("--list", action="store_true", help=text)
    pars2.set_defaults(func=get_command)
    pars2.add_argument("name", nargs="?")

    # Create a parser for the 'set' command.
    text = "Set a property."
    descr = """Set a power meter property like the voltage range, etc. Note, there are more
               properties than listed here, use '--list' to get all the properties that can be
               change along with their possible values."""
    pars1 = subpars.add_parser("set", help=text, description=descr)
    subpars1 = pars1.add_subparsers(title="properties", metavar="")
    subpars1.required = True

    for name in GETSET_SUBCOMMANDS:
        info = PowerMeter.COMMANDS["get-%s" % name]
        text = info["property-descr"].capitalize() + "."
        descr = info["descr"].capitalize() + "."
        pars2 = subpars1.add_parser(name, help=text, description=descr)
        pars2.set_defaults(name=name)
        pars2.set_defaults(func=set_command)
        text = info["property-descr"].capitalize() + "."
        pars2.add_argument("arg", nargs="?", help=text)

    # Other properties. We add the "other" subcommand, but it is hidden from the users.
    choices = GETSET_SUBCOMMANDS + ("current-range", "voltage-range")
    inject_default_subparser("other", ["set"], choices, anyway=True)
    pars2 = subpars1.add_parser("other")
    text = "Print full list of available properties."
    pars2.add_argument("--list", action="store_true", help=text)
    pars2.set_defaults(func=set_command)
    pars2.add_argument("name", nargs="?")
    pars2.add_argument("arg", nargs="?")

    # Create a parser for the 'integration' command.
    text = "Integration commands."
    descr = "Control the 'integration' feature of the power meter."
    pars1 = subpars.add_parser("integration", help=text, description=descr)
    subpars1 = pars1.add_subparsers(title="subcommands", metavar="")
    subpars1.required = True

    for subcmd in INTEGRATION_SUBCMDS:
        pars2 = subpars1.add_parser(subcmd["name"], help=subcmd["descr"],
                                    description=subcmd["descr"])
        if subcmd["name"] == "wait":
            pars2.set_defaults(func=integration_wait_subcommand)
        else:
            pars2.set_defaults(subcmd=subcmd)
            pars2.set_defaults(func=integration_subcommands)

    for prop in INTEGRATION_PROPERTIES:
        pars2 = subpars1.add_parser(prop["name"], help=prop["descr"],
                                    description=prop["descr"])
        if prop["name"] in ("mode", "timer"):
            text = "The value to assign to 'integration %s'." % prop["name"]
            pars2.add_argument("value", nargs="?", help=text)
        pars2.set_defaults(prop=prop)
        pars2.set_defaults(func=integration_properties)

    # Create a parser for the 'calibrate' command.
    text = "Execute zero-level compensation."
    descr = "Execute zero-level compensation."
    pars1 = subpars.add_parser("calibrate", help=text, description=descr)
    pars1.set_defaults(func=calibrate_command)

    # Create a parser for the 'factory-reset' command.
    text = "Reset to factory settings."
    descr = "Reset the power meter to factory settings."
    pars1 = subpars.add_parser("factory-reset", help=text, description=descr)
    pars1.set_defaults(func=factory_reset_command)
    text = """In addition to resetting the power meter, configure it with generally reasonable
              default settings. This way the initial power meter configuration will be similar
              across various Yokogawa power meter flavors."""
    pars1.add_argument("--configure", action="store_true", help=text)

    if argcomplete:
        argcomplete.autocomplete(pars)
    return pars.parse_args()

def info_command(_, pmeter):
    """Implements the 'info' command."""

    for cmd, info in PowerMeter.COMMANDS.items():
        if not cmd.startswith("get-"):
            continue
        result = pmeter.command(cmd)
        LOG.info("%s: %s", info["property-descr"].capitalize(), result)

def _print_properties(pmeter, pfx):
    """Print available properties with the 'pfx' prefix."""

    wrapper = textwrap.TextWrapper(width=79)
    wrapper.initial_indent = " * "
    wrapper. subsequent_indent = "   "
    lines = []

    for cmd, info in pmeter.commands.items():
        if not cmd.startswith(pfx):
            continue
        lines += wrapper.wrap("%s - %s" % (cmd[4:], info["descr"]))

    LOG.info("\n".join(lines))

def get_command(args, pmeter):
    """Implements the 'get <something>' command."""

    if hasattr(args, "list") and args.list:
        _print_properties(pmeter, "get-")
        return

    if not args.name:
        raise Error("please, specify the property to get, use -h for help")

    cmd = "get-%s" % args.name
    if cmd not in pmeter.commands:
        raise Error("unknown power meter property '%s'" % args.name)
    LOG.info(pmeter.command("get-%s" % args.name))

def set_command(args, pmeter):
    """Implements the 'set <something>' command."""

    if hasattr(args, "list") and args.list:
        _print_properties(pmeter, "set-")
        return

    if not args.name:
        raise Error("please, specify the property to set, use -h for help")

    cmd = "set-%s" % args.name
    if not args.arg:
        LOG.info("Use:\n%s", pmeter.get_argument_help(cmd))
    else:
        if cmd not in pmeter.commands:
            raise Error("unknown power meter property '%s'" % (args.name))
        pmeter.command(cmd, args.arg)
    return

def read_command(args, pmeter):
    """Implements the 'read' command."""

    if not args.value:
        text = pmeter.get_argument_help("read-data")
        LOG.info("Use the following data items:\n%s", text)
        return

    ditems = [ditem.strip() for ditem in args.value.strip().strip(",").split(",")]
    pmeter.command("configure-data-items", ditems)

    count_limit = time_limit = None
    if args.count is not None:
        count_limit = args.count
    if args.time is not None:
        time_limit = Helpers.parse_duration(args.time)

    ignore_integration = args.ignore_integration
    if not ignore_integration:
        # No need to follow integration if it is not enabled.
        if pmeter.command("get-integration-state") != "start":
            ignore_integration = True

    if not args.no_header:
        LOG.info(",".join(ditems))

    proc = None
    if args.command:
        try:
            proc = subprocess.Popen(args.command)
        except OSError as err:
            raise Error("cannot run '%s':\n%s" % (" ".join(args.command), err))
        LOG.debug("started: %s", " ".join(args.command))

    # We keep the max. lengths of printed items in this dictionary in order to aling the output.
    maxlens = {idx : 0 for idx in range(len(ditems))}
    count = 0
    start_time = time.time()

    while True:
        if proc:
            exitcode = proc.poll()
            if exitcode is not None:
                LOG.debug("the executed process exited with code %d", exitcode)
                break

        if not ignore_integration:
            if pmeter.command("get-integration-state") != "start":
                LOG.debug("integration finished, exiting")
                break

        if time_limit is not None and time.time() - start_time > time_limit:
            LOG.debug("%s second(s) read time is out, exiting", time_limit)
            break

        if count_limit is not None and count >= count_limit:
            LOG.debug("read %d sample(s), exiting", count_limit)
            break

        pmeter.command("wait-data-update")
        data = pmeter.command("read-data")
        count += 1

        if args.no_align:
            LOG.info(",".join(data))
        else:
            print_data = []
            for idx in range(len(data) -1):
                maxlens[idx] = max(maxlens[idx], len(data[idx]))
                fmt = "%%-%ds" % (maxlens[idx] + 1)
                print_data.append(fmt % (data[idx] + ","))
            print_data.append(data[-1])
            LOG.info(" ".join(print_data))

def integration_wait_subcommand(_, pmeter):
    """
    This function implements the 'integration wait' subcommand. The implementation is very trivial
    since we just poll the integration state.
    """

    while True:
        integ_state = pmeter.command("get-integration-state")
        if integ_state != "start":
            break
        time.sleep(1)

def integration_subcommands(args, pmeter):
    """This function runs the subcommands of 'integration' command."""

    # Integration cannot start in 'continuous' mode when 'timer' is not set.
    if args.subcmd["name"] == "start":
        integ_timer = pmeter.command("get-integration-timer")
        integ_mode = pmeter.command("get-integration-mode")
        if integ_timer == "0" and integ_mode == "continuous":
            LOG.error("Please, set a timer value higher than '%s' to start integration in "
                      "'%s' mode.", integ_timer, integ_mode)
            return

    pmeter.command(args.subcmd["command"])

def integration_properties(args, pmeter):
    """This function reads or writes a value to the properties of 'integration' command."""

    # 'state' is a particular property which value can only be read and not written.
    if args.prop["name"] == "state" or args.value is None:
        if args.prop["get-cmd"] in pmeter.commands:
            LOG.info("%s", pmeter.command(args.prop["get-cmd"]))
        else:
            LOG.info("unfortunately '%s' does not provide the integration state information",
                     pmeter.pmtype)
    else:
        args_list = pmeter.get_argument_help(args.prop["set-cmd"])
        if str(args.value) in args_list or \
           Helpers.is_int(args.value) and 0 <= int(args.value) <= 36000000:
            pmeter.command(args.prop["set-cmd"], args.value)
        else:
            raise Error("unacceptable argument '%s', use: %s" % (args.value, args_list))

def calibrate_command(_, pmeter):
    """Implements the 'calibrate' command."""

    pmeter.command("clear")
    result = pmeter.command("calibrate")
    LOG.info(result)

def factory_reset_command(args, pmeter):
    """Implements the 'factory-reset' command."""

    pmeter.reset(configure=args.configure)

def fetch_devspec():
    """
    The first command line argument can be the power meter device node, the configuration file
    section name or none of that, in which case the "default" section from the configuration file
    will be used. We call this first argument 'devspec'. This function searches for the devspec and
    returns 'None' if it was not found. Otherwise this function removes the devspec from the command
    line in order to make it uniform and returns the devspec.
    """

    # Find the first non-option and non-command.
    devspec = None
    for idx, arg in enumerate(sys.argv[1:]):
        if arg.startswith("-"):
            continue
        if not arg in CMDLINE_COMMANDS:
            devspec = arg
            break

    if not devspec:
        return None

    # Now we have a the 'devspec', because it is not an option and not a supported command.
    #
    # But there is a potential problem: if user did not mean to specify a device node made a typo in
    # the command, the 'devspec' will contain the misspelled command (e.g., 'integation' instead #
    # of 'integration'). Later on we'll try to open 'itegation', fail and print a misleading error
    # message.
    #
    # So let's try to be a bit smart here and first check if there is a valid command in the command
    # line after the 'devspec' candidate, and if there is one, then we are most probably right about
    # the devspec.
    idx += 1 # pylint: disable=undefined-loop-variable
    for arg in sys.argv[idx+1:]:
        if arg.startswith("-"):
            continue
        if arg in CMDLINE_COMMANDS:
            del sys.argv[idx]
            return devspec

    return None

def main():
    """The program entry point."""

    devspec = fetch_devspec()
    LOG.debug("command-line devspec: %s", devspec)
    args = parse_arguments()

    # Configure the logger.
    info_stream = sys.stdout
    if args.outfile:
        try:
            info_stream = open(args.outfile, "w+")
        except OSError as err:
            raise Error("cannot open the output file '%s':\n%s" % (args.outfile, err))

    Logging.setup_logger(prefix=OWN_NAME, info_stream=info_stream)

    args.devnode = args.secname = None
    if devspec:
        if "/" in devspec or os.path.exists(devspec):
            # This must be the device node path.
            args.devnode = devspec
            LOG.debug("command-line device node: %s", devspec)
        else:
            # This must be section name in the configuration file.
            args.secname = devspec
            LOG.debug("command-line configuration section name: %s", devspec)

    try:
        config = Config.parse_config_files(secname=args.secname, overrides=args)
    except ErrorDeviceNotFound as err:
        raise Error("no power meter configured for node '%s'" % args.secname) from err

    if not config.get("devnode"):
        msg = f"the power meter device node name was not found.\n\nHint: use one of the three "\
              f"methods of specifying the device.\n1. device node name as the first argument.\n" \
              f"2. configuration file section name as the first argument.\n3. just add the " \
              f"'[default]' section to {OWN_NAME} configuration file.\nRefer to the man page for " \
              f"more details."
        raise Error(msg)

    if not config.get("pmtype"):
        # Auto-detection is not 100% reliable, so print a warning.
        LOG.warning("power meter type was not specified, trying to auto-detect it")

    transport = Transport.Transport(**config)

    try:
        pmeter = PowerMeter.PowerMeter(transport=transport, **config)
    except TransportError as err:
        if transport.name != "serial":
            LOG.error_out(err)
        # In case of serial we want to be extra helpful.
        msg = "Here are few seral interface troubleshooting hints.\n" \
              "1. You must use a Null modem cable.\n" \
              "2. You used baud rate %d, your power meter must be configured to %d too.\n" \
              "3. Other serial interface settings on the power meter:\n" \
              "   A. 1 start bit, 8 data bits, no parity\n" \
              "   B. handshaking disabled\n" \
              "   C. terminator is 'Cr+Lf'."
        LOG.error_out("%s\n%s", err, msg)

    if not config.get("pmtype"):
        LOG.warning("detected power meter type '%s': %s", pmeter.pmtype, pmeter.name)

    try:
        args.func(args, pmeter)
    except Error as err:
        LOG.error_out(err)
    except KeyboardInterrupt:
        LOG.info("Interrupted, exiting")

    return 0

if __name__ == "__main__":
    sys.exit(main())
