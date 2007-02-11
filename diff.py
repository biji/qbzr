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
from bzrlib.commands import Command, register_command
from bzrlib.diff import show_diff_trees
from bzrlib.workingtree import WorkingTree
from bzrlib.plugins.qbzr.util import QBzrWindow
from bzrlib.patiencediff import PatienceSequenceMatcher as SequenceMatcher


STYLES = {
    'hunk': 'background-color:#666666;color:#FFF;font-weight:bold;',
    'delete': 'background-color:#FFDDDD',
    'insert': 'background-color:#DDFFDD',
    'missing': 'background-color:#E0E0E0',
    'title': 'margin-top: 10px; font-size: 14px; font-weight: bold;',
    'metainfo': 'font-size: 9px; margin-bottom: 10px;',
}


def get_file_lines_from_tree(tree, file_id):
    try:
        return tree.get_file_lines(file_id)
    except AttributeError:
        return tree.get_file(file_id).readlines()


def get_change_extent(str1, str2):
    start = 0
    limit = min(len(str1), len(str2))
    while start < limit and str1[start] == str2[start]:
        start += 1
    end = -1
    limit = limit - start
    while -end <= limit and str1[end] == str2[end]:
        end -= 1
    return (start, end + 1)


def markup_intraline_changes(line1, line2, color):
    line1 = line1.replace("&", "\1").replace("<", "\2").replace(">", "\3")
    line2 = line2.replace("&", "\1").replace("<", "\2").replace(">", "\3")
    start, end = get_change_extent(line1[1:], line2[1:])
    if start == 0 and end < 0:
        text = '<span style="background-color:%s">%s</span>%s' % (color, line1[:end], line1[end:])
    elif start > 0 and end == 0:
        start += 1
        text = '%s<span style="background-color:%s">%s</span>' % (line1[:start], color, line1[start:])
    elif start > 0 and end < 0:
        start += 1
        text = '%s<span style="background-color:%s">%s</span>%s' % (line1[:start], color, line1[start:end], line1[end:])
    else:
        text = line1
    text = text.replace("\1", "&amp;").replace("\2", "&lt;").replace("\3", "&gt;")
    return text


def htmlencode(string):
    return string.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markup_line(line, style='', encode=True):
    if encode:
        line = htmlencode(line)
    if style:
        style = ' style="%s"' % style
    return '<div%s>%s</div>' % (style, line.rstrip() or '&nbsp;')


class FileDiff(object):

    def __init__(self, status, path):
        self.status = status
        self.path = path
        self.binary = False
        self.old_lines = []
        self.new_lines = []
        self.groups = []

    def make_diff(self, old_lines, new_lines, complete):
        try:
            check_text_lines(old_lines)
            check_text_lines(new_lines)
        except BinaryFile:
            self.binary = True
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
                    self.groups = [matcher.get_opcodes()]
                else:
                    self.groups = matcher.get_grouped_opcodes()

    def html_diff_lines(self, html1, html2, inline=True):
        a = self.old_lines
        b = self.new_lines
        groups = self.groups
        a = [a.decode("utf-8", "replace").rstrip("\n") for a in a]
        b = [b.decode("utf-8", "replace").rstrip("\n") for b in b]
        for group in groups:
            i1, i2, j1, j2 = group[0][1], group[-1][2], group[0][3], group[-1][4]
            hunk = "@@ -%d,%d +%d,%d @@" % (i1+1, i2-i1, j1+1, j2-j1)
            html1.append('<div style="%s">%s</div>' % (STYLES['hunk'], htmlencode(hunk)))
            if not inline:
                html2.append('<div style="%s">%s</div>' % (STYLES['hunk'], htmlencode(hunk)))
            for tag, i1, i2, j1, j2 in group:
                if tag == 'equal':
                    for line in a[i1:i2]:
                        line = markup_line(line)
                        html1.append(line)
                        if not inline:
                            html2.append(line)
                elif tag == 'replace':
                    d = (i2 - i1) - (j2 - j1)
                    if d == 0:
                        for i in range(i2 - i1):
                            linea = a[i1 + i]
                            lineb = b[j1 + i]
                            linea = markup_intraline_changes(linea, lineb, '#EE9999')
                            lineb = markup_intraline_changes(lineb, linea, '#99EE99')
                            html1.append(markup_line(linea, STYLES['delete'], encode=False))
                            html2.append(markup_line(lineb, STYLES['insert'], encode=False))
                    else:
                        for line in a[i1:i2]:
                            html1.append(markup_line(line, STYLES['delete']))
                        for line in b[j1:j2]:
                            html2.append(markup_line(line, STYLES['insert']))
                        if not inline:
                            if d < 0:
                                for i in range(-d):
                                    html1.append(markup_line('', STYLES['missing']))
                            else:
                                for i in range(d):
                                    html2.append(markup_line('', STYLES['missing']))
                elif tag == 'insert':
                    for line in b[j1:j2]:
                        if not inline:
                            html1.append(markup_line('', STYLES['missing']))
                        html2.append(markup_line(line, STYLES['insert']))
                elif tag == 'delete':
                    for line in a[i1:i2]:
                        html1.append(markup_line(line, STYLES['delete']))
                        if not inline:
                            html2.append(markup_line('', STYLES['missing']))
        html1.append('</pre>')
        html2.append('</pre>')

    def html_side_by_side(self):
        """Make HTML for side-by-side diff view."""
        if self.binary:
            line = '<p>[binary file]</p>'
            return line, line
        else:
            lines1 = []
            lines2 = []
            self.html_diff_lines(lines1, lines2, inline=False)
            return '<pre>%s</pre>' % ''.join(lines1), '<pre>%s</pre>' % ''.join(lines2)

    def html_inline(self):
        """Make HTML for in-line diff view."""
        if self.binary:
            line = '<p>[binary file]</p>'
            return line, line
        else:
            lines = []
            self.html_diff_lines(lines, lines, inline=True)
            return '<pre>%s</pre>' % ''.join(lines)


class TreeDiff(list):

    def _date(self, tree, file_id, path, secs=None):
        if secs is None:
            try:
                secs = tree.get_file_mtime(file_id, path)
            except NoSuchId:
                secs = 0
        tm = time.localtime(secs)
        return time.strftime('%c', tm).decode(locale.getpreferredencoding())

    def __init__(self, old_tree, new_tree, specific_files=[], complete=False):
        delta = new_tree.changes_from(old_tree, specific_files=specific_files, require_versioned=True)

        for path, file_id, kind in delta.removed:
            diff = FileDiff('removed', path)
            diff.kind = kind
            diff.old_date = self._date(old_tree, file_id, path)
            diff.new_date = self._date(new_tree, file_id, path)
            if diff.kind != 'directory':
                diff.make_diff(get_file_lines_from_tree(old_tree, file_id), [], complete)
            self.append(diff)

        for path, file_id, kind in delta.added:
            diff = FileDiff('added', path)
            diff.kind = kind
            diff.old_date = self._date(old_tree, file_id, path, 0)
            diff.new_date = self._date(new_tree, file_id, path)
            if diff.kind != 'directory':
                diff.make_diff([], get_file_lines_from_tree(new_tree, file_id), complete)
            self.append(diff)

        for old_path, new_path, file_id, kind, text_modified, meta_modified in delta.renamed:
            diff = FileDiff('renamed', u'%s \u2192 %s' % (old_path, new_path))
            diff.kind = kind
            diff.old_date = self._date(old_tree, file_id, old_path)
            diff.new_date = self._date(new_tree, file_id, new_path)
            if text_modified:
                old_lines = get_file_lines_from_tree(old_tree, file_id)
                new_lines = get_file_lines_from_tree(new_tree, file_id)
                diff.make_diff(old_lines, new_lines, complete)
            self.append(diff)

        for path, file_id, kind, text_modified, meta_modified in delta.modified:
            diff = FileDiff('modified', path)
            diff.kind = kind
            diff.old_date = self._date(old_tree, file_id, path)
            diff.new_date = self._date(new_tree, file_id, path)
            if text_modified:
                old_lines = get_file_lines_from_tree(old_tree, file_id)
                new_lines = get_file_lines_from_tree(new_tree, file_id)
                diff.make_diff(old_lines, new_lines, complete)
            self.append(diff)

    def html_inline(self):
        html = []
        for diff in self:
            html.append('<div style="%s">%s</div>' % (STYLES['title'], diff.path))
            html.append('<div style="%s"><small><b>Last modified:</b> %s, <b>Status:</b> %s, <b>Kind:</b> %s</small></div>' % (STYLES['metainfo'], diff.old_date, diff.status, diff.kind))
            html.append(diff.html_inline())
        return ''.join(html)

    def html_side_by_side(self):
        html1 = []
        html2 = []
        for diff in self:
            html1.append('<div style="%s">%s</div>' % (STYLES['title'], diff.path))
            html1.append('<div style="%s"><small><b>Last modified:</b> %s, <b>Status:</b> %s, <b>Kind:</b> %s</small></div>' % (STYLES['metainfo'], diff.old_date, diff.status, diff.kind))
            html2.append('<div style="%s">%s</div>' % (STYLES['title'], diff.path))
            html2.append('<div style="%s"><small><b>Last modified:</b> %s, <b>Status:</b> %s, <b>Kind:</b> %s</small></div>' % (STYLES['metainfo'], diff.new_date, diff.status, diff.kind))
            lines1, lines2 = diff.html_side_by_side()
            html1.append(lines1)
            html2.append(lines2)
        return ''.join(html1), ''.join(html2)


class DiffWindow(QBzrWindow):

    def __init__(self, tree1=None, tree2=None, specific_files=None,
                 parent=None, custom_title=None, inline=False,
                 complete=False):
        title = ["Diff"]
        if custom_title:
            title.append(custom_title)
        if specific_files:
            if len(specific_files) > 2:
                title.append("%s files" % len(specific_files))
            else:
                title.append(", ".join(specific_files))

        size = (780, 580)
        try:
            branch = None
            if hasattr(tree1, '_branch'):
                branch = tree1._branch
            elif hasattr(tree2, '_branch'):
                branch = tree2._branch
            if branch:
                config = branch.get_config()
                size_str = config.get_user_option("qdiff_window_size")
                if size_str:
                    size = map(int, size_str.split("x"))
        except:
            pass

        QBzrWindow.__init__(self, title, size, parent)

        self.tree1 = tree1
        self.tree2 = tree2
        self.specific_files = specific_files

        treediff = TreeDiff(self.tree1, self.tree2, self.specific_files, complete)

        hbox = QtGui.QHBoxLayout()
        if inline:
            self.doc = QtGui.QTextDocument()
            self.doc.setHtml(treediff.html_inline())
            self.browser = QtGui.QTextBrowser()
            self.browser.setDocument(self.doc)
            hbox.addWidget(self.browser)
        else:
            html1, html2 = treediff.html_side_by_side()
            self.doc1 = QtGui.QTextDocument()
            self.doc1.setHtml(html1)
            self.doc2 = QtGui.QTextDocument()
            self.doc2.setHtml(html2)
            self.browser1 = QtGui.QTextBrowser()
            self.browser1.setDocument(self.doc1)
            self.browser1.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.browser2 = QtGui.QTextBrowser()
            self.browser2.setDocument(self.doc2)
            self.connect(self.browser1.verticalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.browser2.verticalScrollBar(), QtCore.SLOT("setValue(int)"))
            self.connect(self.browser1.horizontalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.browser2.horizontalScrollBar(), QtCore.SLOT("setValue(int)"))
            self.connect(self.browser2.verticalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.browser1.verticalScrollBar(), QtCore.SLOT("setValue(int)"))
            self.connect(self.browser2.horizontalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.browser1.horizontalScrollBar(), QtCore.SLOT("setValue(int)"))
            hbox.addWidget(self.browser1)
            hbox.addWidget(self.browser2)

        buttonbox = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.StandardButtons(
                QtGui.QDialogButtonBox.Close),
            QtCore.Qt.Horizontal,
            self.centralwidget)
        self.connect(buttonbox, QtCore.SIGNAL("rejected()"), self.close)

        vbox = QtGui.QVBoxLayout(self.centralwidget)
        vbox.addLayout(hbox)
        vbox.addWidget(buttonbox)
