<!--
Copyright (c) 2013-2018 Intel, Inc.
SPDX-License-Identifier: GPL-2.0-only

-*- coding: utf-8 -*-
vim: ts=4 sw=4 tw=100 et ai si

Author: Artem Bityutskiy <artem.bityutskiy@linux.intel.com>
-->
- [Introduction](#introduction)
- [Authors](#authors)
- [What is supported](#what-is-supported)
- [Tested configuration](#tested-configuration)
- [Installation](#installation)
  - [Dependencies](#dependencies)
  - [Installing from sources](#installing-from-sources)
- [Preparing power meters](#preparing-power-meters)
  - [WT310](#wt310)
  - [WT210](#wt210)
  - [Connection types](#connection-types)
    - [USB](#usb)
      - [udev](#udev)
    - [Serial](#serial)
- [Usage](#usage)
  - [Contextual help](#contextual-help)
  - [yokotool.conf](#yokotoolconf)
  - [Reading data](#reading-data)
    - [Running a command](#running-a-command)
  - [Power meter properties](#power-meter-properties)
- [Tests](#tests)
- [Tab completions](#tab-completions)

# Introduction

Yokotool is a command-line tool for controlling Yokogawa power meters in Linux.
The tool is written in Python and works with both Python 2.7 and Python 3. The
tool comes with the "yokolibs.PowerMeter" module which can be used from Python scripts.

Project web page: [https://01.org/yoko-tool](https://01.org/yoko-tool).

# Authors

* Artem Bityutskiy <dedekind1@gmail.com> - original author, project maintainer.
* Helia Correia <hcopro@gmail.com>  - project maintainer.

# What is supported

Today the WT210 and WT310 power meters are supported, and WT320/WT330 are partially supported.

WT320/WT330 are basically the same as WT310, but they include 2 or 3 measurement elements.
Yokotool supports only one element (the default one), and it does not include the option of
selecting the element.

Today only the USB and Serial (RS-234) communication interfaces are supported. GPIB is not supported
because Linux generally lacks GPIB drivers. The Ethernet interface is not supported because the
authors do not have a power meter with this communication interface.

# Tested configuration

This project comes with a test suite and tests passed with no errors on the following hardware
configurations:

* WT310E over USB and Serial
* WT313E over USB (element 0 only)
* WT210 over Serial

# Installation

## Dependencies

The only yokotool dependency is the `pyserial` python package, which is only required if your power
meter is using the serial interface. If you are using USB, then you do not have to install it.

If you install yokotool using `pip`, the dependencies will be automatically installed.
Otherwise the dependencies can be installed from the OS packages. For example, in Fedora:

```
dnf install pyserial
```

In Ubuntu:

```
apt-get install python-serial
```

## Installing from sources

First of all, you do not have to install yokotool if you want to use it from sources, just run
'`yokotool`' executable file from the cloned repository directory. This may be convenient for a
quick experiment, but not very convenient for long-term usage.

To install yokotool from sources you need the `pip` tool installed on your system. Here is how to
install 'pip' in Fedora and Ubuntu:

```
dnf install python-pip     # Fedroa
apt-get install python-pip # Ubuntu
```

Then clone `yoko-tool` and checkout the branch or git revision you want to install. If you want
the latest release, checkout the latest release tag. If you want the latest code-base, use the
`master` branch, and for the latest development code-base, use the `devel` branch. Then run:

```
pip install --user /path/to/cloned/yoko-tool
```

This does not require `root` privileges and everything will be installed to your home directory. But
this command may require network access in order to pull the dependencies, unless they are already
installed in your system.

If you want to install system-wide, run without the `--user` option. To uninstall, run

```
pip uninstall yoko-tool
```

And of course you can install yokotool into a python virtual environment as well.

# Preparing power meters

## WT310

Yokogawa WT310 should work without any additional configuration efforts.

## WT210

Yokogawa WT210 has several operation modes, and yokotool only supports the "488.2" mode, which
defines the protocol used by the power meter when talking to the controlling host over the Serial
line. You have to select the 488.2 mode by using power meter buttons. The relevant menu appears when
you press the "local" key. See the detailed instructions at page 11-5 of "WT210/WT230 Digital Power
Meter User's Manual".

## Connection types

### USB

USB is the easiest type of connection to use. The power meter exposes itself to Linux via USB as a
TMC device, and Linux has a standard `usbtmc` driver to talk to TMC devices. Once you plug your
power meter and switch it on, a new `/dev/usbtmcX` device node gets created, for example:

```
$ ls -l /dev/*tmc*
crw-------. 1 root root 180, 176 Feb 20 15:22 /dev/usbtmc0
```

Use this device node to control the power meter (see the [yokotool.conf](#yokotoolconf) section to
learn how).

#### udev

If you have many power meters attached to a single Linux host, then the device node names will be
changing depending on the order you plugged or switched the power meters on. You can solve this
problem with udev rules. Here is an example of a udev rule that adds a handy `/dev/pmeter` symlink
for the /dev/usbtmc0 power meter and grants user `john` and group `john` the ownership.

```
$ cat /etc/udev/rules.d/70-yokogawa-pmeter.rules
ATTRS{idVendor}=="0b21", ATTRS{idProduct}=="0025", ATTRS{serial}=="4333544C303830313745", \
SYMLINK:="pmeter", MODE:="0660", OWNER:="john", GROUP:="john"
```

Make sure to use your device serial number (`ATTRS{serial}=`), you can find it in `dmesg`. Also
use your user and group names. And remember to re-trigger udev events:

```
$  udevadm trigger /dev/usbtmc0
```

### Serial

Serial interface requires the device and the host system to agree on data format and the baud rate.
This must be done manually. By default yokotool assumes the following serial port settings (WT310
defaults as well):

* Baud rate: 9600
* Data format: 1 start bit, 8 data bits, no parity, one stop bit (aka 8n1)
* Handshaking: off
* Terminator: Cr+Lf

You can change baud rate (higher baud rate is recommended), but only the above data format,
handshaking and terminator settings have been tested and are currently supported.

Use the baud rate and the serial device node (e.g., `/dev/ttyS0` or `/dev/ttyUSB0`) to control
the power meter (see the [yokotool.conf](#yokotoolconf) section to learn how).

You must use a Null modem calbe, and it it OK to use USB-serial adapters.

# Usage

For simple usage scenario like reading power meter data you do not really need to know your
power meter that well. However, in order to use the advanced power meter features, you have to read
the manual for your measurement instrument.

## Contextual help

Yokotool's command line interface is based on commands and sub-commands, similar to `git` and many
other tools. Always use `-h` to get contextual help, for example.

```
$ yokotool -h       # Will list all the supported commands and options
$ yokotool read -h  # Will print information about data reading
$ yokotool set -h   # Will print information about the properties that can be changed
```

Note, the help messages are agnostic to the power meter type and only contains general information,
common to all the supported power meter types. In other words, all the `-h` information does not
require you to specify your power meter device node or configure it in `yokotool.conf`.

There are way to get additional help, specific to your power meter type. In order to get it, you
have to either specify the power meter type, device node, and other arguments in command line or in
the `yokotool.conf` file. The former is documented described in the manual page and by `yokotool
-h`, the latter is described in the next section.

## yokotool.conf

In order for yokotool to control your power meter you have to specify power meter type, the device
node and the baud rate. You can do it from command line, for example

```
$ yokotool /dev/ttyUSB0 --pmtype wt210 --baudrate=9600 info
```

will print information about the WT210 power meter which is configured to use baud rate 9600 and
represented by the `/dev/ttyUSB0` device node.

However, it is very inconvenient to provide all these details every time you run yokotool, and this
is where `yokotool.conf` comes handy.

Just like many standard Unix tools yokotool has the global and local configuration files. The former
defines the default or common options. The latter is defines user specific options and can extend or
override the global configuration. Both files are optional.

For yokotool the files are:

* Global: `/etc/yokotool.conf`
* Local: `$HOME/.yokotool.conf`

Here is
[the example configuration file](https://github.com/intel/yoko-tool/blob/devel/yokotool.conf)
along with commentaries.

In a simple case when you have only one power meter, all you need to do is to create the "default"
section and specify the power meter type, the device node name, and possibly the baud rate there,
something like this:

```
[default]
devnode=/dev/ttyUSB0
baudrate=9600
pmtype=wt210
```

The rest of the examples in this document assume you have the default configuration similar to this.

## Reading data

Here is how you can read power, voltage, and the current, along with the time-stamp.

```
$ yokotool read T,P,V,I
T,P,V,I
1521194105.8, 15.4, 231.96, 0.12532
1521194106.8, 15.4, 232.01, 0.12519
1521194107.8, 15.4, 231.94, 0.12517
1521194108.8, 15.39, 231.89, 0.12553
```

Reading will continue until you interrupt it with `Ctrl-C`. You can limit data readings by time or
samples count using the `--time` or `--count` options. You can also redirect the output to a file
using the `-o` option. For example, the below command tells yokotool to read the data for 10 minutes
and save them in the `data.csv` file.

```
$ yokotool read T,P,V,I -o data.csv --time 10m
```

Yokotool uses the CSV format for data output. You can adjust it with the `--no-header` and
`--no-align` options. Please, check `yokotool read -h` for more information.

Please, run the following command in order to get the list data item types the power meter can
provide.

```
$ yokotool read
Use the following data items:
V - voltage
I - current
P - active power
S - apparent power
Q - reactive power
Lambda - power factor (λ)
...
```

### Running a command

You can ask yokotool to run a program and measure power while it is running, for example:

```
$ yokotool read T,P,V,I -o data.csv -c my_program
```

Here is an example when this feature may be useful. Suppose you have the control host - a Linux
computer the controls the power meter over the communication interface like USB. This is the host
where you run yokotool. And you also have the `testbox` host - another computer which is measured by
your power meter. If you can login from the control host to the `testbox` with SSH, you can also
do something like this:

```
$ yokotool read T,P,V,I -o data.csv -c ssh testbox workload
```

This command will run "workload" on `testbox`, measure `testbox`'s power consumption and save
measurement results in the `data.csv` file of the control host.

## Power meter properties

Power meter has lots of settings and tunables that you can toggle using yokotool, and they are
referred to as "properties". You can read the value of a property with `yokotool get` and change the
value with `yokotool set`. For example, the data update interval and the current range are the
properties. Here is how you read them.

```
$ yokotool get interval
1
$ yokotool get current-range
0.2
```

You can use `yokotool get interval -h` and `yokotool get current-range -h` for some more help.

Let's change the update interval and the current range. First of all, here is how you get the list
of possible values.

```
$ yokotool set interval
Use:
0.1, 0.25, 0.5, 1, 2, 5
$ yokotool set current-range
Use:
auto, 0.0025, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20
```

To change the update interval to 0.1s and current range to "auto" (means that power meter will
automatically select the current range), use:

```
$ yokotool set interval 0.1
$ yokotool set current-range auto
```

And finally, here is ho you get full list of properties that can be gotten or set:

```
$ yokotool get --list
$ yokotool set --list
```

# Tests

This project comes with a test suite. The test suite uses the `pytest` Python test framework which
must be installed in order to run the test. The test require one or multiple configured power meters.

For example, if you have two power meters describe as "wt210-serial" and "wt310-usb" in
`yokotool.conf`, you can run the tests with this command:

```
python -m pytest --devspec wt210-serial --devspec wt310-usb
```

If you see an issue and want to report a bug, add the ```--loglevel=debug```, collect the output and
include to the bug report.

# Tab completions

Yokotool supports tab completions, but they will only work if you installed yokotool with
`pip`. Completions will not work if you use yokotool directly from the source codes.

Yokotool tab completions are based on the `argcomplete` Python module. You can install
it using `pip` or by installing the corresponding OS package.  In Fedora, use:

```
$ dnf install python-argcomplete  # Python 2.7
$ dnf install python3-argcomplete # Python 3.x
```

In Ubuntu, use:

```
$ apt-get install python-argcomplete  # Python 2.7
$ apt-get install python3-argcomplete # Python 3.x
```

Once you have `argcomplete` installed in your system, run

```
eval "$(register-python-argcomplete yokotool)"
```

and verify that tab completions work. Add this command to your `.bashrc` to have yokotool tab
completions enabled by default.
