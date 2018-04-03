#!/bin/sh -euf
#
# Copyright (c) 2018 Intel, Inc.
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

# This script automates the process of releasing the yoko-tool project. The
# idea is that it should be enough to run this script with few parameters and
# the release is ready.

#
# This script is supposed to be executed in the root of the yoko-tool
# project's source code tree.

PROG="make_a_release.sh"

fatal() {
        printf "Error: %s\n" "$1" >&2
        exit 1
}

usage() {
        cat <<EOF
Usage: ${0##*/} <new_ver> <outdir>

<new_ver>  - new yoko-tool version to make in X.Y format
EOF
        exit 0
}

ask_question() {
	local question=$1

	while true; do
		printf "%s\n" "$question (yes/no)?"
		IFS= read answer
		if [ "$answer" == "yes" ]; then
			printf "%s\n" "Very good!"
			return
		elif [ "$answer" == "no" ]; then
			printf "%s\n" "Please, do that!"
			exit 1
		else
			printf "%s\n" "Please, answer \"yes\" or \"no\""
		fi
	done
}

format_changelog() {
	local logfile="$1"; shift
	local pfx1="$1"; shift
	local pfx2="$1"; shift
	local pfx_len="$(printf "%s" "$pfx1" | wc -c)"
	local width="$((80-$pfx_len))"

	while IFS= read -r line; do
		printf "%s\n" "$line" | fold -c -s -w "$width" | \
			sed -e "1 s/^/$pfx1/" | sed -e "1! s/^/$pfx2/" | \
			sed -e "s/[\t ]\+$//"
	done < "$logfile"
}

[ $# -eq 0 ] && usage
[ $# -eq 1 ] || fatal "insufficient or too many argumetns"

new_ver="$1"; shift

# Validate the new version
printf "%s" "$new_ver" | egrep -q -x '[[:digit:]]+\.[[:digit:]]+' ||
        fatal "please, provide new version in X.Y format"

# Make sure that the current branch is 'devel'
current_branch="$(git branch | sed -n -e '/^*/ s/^* //p')"
if [ "$current_branch" != "devel" ]; then
	fatal "current branch is '$current_branch' but must be 'devel'"
fi

# Remind the maintainer about various important things
ask_question "Did you run tests"
ask_question "Did you update the docs/RELEASE_NOTES file"
ask_question "Did you update the README.md file"
ask_question "Did you update the man page"
ask_question "Did you update tests"

# Make sure the git index is up-to-date
[ -z "$(git status --porcelain)" ] || fatal "git index is not up-to-date"

# Change the version in the 'yokolibs/yokotool.py' file
sed -i -e "s/^VERSION = \"[0-9]\+\.[0-9]\+\"$/VERSION = \"$new_ver\"/" yokolibs/yokotool.py

# Commit the changes
git commit -a -s -m "Release version $new_ver"

outdir="."
tag_name="v$new_ver"
release_name="yoko-tool-$new_ver"

# Create new signed tag
printf "%s\n" "Signing tag $tag_name"
git tag -m "$release_name" -s "$tag_name"

cat <<EOF
To finish the release:
  1. push the $tag_name tag out
  2. push the devel and master branches out

The commands would be:

git push origin $tag_name
git push origin devel:devel
git push origin master:master
EOF
