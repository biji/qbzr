# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2006 Lukáš Lalinský <lalinsky@gmail.com>
# Portions Copyright (C) 2006 Jelmer Vernooij <jelmer@samba.org>
# Portions Copyright (C) 2005 Canonical Ltd. (author: Scott James Remnant <scott@ubuntu.com>)
# Portions Copyright (C) 2004-2006 Christopher Lenz <cmlenz@gmx.de>
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

import locale
import sys
import time
from cStringIO import StringIO

from PyQt4 import QtCore, QtGui

from bzrlib.errors import BinaryFile, NoSuchId
from bzrlib.textfile import check_text_lines
from bzrlib.config import GlobalConfig
from bzrlib.diff import show_diff_trees
from bzrlib.workingtree import WorkingTree
from bzrlib.patiencediff import PatienceSequenceMatcher as SequenceMatcher

from bzrlib.plugins.qbzr.lib.diffview import (
    DiffView,
    SimpleDiffView,
    populate_diff_documents,
    )
from bzrlib.plugins.qbzr.lib.i18n import gettext, ngettext, N_
from bzrlib.plugins.qbzr.lib.util import (
    BTN_CLOSE,
    FilterOptions,
    QBzrWindow,
    format_timestamp,
    get_branch_config,
    get_set_encoding,
    )


def get_file_lines_from_tree(tree, file_id):
    try:
        return tree.get_file_lines(file_id)
    except AttributeError:
        return tree.get_file(file_id).readlines()


class FileDiff(object):

    def __init__(self, status, path):
        self.status = status
        self.path = path
        self.binary = False
        self.old_lines = []
        self.new_lines = []
        self.groups = []

    def make_diff(self, old_lines, new_lines, complete, encoding='utf-8'):
        try:
            check_text_lines(old_lines)
            check_text_lines(new_lines)
        except BinaryFile:
            self.binary = True
            self.old_data = ''.join(old_lines)
            self.new_data = ''.join(new_lines)
        else:
            self.old_lines = old_lines
            self.new_lines = new_lines
            if old_lines and not new_lines:
                self.groups = [[('delete', 0, len(old_lines), 0, 0)]]
            elif not old_lines and new_lines:
                self.groups = [[('insert', 0, 0, 0, len(new_lines))]]
            else:
                matcher = SequenceMatcher(None, old_lines, new_lines)
                if complete:
                    self.groups = list([matcher.get_opcodes()])
                else:
                    self.groups = list(matcher.get_grouped_opcodes())
            self.old_lines = [i.decode(encoding,'replace') for i in old_lines]
            self.new_lines = [i.decode(encoding,'replace') for i in new_lines]


class TreeDiff(list):

    def _date(self, tree, file_id, path, secs=None):
        if secs is None:
            try:
                secs = tree.get_file_mtime(file_id, path)
            except (NoSuchId, OSError):
                secs = 0
        return format_timestamp(secs)

    def _make_diff(self, specific_files=[], complete=False,
                   encoding='utf-8', filter_options=None):
        if filter_options == None:
            filter_options = FilterOptions()
            filter_options.all_enable()
        delta = self.new_tree.changes_from(self.old_tree,
                                           specific_files=specific_files,
                                           require_versioned=True)

        delta_removed = []
        delta_added = []
        delta_renamed = []
        delta_modified = []
        if filter_options.deleted:
            delta_removed = delta.removed
        if filter_options.added:
            delta_added = delta.added
        if filter_options.renamed or filter_options.modified:
            delta_renamed = delta.renamed
        if filter_options.modified:
            delta_modified = delta.modified

        for path, file_id, kind in delta_removed:
            diff = FileDiff(N_('removed'), path)
            diff.kind = kind
            diff.old_date = self._date(self.old_tree, file_id, path)
            diff.new_date = self._date(self.new_tree, file_id, path)
            diff.file_id = file_id
            diff.old_path = path
            diff.new_path = path
            if diff.kind != 'directory':
                diff.make_diff(get_file_lines_from_tree(self.old_tree, file_id),
                               [], complete, encoding)
            self.append(diff)

        for path, file_id, kind in delta_added:
            diff = FileDiff(N_('added'), path)
            diff.kind = kind
            diff.old_date = self._date(self.old_tree, file_id, path, 0)
            diff.new_date = self._date(self.new_tree, file_id, path)
            diff.file_id = file_id
            diff.old_path = path
            diff.new_path = path
            if diff.kind != 'directory':
                diff.make_diff([], get_file_lines_from_tree(self.new_tree, file_id),
                               complete, encoding)
            self.append(diff)

        for (old_path, new_path, file_id, kind, text_modified, meta_modified
            ) in delta_renamed:
            if text_modified:
                status = N_('renamed and modified')
            else:
                if not filter_options.renamed:
                    continue
                status = N_('renamed')
            diff = FileDiff(status, u'%s \u2192 %s' % (old_path, new_path))
            diff.kind = kind
            diff.old_date = self._date(self.old_tree, file_id, old_path)
            diff.new_date = self._date(self.new_tree, file_id, new_path)
            diff.file_id = file_id
            diff.old_path = old_path
            diff.new_path = new_path
            if text_modified:
                old_lines = get_file_lines_from_tree(self.old_tree, file_id)
                new_lines = get_file_lines_from_tree(self.new_tree, file_id)
                diff.make_diff(old_lines, new_lines, complete, encoding)
            self.append(diff)

        for (path, file_id, kind, text_modified, meta_modified
            ) in delta_modified:
            diff = FileDiff(N_('modified'), path)
            diff.kind = kind
            # the path for this file might be changed by a directory rename, so
            # let it to use just the file_id
            diff.old_date = self._date(self.old_tree, file_id, None)
            diff.new_date = self._date(self.new_tree, file_id, path)
            diff.file_id = file_id
            diff.old_path = path
            diff.new_path = path
            if text_modified:
                old_lines = get_file_lines_from_tree(self.old_tree, file_id)
                new_lines = get_file_lines_from_tree(self.new_tree, file_id)
                diff.make_diff(old_lines, new_lines, complete, encoding)
            self.append(diff)

    def __init__(self, old_tree, new_tree, specific_files=[], complete=False,
                 encoding='utf-8', filter_options=None):
        self._metainfo_template = None
        self.old_tree = old_tree
        self.new_tree = new_tree
        self.old_tree.lock_read()
        self.new_tree.lock_read()
        try:
            self._make_diff(specific_files, complete,
                            encoding, filter_options)
        finally:
            self.old_tree.unlock()
            self.new_tree.unlock()

    def html_unidiff(self):
        res = []
        for diff in self:
            res.append(diff.html_unidiff())
        return ''.join(res)


class DiffWindow(QBzrWindow):

    def __init__(self, tree1=None, tree2=None, specific_files=None,
                 parent=None, custom_title=None,
                 complete=False, branch=None, encoding=None,
                 filter_options=None):
        title = [gettext("Diff")]
        if custom_title:
            title.append(custom_title)
        if specific_files:
            nfiles = len(specific_files)
            if nfiles > 2:
                title.append(
                    ngettext("%d file", "%d files", nfiles) % nfiles)
            else:
                title.append(", ".join(specific_files))
        else:
            if filter_options and not filter_options.is_all_enable():
                title.append(filter_options.to_str())

        config = get_branch_config(branch)
        encoding = get_set_encoding(encoding, config)

        QBzrWindow.__init__(self, title, parent)
        self.restoreSize("diff", (780, 580))

        self.tree1 = tree1
        self.tree2 = tree2
        self.specific_files = specific_files

        treediff = TreeDiff(self.tree1, self.tree2, self.specific_files,
                            complete, encoding, filter_options)
        self.diffview = DiffView(treediff, self)

        self.sdiffview = SimpleDiffView(treediff, self)
        self.sdiffview.setVisible(False)

        populate_diff_documents(self.font(), treediff,
                                self.diffview, self.sdiffview)

        self.diffview.rewind()
        self.sdiffview.rewind()

        self.stack = QtGui.QStackedWidget(self.centralwidget)
        self.stack.addWidget(self.diffview)
        self.stack.addWidget(self.sdiffview)

        vbox = QtGui.QVBoxLayout(self.centralwidget)
        vbox.addWidget(self.stack)

        diffsidebyside = QtGui.QRadioButton(gettext("Side by side"),
                                            self.centralwidget)
        self.connect(diffsidebyside,
                     QtCore.SIGNAL("clicked(bool)"),
                     self.click_diffsidebyside)
        diffsidebyside.setChecked(True);

        unidiff = QtGui.QRadioButton(gettext("Unidiff"), self.centralwidget)
        self.connect(unidiff,
                     QtCore.SIGNAL("clicked(bool)"),
                     self.click_unidiff)

        buttonbox = self.create_button_box(BTN_CLOSE)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(diffsidebyside)
        hbox.addWidget(unidiff)
        hbox.addWidget(buttonbox)
        vbox.addLayout(hbox)

    def click_unidiff(self, checked):
        if checked:
            self.stack.setCurrentIndex(1)

    def click_diffsidebyside(self, checked):
        if checked:
            self.stack.setCurrentIndex(0)
