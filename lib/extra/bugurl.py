# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2008 Lukáš Lalinský <lalinsky@gmail.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

import sys
if hasattr(sys, "frozen"):
    # "hack in" our PyQt4 binaries
    import os
    sys.path.append(os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', '_lib')))

from bzrlib import commands, errors, trace, bugtracker
from bzrlib.config import GlobalConfig
from bzrlib.branch import Branch
from bzrlib.option import Option
from bzrlib.plugins.qbzr.lib.util import open_browser, url_for_display


class FakeBranch(object):

    def __init__(self):
        self._config = GlobalConfig()

    def get_config(self):
        return self._config


class cmd_bug_url(commands.Command):
    """Print full URL to a specific bug, or open it in your browser."""

    takes_args = ['bug_id']
    takes_options = [
        Option('open', help='Open the URL in a web browser.'),
    ]

    def run(self, bug_id, open=False):
        try:
            branch = Branch.open_containing(u'.')[0]
        except errors.NotBranchError:
            branch = FakeBranch()
        tokens = bug_id.split(':')
        if len(tokens) != 2:
            raise errors.BzrCommandError(
                "Invalid bug %s. Must be in the form of 'tag:id'." % bug_id)
        tag, tag_bug_id = tokens
        try:
            bug_url = bugtracker.get_bug_url(tag, branch, tag_bug_id)
        except errors.UnknownBugTrackerAbbreviation:
            raise errors.BzrCommandError(
                'Unrecognized bug %s.' % bug_id)
        except errors.MalformedBugIdentifier:
            raise errors.BzrCommandError(
                "Invalid bug identifier for %s." % bug_id)
        self.outf.write(url_for_display(bug_url) + "\n")
        if open:
            open_browser(bug_url)
