# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2006 Lukáš Lalinský <lalinsky@gmail.com>
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
from PyQt4 import QtCore, QtGui
from bzrlib import (
    errors,
    )
from bzrlib.branch import Branch
from bzrlib.osutils import pathjoin
from bzrlib.urlutils import local_path_from_url
from bzrlib.plugins.qbzr.i18n import gettext
from bzrlib.plugins.qbzr.util import (
    BTN_CLOSE,
    QBzrWindow,
    format_timestamp,
    get_qlog_replace,
    )
from bzrlib.plugins.qbzr.log import LogWindow
from bzrlib.revisionspec import RevisionSpec


class FileTreeWidget(QtGui.QTreeWidget):

    def __init__(self, window, *args):
        QtGui.QTreeWidget.__init__(self, *args)
        self.window = window

    def contextMenuEvent(self, event):
        self.window.context_menu.popup(event.globalPos())
        event.accept()


class BrowseWindow(QBzrWindow):

    def __init__(self, branch=None, revision=None, revision_id=None,
                 revision_spec=None, parent=None):
        self.branch = branch
        self.location = local_path_from_url(branch.base)
        QBzrWindow.__init__(self,
            [gettext("Browse"), self.location], parent)
        self.restoreSize("browse", (780, 580))

        vbox = QtGui.QVBoxLayout(self.centralwidget)

        hbox = QtGui.QHBoxLayout()
        hbox.addWidget(QtGui.QLabel(gettext("Location:")))
        self.location_edit = QtGui.QLineEdit()
        self.location_edit.setReadOnly(True)
        self.location_edit.setText(self.location)
        hbox.addWidget(self.location_edit, 7)
        hbox.addWidget(QtGui.QLabel(gettext("Revision:")))
        self.revision_edit = QtGui.QLineEdit()
        hbox.addWidget(self.revision_edit, 1)
        self.show_button = QtGui.QPushButton(gettext("Show"))
        self.connect(self.show_button, QtCore.SIGNAL("clicked()"), self.reload_tree)
        hbox.addWidget(self.show_button, 0)
        vbox.addLayout(hbox)

        self.file_tree = FileTreeWidget(self)
        self.file_tree.setHeaderLabels(
            [gettext("Name"), gettext("Date"),
             gettext("Author"), gettext("Message")])

        self.context_menu = QtGui.QMenu(self.file_tree)
        self.context_menu.addAction(gettext("Show log..."), self.show_file_log)

        self.dir_icon = self.style().standardIcon(QtGui.QStyle.SP_DirIcon)
        self.file_icon = self.style().standardIcon(QtGui.QStyle.SP_FileIcon)

        vbox.addWidget(self.file_tree)

        buttonbox = self.create_button_box(BTN_CLOSE)
        vbox.addWidget(buttonbox)

        self.windows = []

        if revision is None:
            if revision_id is None:
                revno, revision_id = self.branch.last_revision_info()
                revision_spec = str(revno)
            self.set_revision(revision_id=revision_id, text=revision_spec)
        else:
            self.set_revision(revspec)

    def load_file_tree(self, entry, parent_item):
        files, dirs = [], []
        revs = set()
        for name, child in entry.sorted_children():
            revs.add(child.revision)
            if child.kind == "directory":
                dirs.append(child)
            else:
                files.append(child)
        for child in dirs:
            item = QtGui.QTreeWidgetItem(parent_item)
            item.setIcon(0, self.dir_icon)
            item.setText(0, child.name)
            revs.update(self.load_file_tree(child, item))
            self.items.append((item, child.revision))
        for child in files:
            item = QtGui.QTreeWidgetItem(parent_item)
            item.setIcon(0, self.file_icon)
            item.setText(0, child.name)
            self.items.append((item, child.revision))
        return revs

    def show_file_log(self):
        """Show qlog for one selected file."""
        # Get selected item.
        item = self.file_tree.currentItem()
        if item == None: return

        # Build full item path.
        path_parts = [unicode(item.text(0))]
        parent = item.parent()
        while parent is not None:
            path_parts.append(unicode(parent.text(0)))
            parent = parent.parent()
        path_parts.append('.')      # IMO with leading ./ path looks better
        path_parts.reverse()
        path = pathjoin(*path_parts)

        branch = self.branch
        file_id = branch.basis_tree().path2id(path)

        window = LogWindow(branch, path, file_id, get_qlog_replace(branch))
        window.show()
        self.windows.append(window)

    def set_revision(self, revspec=None, revision_id=None, text=None):
        branch = self.branch
        branch.lock_read()
        try:
            if revision_id is None:
                text = revspec.spec or ''
                if revspec.in_branch == revspec.in_history:
                    args = [branch]
                else:
                    args = [branch, False]
                try:
                    revision_id = revspec.in_branch(*args).rev_id
                except errors.InvalidRevisionSpec, e:
                    QtGui.QMessageBox.warning(self,
                        "QBzr - " + gettext("Commit"), str(e),
                        QtGui.QMessageBox.Ok)
                    return
            self.items = []
            self.file_tree.invisibleRootItem().takeChildren()
            tree = branch.repository.revision_tree(revision_id)
            root_file_id = tree.path2id('.')
            if root_file_id is not None:
                revs = self.load_file_tree(tree.inventory[root_file_id],
                                           self.file_tree)
                revs = dict(zip(revs, branch.repository.get_revisions(list(revs))))
            else:
                revs = {}
        finally:
            branch.unlock()
        self.revision_edit.setText(text)
        for item, revision_id in self.items:
            rev = revs[revision_id]
            item.setText(1, format_timestamp(rev.timestamp))
            item.setText(2, rev.committer)
            item.setText(3, rev.get_summary())

    def reload_tree(self):
        revspec = RevisionSpec.from_string(unicode(self.revision_edit.text()))
        self.set_revision(revspec)


def get_diff_trees(tree1, tree2, **kwargs):
    """Return unified diff between two trees as a string."""
    from bzrlib.diff import show_diff_trees
    output = StringIO()
    show_diff_trees(tree1, tree2, output, **kwargs)
    # XXX more complicated encoding support needed
    return output.getvalue().decode("UTF-8", "replace")
