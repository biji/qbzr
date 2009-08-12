# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2009 Alexander Belchenko
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

"""Tests for commit data object and operations."""

from bzrlib.tests import TestCase
from bzrlib.plugins.qbzr.lib.commit_data import (
    CommitData,
    )


class TestCommitDataBase(TestCase):

    def test_empty(self):
        d = CommitData()
        self.assertFalse(bool(d))
        self.assertEqual(None, d['message'])
        self.assertEqual({}, d.as_dict())
