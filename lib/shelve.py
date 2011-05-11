# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2011 QBzr Developers
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

import sys, time
from PyQt4 import QtCore, QtGui

from bzrlib.revision import CURRENT_REVISION
from bzrlib.errors import (
        NoSuchRevision, 
        NoSuchRevisionInTree,
        PathsNotVersionedError,
        BinaryFile)
from bzrlib.plugins.qbzr.lib.i18n import gettext, N_
from bzrlib.plugins.qbzr.lib.util import (
    BTN_OK, BTN_CLOSE, BTN_REFRESH,
    get_apparent_author_name,
    get_global_config,
    get_set_encoding,
    runs_in_loading_queue,
    get_icon,
    QBzrDialog,
    ToolBarThrobberWidget,
    get_monospace_font,
    )
from bzrlib.plugins.qbzr.lib.widgets.toolbars import FindToolbar, ToolbarPanel
from bzrlib import errors
from bzrlib.plugins.qbzr.lib.uifactory import ui_current_widget
from bzrlib.plugins.qbzr.lib.trace import reports_exception
from bzrlib.plugins.qbzr.lib.logwidget import LogList
from bzrlib.patches import HunkLine, ContextLine, InsertLine, RemoveLine
from bzrlib.lazy_import import lazy_import
lazy_import(globals(), '''
from bzrlib import transform, textfile, patches
from bzrlib.workingtree import WorkingTree
from bzrlib.revisiontree import RevisionTree
from bzrlib.plugins.qbzr.lib.encoding_selector import EncodingMenuSelector
from bzrlib.plugins.qbzr.lib.commit import TextEdit
from bzrlib.plugins.qbzr.lib.spellcheck import SpellCheckHighlighter, SpellChecker
from bzrlib.patiencediff import PatienceSequenceMatcher as SequenceMatcher
from bzrlib.shelf import ShelfCreator
from bzrlib.shelf_ui import Shelver
''')

"""
TODO::
  Auto complete of shelve message.
  Wordwrap mode
  Side by side view
  External diff (ShelveListWindow)
  Lock management
  Select hunk by Find.
"""

# For i18n
change_status = (
        N_("delete file"), N_("rename"), N_("add file"), 
        N_("modify text"), N_("modify target"), N_("modify binary")
        )

class DummyDiffWriter(object):
    def __init__(self):
        pass
    def write(self, *args, **kwargs):
        pass

class Change(object):
    def __init__(self, change, shelver, trees):
        status = change[0]
        file_id = change[1]
        if status == 'delete file':
            self.disp_text = trees[0].id2path(file_id)
        elif status == 'rename':
            self.disp_text = u'%s => %s' % (trees[0].id2path(file_id), trees[1].id2path(file_id))
        else:
            self.disp_text = trees[1].id2path(file_id)
        if status == 'modify text':
            try:
                self.sha1 = trees[1].get_file_sha1(file_id)
                target_lines = trees[0].get_file_lines(file_id)
                textfile.check_text_lines(target_lines)
                work_lines = trees[1].get_file_lines(file_id)
                textfile.check_text_lines(work_lines)
                
                self._target_lines = [None, target_lines, None]
                self._work_lines = [None, work_lines, None]

                parsed = shelver.get_parsed_patch(file_id, False)
                for hunk in parsed.hunks:
                    hunk.selected = False
                self.parsed_patch = parsed
                self.hunk_texts = [None, None, None]
            except errors.BinaryFile:
                status = 'modify binary'

        self.data = change
        self.file_id = file_id
        self.status = status

    def is_same_change(self, other):
        # NOTE: I does not use __cmp__ because this method does not compare entire data.
        if self.data != other.data:
            return False
        if self.status in ('modify text', 'modify binary'):
            if self.sha1 != other.sha1:
                return False
        return True

    @property
    def target_lines(self):
        """Original file lines"""
        return self._target_lines[1]

    @property
    def work_lines(self):
        """Working file lines"""
        return self._work_lines[1]

    def encode_hunk_texts(self, encoding):
        """
        Return encoded hunk texts.
        hunk texts is nested list. Outer is per hunks, inner is per lines.
        """
        if self.hunk_texts[0] == encoding:
            return self.hunk_texts[2]
        patch = self.parsed_patch
        try:
            texts = [[str(l).decode(encoding) for l in hunk.lines]
                     for hunk in patch.hunks]
        except UnicodeError:
            if self.hunk_texts[1] is None:
                texts = [[str(l) for l in hunk.lines] for hunk in patch.hunks]
                self.hunk_texts[1] = texts
            else:
                texts = self.hunk_texts[1]
        self.hunk_texts[0] = encoding
        self.hunk_texts[2] = texts

        return texts

    def encode(self, lines, encoding):
        if lines[0] == encoding:
            return lines[2]
        try:
            encoded_lines = [l.decode(encoding) for l in lines[1]]
        except UnicodeError:
            encoded_lines = lines[1]
        lines[2] = encoded_lines
        return encoded_lines

    def encode_work_lines(self, encoding):
        """Return encoded working file lines. """
        return self.encode(self._work_lines, encoding)

    def encode_target_lines(self, encoding):
        """Return encoded original file lines."""
        return self.encode(self._target_lines, encoding)


class SelectAllCheckBox(QtGui.QCheckBox):
    def __init__(self, view, parent):
        QtGui.QCheckBox.__init__(self, 
                                 gettext("Select / deselect all"), 
                                 parent)
        self.changed_by_code = False
        self.view = view
        self.connect(self, QtCore.SIGNAL("clicked(bool)"),
                self.clicked)
        self.connect(self.view, QtCore.SIGNAL("itemChanged(QTreeWidgetItem *, int)"),
                self.view_itemchecked)

    def view_itemchecked(self, item, column):
        if self.changed_by_code:
            return
        if column != 0:
            return
        view = self.view
        state = None
        for i in range(view.topLevelItemCount()):
            item = view.topLevelItem(i)
            if state is None:
                state = item.checkState(0)
                if state == QtCore.Qt.PartiallyChecked:
                    break
            elif state != item.checkState(0):
                state = QtCore.Qt.PartiallyChecked
                break
        try:
            self.changed_by_code = True
            self.setCheckState(state)
        finally:
            self.changed_by_code = False

    def clicked(self, state):
        if self.changed_by_code:
            return
        if state:
            state = QtCore.Qt.Checked
        else:
            state = QtCore.Qt.Unchecked

        view = self.view
        self.changed_by_code = True
        try:
            self.setCheckState(state)
            for i in range(view.topLevelItemCount()):
                item = view.topLevelItem(i)
                if item.checkState(0) != state:
                    item.setCheckState(0, state)
        finally:
            self.changed_by_code = False

class ShelveWindow(QBzrDialog):

    def __init__(self, file_list=None, directory=None, complete=False, encoding=None, dialog=True, parent=None, ui_mode=True):
        QBzrDialog.__init__(self,
                            gettext("Shelve"),
                            parent, ui_mode=ui_mode)
        self.restoreSize("shelve", (780, 680))
        self._cleanup_funcs = []

        self.revision = None
        self.file_list = file_list
        self.directory = directory
        self.message = None

        self.encoding = encoding

        self.throbber = ToolBarThrobberWidget(self)

        splitter = QtGui.QSplitter(QtCore.Qt.Vertical, self)
        message_groupbox = QtGui.QGroupBox(gettext("Message"), splitter)
        message_layout = QtGui.QVBoxLayout(message_groupbox)
        splitter.addWidget(message_groupbox)

        language = get_global_config().get_user_option('spellcheck_language') or 'en'
        spell_checker = SpellChecker(language)
        
        self.message = TextEdit(spell_checker, message_groupbox, main_window=self)
        self.message.setToolTip(gettext("Enter the commit message"))
        self.completer = QtGui.QCompleter()
        self.completer_model = QtGui.QStringListModel(self.completer)
        self.completer.setModel(self.completer_model)
        self.message.setCompleter(self.completer)
        self.message.setAcceptRichText(False)
        SpellCheckHighlighter(self.message.document(), spell_checker)

        message_layout.addWidget(self.message)

        hsplitter = QtGui.QSplitter(QtCore.Qt.Horizontal, splitter)
        splitter.addWidget(hsplitter)

        fileview_panel = QtGui.QWidget()
        hsplitter.addWidget(fileview_panel)
        vbox = QtGui.QVBoxLayout(fileview_panel)
        vbox.setMargin(0)
        
        self.file_view = QtGui.QTreeWidget(self)
        self.file_view.setHeaderLabels(
                [gettext("File Name"), gettext("Status"), gettext("Hunks")])
        header = self.file_view.header()
        header.setStretchLastSection(False)
        header.setResizeMode(0, QtGui.QHeaderView.Stretch)
        header.setResizeMode(1, QtGui.QHeaderView.ResizeToContents)
        header.setResizeMode(2, QtGui.QHeaderView.ResizeToContents)

        vbox.addWidget(self.file_view)

        selectall_checkbox = SelectAllCheckBox(
                                view=self.file_view, parent=fileview_panel)
        vbox.addWidget(selectall_checkbox)

        hunk_panel = ToolbarPanel(self)
        self.hunk_view = HunkView(complete=complete)

        hsplitter.addWidget(hunk_panel)

        # Build hunk panel toolbar
        show_find = hunk_panel.add_toolbar_button(
                        N_("Find"), icon_name="edit-find", checkable=True)
        hunk_panel.add_separator()

        view_menu = QtGui.QMenu(gettext('View Options'), self)
        view_menu.addAction(
                hunk_panel.create_button(N_("Complete"), icon_name="complete", 
                    onclick=self.hunk_view.set_complete,
                    checkable=True, checked=complete)
                )
        self.encoding_selector = EncodingMenuSelector(self.encoding,
                                    gettext("Encoding"), self.encoding_changed)
        self.encoding_selector.setIcon(get_icon("format-text-bold", 16))
        view_menu.addMenu(self.encoding_selector)
        hunk_panel.add_toolbar_menu(N_("View Options"), view_menu, icon_name="document-properties")

        hunk_panel.add_separator()
        hunk_panel.add_toolbar_button(N_("Previous hunk"), icon_name="go-up",
                          onclick=self.hunk_view.move_previous)
        hunk_panel.add_toolbar_button(N_("Next hunk"), icon_name="go-down",
                          onclick=self.hunk_view.move_next)

        find_toolbar = FindToolbar(self, self.hunk_view.browser, show_find)
        hunk_panel.add_widget(find_toolbar)
        hunk_panel.add_widget(self.hunk_view)
        find_toolbar.hide()

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 6)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(self.throbber)
        layout.addWidget(splitter)

        # build buttonbox
        buttonbox = self.create_button_box(BTN_OK, BTN_CLOSE)
        layout.addWidget(buttonbox)

        self.connect(self, QtCore.SIGNAL("finished(int)"),
                self.finished)

        self.connect(self.file_view, QtCore.SIGNAL("itemSelectionChanged()"),
                self.selected_file_changed)

        self.connect(self.file_view, QtCore.SIGNAL("itemChanged(QTreeWidgetItem *, int)"),
                self.file_checked)

        self.connect(self.hunk_view, QtCore.SIGNAL("selectionChanged()"),
                self.selected_hunk_changed)

    def show(self):
        QtCore.QTimer.singleShot(1, self.load)
        QBzrDialog.show(self)

    def exec_(self):
        QtCore.QTimer.singleShot(1, self.load)
        return QBzrDialog.exec_(self)

    def _create_shelver_and_creator(self):
        shelver = Shelver.from_args(DummyDiffWriter(), self.revision,
                False, self.file_list, None, directory = self.directory)
        try:
            creator = ShelfCreator(
                    shelver.work_tree, shelver.target_tree, self.file_list)
        except:
            shelver.finalize()
            raise

        return shelver, creator

    @runs_in_loading_queue
    @ui_current_widget
    @reports_exception()
    def load(self):
        cleanup = []
        try:
            self.throbber.show()
            cleanup.append(self.throbber.hide)
            shelver, creator = self._create_shelver_and_creator()
            cleanup.append(shelver.finalize)
            cleanup.append(creator.finalize)

            trees = (shelver.target_tree, shelver.work_tree)
            for change in creator.iter_shelvable():
                item = self._create_item(change, shelver, trees)
                self.file_view.addTopLevelItem(item)
            
        finally:
            for func in cleanup:
                func()

    def _create_item(self, change, shelver, trees):
        """Create QTreeWidgetItem for file list from Change instance."""
        ch = Change(change, shelver, trees)
        item = QtGui.QTreeWidgetItem()

        item.setIcon(0, get_icon("file", 16))
        item.change = ch
        item.setText(0, ch.disp_text)
        item.setText(1, gettext(ch.status))
        if ch.status == 'modify text':
            item.setText(2, u'0/%d' % len(ch.parsed_patch.hunks))
        item.setCheckState(0, QtCore.Qt.Unchecked)
        return item

    def selected_file_changed(self):
        items = self.file_view.selectedItems()
        if len(items) != 1 or items[0].change.status != 'modify text':
            self.hunk_view.clear()
        else:
            item = items[0]
            encoding = self.encoding_selector.encoding
            self.hunk_view.set_parsed_patch(item.change, encoding)

    def selected_hunk_changed(self):
        for item in self.file_view.selectedItems():
            change = item.change
            if change.status != 'modify text':
                continue
            hunks = change.parsed_patch.hunks
            hunk_num = len(hunks)
            selected_hunk_num = 0
            for hunk in hunks:
                if hunk.selected:
                    selected_hunk_num += 1
            item.setText(2, "%d/%d" % (selected_hunk_num, hunk_num))
            if selected_hunk_num == 0:
                item.setCheckState(0, QtCore.Qt.Unchecked)
            elif selected_hunk_num == hunk_num:
                item.setCheckState(0, QtCore.Qt.Checked)
            else:
                item.setCheckState(0, QtCore.Qt.PartiallyChecked)

    def file_checked(self, item, column):
        if column != 0:
            return

        checked = item.checkState(0)
        if checked == QtCore.Qt.Checked:
            selected = True
        elif checked == QtCore.Qt.Unchecked:
            selected = False
        else:
            return

        if item.change.status == 'modify text':
            hunk_num = len(item.change.parsed_patch.hunks)
            for hunk in item.change.parsed_patch.hunks:
                hunk.selected = selected
            self.hunk_view.update()
            item.setText(2, u'%d/%d' % (hunk_num if selected else 0, hunk_num))

    def encoding_changed(self, encoding):
        self.selected_file_changed()

    def complete_toggled(self, checked):
        self.hunk_view.set_complete(checked)
    
    def do_accept(self):
        change_dict = {}
        for i in range(0, self.file_view.topLevelItemCount()):
            item = self.file_view.topLevelItem(i)
            change = item.change
            if item.checkState(0) == QtCore.Qt.Unchecked:
                continue
            change_dict[(change.file_id, change.status)] = change
        if change_dict:
            ret = QtGui.QMessageBox.question(self, gettext('Shelve'),
                    gettext('%d file(s) will be shelved.') % len(change_dict),
                    QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
            if ret != QtGui.QMessageBox.Ok:
                return
        else:
            QtGui.QMessageBox.information(self, gettext('Shelve'),
                    gettext('No changes selected.'), gettext('&OK'))
            return

        cleanup = []
        try:
            shelver, creator = self._create_shelver_and_creator()
            cleanup.append(shelver.finalize)
            cleanup.append(creator.finalize)
            trees = (shelver.target_tree, shelver.work_tree)
            changes = []
            for ch in creator.iter_shelvable():
                change = Change(ch, shelver, trees)
                key = (change.file_id, change.status)
                org_change = change_dict.get(key)
                if org_change is None:
                    continue
                if not change.is_same_change(org_change):
                    QtGui.QMessageBox.warning(self, gettext('Shelve'),
                            gettext('Operation aborted because target file(s) has been changed.'), gettext('&OK'))
                    return
                del(change_dict[key])
                changes.append(org_change)

            if change_dict:
                QtGui.QMessageBox.warning(self, gettext('Shelve'),
                        gettext('Operation aborted because target file(s) has been changed.'), gettext('&OK'))
                return

            for change in changes:
                if change.status == 'modify text':
                    self.handle_modify_text(creator, change)
                elif change.status == 'modify binary':
                    creator.shelve_content_change(change.data[1])
                else:
                    creator.shelve_change(change.data)
            manager = shelver.work_tree.get_shelf_manager()
            message = unicode(self.message.toPlainText()).strip() or gettext(u'<no message>')
            shelf_id = manager.shelve_changes(creator, message)
        finally:
            while cleanup:
                cleanup.pop()()
        QBzrDialog.do_accept(self)

    def handle_modify_text(self, creator, change):
        final_hunks = []
        offset = 0
        change_count = 0
        for hunk in change.parsed_patch.hunks:
            if hunk.selected:
                offset -= (hunk.mod_range - hunk.orig_range)
                change_count += 1
            else:
                hunk.mod_pos += offset
                final_hunks.append(hunk)

        if change_count == 0:
            return
        patched = patches.iter_patched_from_hunks(change.target_lines, final_hunks)
        creator.shelve_lines(change.file_id, list(patched))

    def add_cleanup(self, func):
        self._cleanup_funcs.append(func)
        
    def cleanup(self):
        while len(self._cleanup_funcs) > 0:
            try:
                self._cleanup_funcs.pop()()
            except:
                pass

    def finished(self, ret):
        self.cleanup()
        self.saveSize()

class HunkView(QtGui.QWidget):
    def __init__(self, complete=False, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setMargin(0)
        self.browser = HunkTextBrowser(complete, self)
        self.selector = HunkSelector(self.browser, self)
        layout.addWidget(self.selector)
        layout.addWidget(self.browser)
        self.connect(self.browser, QtCore.SIGNAL("focusedHunkChanged()"), 
                     self.update)

        def selected_hunk_changed():
            self.update()
            self.emit(QtCore.SIGNAL("selectionChanged()"))
        self.connect(self.browser, QtCore.SIGNAL("selectedHunkChanged()"), 
                     selected_hunk_changed)

        self.change = None
        self.encoding = None

    def set_complete(self, value):
        self.browser.complete = value
        if self.change is not None:
            self.set_parsed_patch(self.change, self.encoding)

    def move_previous(self):
        self.browser.move_previous()

    def move_next(self):
        self.browser.move_next()

    def rewind(self):
        self.browser.rewind()

    def set_parsed_patch(self, change, encoding):
        self.change = change
        self.encoding = encoding
        self.browser.set_parsed_patch(change, encoding)
        self.update()

    def update(self):
        self.selector.update()
        self.browser.update()

    def clear(self):
        self.browser.clear()

class HunkSelector(QtGui.QFrame):
    def __init__(self, browser, parent):
        QtGui.QFrame.__init__(self, parent)
        self.browser = browser
        self.setFixedWidth(25)
        self.setStyleSheet("border:1px solid lightgray;")
        self.connect(browser.verticalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.scrolled)
        self.frame_width = QtGui.QApplication.style().pixelMetric(QtGui.QStyle.PM_DefaultFrameWidth)

        self.checkbox_pen = QtGui.QPen(QtCore.Qt.black)
        self.checkbox_pen.setWidth(2)

    def scrolled(self, value):
        self.update()

    def paintEvent(self, event):
        QtGui.QFrame.paintEvent(self, event) 
        browser = self.browser
        if not browser.hunk_list:
            return
        scroll_y = browser.verticalScrollBar().value() - self.frame_width
        painter = QtGui.QPainter(self)
        rect = event.rect()
        painter.setClipRect(rect)
        browser.draw_background(
                QtCore.QRect(1, rect.top(), self.width() - 2, rect.height()), 
                painter, scroll_y)

        # draw checkbox
        top, bottom = rect.top(), rect.bottom()
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(self.checkbox_pen)
        for hunk, y1, y2 in browser.hunk_list:
            y1 -= scroll_y
            y1 += 4
            if y1 + 13 < top:
                continue
            if bottom < y1:
                break
            painter.fillRect(6, y1, 13, 13, QtCore.Qt.white)

            painter.drawRect(6, y1, 13, 13)
            if hunk.selected:
                painter.drawLine(9, y1 + 7, 12, y1 + 10)
                painter.drawLine(16, y1 + 3, 12, y1 + 10)

        del painter

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            browser = self.browser
            scroll_y = browser.verticalScrollBar().value()

            y = event.y() + scroll_y - self.frame_width
            for i, (hunk, top, bottom) in enumerate(browser.hunk_list):
                if top <= y <= bottom:
                    browser.toggle_selection(i)
                    break
                elif y < top:
                    break
            browser.focus_hunk_by_pos(event.y() - self.frame_width)
        QtGui.QFrame.mousePressEvent(self, event)

class HunkTextBrowser(QtGui.QTextBrowser):

    def __init__(self, complete=False, parent=None):
        # XXX: This code should be merged with QSimpleDiffView
        QtGui.QTextBrowser.__init__(self, parent)
        self.hunk_list = []
        self.doc = QtGui.QTextDocument(parent)
        self.doc.setUndoRedoEnabled(False)
        self.setDocument(self.doc)

        option = self.doc.defaultTextOption()
        option.setWrapMode(QtGui.QTextOption.NoWrap)
        self.doc.setDefaultTextOption(option)
        self.rewinded = False
        self.cursor = QtGui.QTextCursor(self.doc)
        
        monospacedFont = get_monospace_font()
        self.monospacedFormat = QtGui.QTextCharFormat()
        self.monospacedFormat.setFont(monospacedFont)
        self.monospacedInsertFormat = QtGui.QTextCharFormat(self.monospacedFormat)
        self.monospacedInsertFormat.setForeground(QtGui.QColor(0, 136, 11))
        self.monospacedDeleteFormat = QtGui.QTextCharFormat(self.monospacedFormat)
        self.monospacedDeleteFormat.setForeground(QtGui.QColor(204, 0, 0))
        
        self.monospacedInactiveFormat = QtGui.QTextCharFormat(self.monospacedFormat)
        self.monospacedInactiveFormat.setForeground(QtGui.QColor(128, 128, 128))
    
        titleFont = QtGui.QFont(monospacedFont)
        titleFont.setPointSize(titleFont.pointSize() * 140 / 100)
        titleFont.setBold(True)
        titleFont.setItalic(True)

        self.monospacedHunkFormat = QtGui.QTextCharFormat()
        self.monospacedHunkFormat.setFont(titleFont)
        self.monospacedHunkFormat.setForeground(QtCore.Qt.black)
        
        from bzrlib.plugins.qbzr.lib.diffview import colors
        self.header_color = colors['blank'][0]
        self.border_pen = QtGui.QPen(QtCore.Qt.gray)
        self.focus_color = QtGui.QColor(0x87, 0xCE, 0xEB, 0x48) # lightBlue
        self.focus_color_inactive = QtGui.QColor(0x87, 0xCE, 0xEB, 0x20) # lightBlue

        self.complete = complete
        self._focused_index = -1

    def rewind(self):
        if not self.rewinded:
            self.rewinded = True
            self.verticalScrollBar().setValue(0)

    def set_parsed_patch(self, change, encoding):
        self.clear()
        cursor = self.cursor

        patch = change.parsed_patch
        texts = change.encode_hunk_texts(encoding)
        if self.complete:
            work_lines = change.encode_work_lines(encoding)

        def print_hunk(hunk, hunk_texts):
            for line, text in zip(hunk.lines, hunk_texts):
                if isinstance(line, InsertLine):
                    fmt = self.monospacedInsertFormat
                elif isinstance(line, RemoveLine):
                    fmt = self.monospacedDeleteFormat
                else:
                    fmt = self.monospacedFormat
                cursor.insertText(text, fmt)
        
        start = 0
        for hunk, hunk_texts in zip(patch.hunks, texts):
            # NOTE: hunk.mod_pos is 1 based value, not 0 based.
            if self.complete:
                lines = "".join([' ' + l for l in work_lines[start:hunk.mod_pos - 1]])
                if lines:
                    cursor.insertText(lines, self.monospacedInactiveFormat)
                start = hunk.mod_pos + hunk.mod_range - 1
                y1 = cursor.block().layout().position().y()
                print_hunk(hunk, hunk_texts)
                y2 = cursor.block().layout().position().y()

            else:
                y1 = cursor.block().layout().position().y()
                cursor.insertText(str(hunk.get_header()), self.monospacedHunkFormat)
                print_hunk(hunk, hunk_texts)
                cursor.insertText("\n", self.monospacedFormat)
                y2 = cursor.block().layout().position().y()

            self.hunk_list.append((hunk, y1, y2))

        if self.complete:
            lines = "".join([' ' + l for l in work_lines[start:]])
            if lines:
                cursor.insertText(lines, self.monospacedInactiveFormat)

        if self.hunk_list:
            self._set_focused_hunk(0)

        self.update()

    def update(self):
        QtGui.QTextBrowser.update(self)
        self.viewport().update()

    def clear(self):
        QtGui.QTextBrowser.clear(self)
        del(self.hunk_list[:])
        self._set_focused_hunk(-1)

    def paintEvent(self, event):
        if not self.hunk_list:
            QtGui.QTextBrowser.paintEvent(self, event) 
            return
        scroll_y = self.verticalScrollBar().value()

        painter = QtGui.QPainter(self.viewport())
        rect = event.rect()
        painter.setClipRect(rect)

        self.draw_background(rect, painter, scroll_y)

        QtGui.QTextBrowser.paintEvent(self, event) 
        del painter

    def draw_background(self, rect, painter, offset):
        left, right, width = rect.left(), rect.right(), rect.width()
        top, bottom = rect.top(), rect.bottom()
        painter.setPen(self.border_pen)
        for i, (hunk, y1, y2) in enumerate(self.hunk_list):
            y1 -= offset
            y2 -= offset
            if bottom < y1 or y2 < top:
                continue
            if not self.complete:
                # Fill header rect.
                painter.fillRect(left, y1, width, 20, self.header_color)
            # Overlay focus rect.
            if i == self._focused_index:
                if self.hasFocus():
                    color = self.focus_color
                else:
                    color = self.focus_color_inactive
                painter.fillRect(left, y1, width, y2 - y1, color)
            # Draw border.
            painter.drawLine(left, y1, right, y1)
            painter.drawLine(left, y2, right, y2)
        
    def move_next(self):
        index = int(self._focused_index + 1)
        if index == len(self.hunk_list):
            index -= 1
        self._set_focused_hunk(index)

    def move_previous(self):
        index = int(self._focused_index)
        if 1 <= index and index == self._focused_index:
            index -= 1
        self._set_focused_hunk(index)

    def toggle_selection(self, index):
        if 0 <= index < len(self.hunk_list) and int(index) == index:
            self.hunk_list[index][0].selected = \
                    not self.hunk_list[index][0].selected
            self.emit(QtCore.SIGNAL("selectedHunkChanged()"))

    def focus_hunk_by_pos(self, y):
        index = self.hittest(y)
        self._set_focused_hunk(index, scroll=False)

    def _set_focused_hunk(self, index, scroll=True):
        self._focused_index = index
        self.update()
        self.emit(QtCore.SIGNAL("focusedHunkChanged()"))
        if scroll and int(index) == index:
            self.scroll_to_hunk(index)

    def hittest(self, y):
        # NOTE : Value of y is client coordinate.
        # If y is between (N)th and (N+1)th hunks, return (N + 0.5)
        if not self.hunk_list:
            return -1
        y += self.verticalScrollBar().value()
        for i, (hunk, y1, y2) in enumerate(self.hunk_list):
            if y1 <= y <= y2:
                return i
            elif y < y1:
                return i - 0.5
        return i + 0.5

    def scroll_to_hunk(self, index):
        sbar = self.verticalScrollBar()
        if index < 0:
            sbar.setValue(0)
        elif len(self.hunk_list) <= index:
            sbar.setValue(sbar.maximum())
        else:
            MARGIN = 24
            height = self.viewport().height()
            cur_pos = sbar.value()
            max_pos = self.hunk_list[index][1] - MARGIN
            min_pos = self.hunk_list[index][2] - height + MARGIN
            if max_pos <= min_pos or max_pos < cur_pos:
                sbar.setValue(max_pos)
            elif cur_pos < min_pos:
                sbar.setValue(min_pos)
                
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.focus_hunk_by_pos(event.y())

        QtGui.QTextBrowser.mousePressEvent(self, event)

    def focusInEvent(self, event):
        self.parent().update()
        QtGui.QTextBrowser.focusInEvent(self, event)

    def focusOutEvent(self, event):
        self.parent().update()
        QtGui.QTextBrowser.focusOutEvent(self, event)

    def keyPressEvent(self, event):
        mod, key = int(event.modifiers()), event.key()
        if mod == QtCore.Qt.NoModifier:
            if key == QtCore.Qt.Key_Space:
                self.toggle_selection(self._focused_index)
                return
        elif mod == QtCore.Qt.ControlModifier:
            if key == QtCore.Qt.Key_Up:
                self.move_previous()
                return
            elif key == QtCore.Qt.Key_Down:
                self.move_next()
                return
        QtGui.QTextBrowser.keyPressEvent(self, event)




