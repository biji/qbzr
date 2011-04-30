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

import errno
import time
import string

from PyQt4 import QtCore, QtGui

from bzrlib.errors import NoSuchRevision, PathsNotVersionedError
from bzrlib.mutabletree import MutableTree
from bzrlib.patiencediff import PatienceSequenceMatcher as SequenceMatcher
from bzrlib.revisiontree import RevisionTree
from bzrlib.transform import _PreviewTree
from bzrlib.workingtree import WorkingTree
from bzrlib.workingtree_4 import DirStateRevisionTree
from bzrlib import trace
from bzrlib import cleanup

from bzrlib.plugins.qbzr.lib.diffview import (
    SidebySideDiffView,
    SimpleDiffView,
    )
from bzrlib.plugins.qbzr.lib.diff import (
    show_diff,
    has_ext_diff,
    ExtDiffMenu,
    )

from bzrlib.plugins.qbzr.lib.i18n import gettext, ngettext, N_
from bzrlib.plugins.qbzr.lib.util import (
    FilterOptions,
    FindToolbar,
    QBzrWindow,
    ToolBarThrobberWidget,
    get_icon,
    get_set_encoding,
    get_tab_width_pixels,
    is_binary_content,
    run_in_loading_queue,
    runs_in_loading_queue,
    show_shortcut_hint,
    )
from bzrlib.plugins.qbzr.lib.uifactory import ui_current_widget
from bzrlib.plugins.qbzr.lib.trace import reports_exception
from bzrlib.plugins.qbzr.lib.encoding_selector import EncodingMenuSelector

try:
    from bzrlib.errors import FileTimestampUnavailable
except ImportError:
    # FileTimestampUnavailable is available only in bzr 2.1.0rc1 and up
    from bzrlib.errors import BzrError
    class FileTimestampUnavailable(BzrError):
        """Fake FileTimestampUnavailable error for older bzr."""
        pass


def get_file_lines_from_tree(tree, file_id):
    try:
        return tree.get_file_lines(file_id)
    except AttributeError:
        return tree.get_file(file_id).readlines()

def get_title_for_tree(tree, branch, other_branch):
    branch_title = ""
    if None not in (branch, other_branch) and branch.base != other_branch.base:
        branch_title = branch.nick

    if isinstance(tree, WorkingTree):
        if branch_title:
            return gettext("Working Tree for %s") % branch_title
        else:
            return gettext("Working Tree")

    elif isinstance(tree, (RevisionTree, DirStateRevisionTree)):
        # revision_id_to_revno is faster, but only works on mainline rev
        revid = tree.get_revision_id()
        try:
            revno = branch.revision_id_to_revno(revid)
        except NoSuchRevision:
            try:
                revno_map = branch.get_revision_id_to_revno_map()
                revno_tuple = revno_map[revid]      # this can raise KeyError is revision not in the branch
                revno = ".".join("%d" % i for i in revno_tuple)
            except KeyError:
                # this can happens when you try to diff against other branch
                # or pending merge
                revno = revid

        if revno is not None:
            if branch_title:
                return gettext("Rev %(rev)s for %(branch)s") % {"rev": revno, "branch": branch_title}
            else:
                return gettext("Rev %s") % revno
        else:
            if branch_title:
                return gettext("Revid: %(revid)s for %(branch)s") %  {"revid": revid, "branch": branch_title}
            else:
                return gettext("Revid: %s") % revid

    elif isinstance(tree, _PreviewTree):
        return gettext('Merge Preview')

    # XXX I don't know what other cases we need to handle
    return 'Unknown tree'


class DiffItem(object):
    
    @classmethod
    def create(klass, trees, file_id, paths, changed_content, versioned, 
            parent, name, kind, executable, filter = None):

        if parent == (None, None): # filter out TREE_ROOT (?)
            return None

        # check for manually deleted files (w/o using bzr rm commands)
        if kind[1] is None:
            if versioned == (False, True):
                # added and missed
                return None
            if versioned == (True, True):
                versioned = (True, False)
                paths = (paths[0], None)

        renamed = (parent[0], name[0]) != (parent[1], name[1])

        dates = [None, None]
        for ix in range(2):
            if versioned[ix]:
                try:
                    dates[ix] = trees[ix].get_file_mtime(file_id, paths[ix])
                except OSError, e:
                    if not renamed or e.errno != errno.ENOENT:
                        raise
                    # If we get ENOENT error then probably we trigger
                    # bug #251532 in bzrlib. Take current time instead
                    dates[ix] = time.time()
                except FileTimestampUnavailable:
                    # ghosts around us (see Bug #513096)
                    dates[ix] = 0  # using 1970/1/1 instead

        properties_changed = [] 
        if bool(executable[0]) != bool(executable[1]):
            descr = {True: "+x", False: "-x", None: None}
            properties_changed.append((descr[executable[0]],
                                       descr[executable[1]]))

        if versioned == (True, False):
            status = N_('removed')
        elif versioned == (False, True):
            status = N_('added')
        elif renamed and changed_content:
            status = N_('renamed and modified')
        elif renamed:
            status = N_('renamed')
        else:
            status = N_('modified')
        # check filter options
        if filter and not filter(status):
            return None

        return klass(trees, file_id, paths, changed_content, versioned, kind, 
                        properties_changed, dates, status)

    def __init__(self, trees, file_id, paths, changed_content, versioned, kind,
                        properties_changed, dates, status):
        self.trees = trees
        self.file_id = file_id
        self.paths = paths
        self.changed_content = changed_content
        self.versioned = versioned
        self.kind = kind
        self.properties_changed = properties_changed
        self.dates = dates
        self.status = status

        self._lines = None
        self._binary = None
        self._group_cache = {}
        self._encodings = [None, None]
        self._ulines = [None, None]

    def load(self):
        if self._lines is None:
            self._load_lines()

    def _load_lines(self):
        if ((self.versioned[0] != self.versioned[1] or self.changed_content)
            and (self.kind[0] == 'file' or self.kind[1] == 'file')):
            lines = []
            binary = False
            for ix, tree in enumerate(self.trees):
                content = ()
                if self.versioned[ix] and self.kind[ix] == 'file':
                    content = get_file_lines_from_tree(tree, self.file_id)
                lines.append(content)
                binary = binary or is_binary_content(content)
            self._lines = lines
            self._binary = binary
        else:
            self._lines = ((),())
            self._binary = False

    @property
    def lines(self):
        if self._lines is None:
            self._load_lines()
        return self._lines

    @property
    def binary(self):
        if self._binary is None:
            self._load_lines()
        return self._binary

    def groups(self, complete, ignore_whitespace):
        key = (complete, ignore_whitespace)
        groups = self._group_cache.get(key)
        if groups is not None:
            return groups

        lines = self.lines

        if not self.binary:
            if self.versioned == (True, False):
                groups = [[('delete', 0, len(lines[0]), 0, 0)]]
            elif self.versioned == (False, True):
                groups = [[('insert', 0, 0, 0, len(lines[1]))]]
            else:
                groups = self.difference_groups(lines, complete, ignore_whitespace)
        else:
            groups = []

        self._group_cache[key] = groups
        return groups

    def difference_groups(self, lines, complete, ignore_whitespace):
        left, right = lines
        if ignore_whitespace:
            table = string.maketrans("", "")
            strip = lambda l : l.translate(table, string.whitespace)
            left  = (line.translate(table, string.whitespace) for line in left)
            right = (line.translate(table, string.whitespace) for line in right)
        matcher = SequenceMatcher(None, left, right)
        if complete:
            groups = list([matcher.get_opcodes()])
        else:
            groups = list(matcher.get_grouped_opcodes())

        return groups


    def encode(self, encodings):
        lines = self.lines
        ulines = self._ulines
        for i in range(2):
            if encodings[i] != self._encodings[i]:
                self._encodings[i] = encodings[i]
                if self.binary:
                    ulines[i] = lines[i][:]
                else:
                    try:
                        ulines[i] = [l.decode(encodings[i]) for l in lines[i]]
                    except UnicodeDecodeError, e:
                        trace.note('Failed to decode using %s, falling back to latin1', e.encoding)
                        ulines[i] = [l.decode('latin1') for l in lines[i]]
        return ulines

class DiffWindow(QBzrWindow):

    def __init__(self, arg_provider, parent=None,
                 complete=False, encoding=None,
                 filter_options=None, ui_mode=True, allow_refresh=True):

        title = [gettext("Diff"), gettext("Loading...")]
        QBzrWindow.__init__(self, title, parent, ui_mode=ui_mode)
        self.restoreSize("diff", (780, 580))

        self.trees = None
        self.encoding = encoding
        self.arg_provider = arg_provider
        self.filter_options = filter_options
        if filter_options is None:
            self.filter_options = FilterOptions(all_enable=True)
        self.complete = complete
        self.ignore_whitespace = False
        self.delayed_signal_connections = []

        self.diffview = SidebySideDiffView(self)
        self.sdiffview = SimpleDiffView(self)
        self.views = (self.diffview, self.sdiffview)

        self.stack = QtGui.QStackedWidget(self.centralwidget)
        self.stack.addWidget(self.diffview)
        self.stack.addWidget(self.sdiffview)
        vbox = QtGui.QVBoxLayout(self.centralwidget)
        vbox.addWidget(self.stack)

        for browser in self.diffview.browsers:
            browser.installEventFilter(self)

        self.create_main_toolbar(allow_refresh)
        self.addToolBarBreak()
        self.find_toolbar = FindToolbar(self, self.diffview.browsers[0],
                self.show_find)
        self.find_toolbar.hide()
        self.addToolBar(self.find_toolbar)

    def connect_later(self, *args, **kwargs):
        """Schedules a signal to be connected after loading CLI arguments.
        
        Accepts the same arguments as QObject.connect method.
        """
        self.delayed_signal_connections.append((args, kwargs))

    def process_delayed_connections(self):
        for (args, kwargs) in self.delayed_signal_connections:
            self.connect(*args, **kwargs)

    def create_main_toolbar(self, allow_refresh=True):
        toolbar = self.addToolBar(gettext("Diff"))
        toolbar.setMovable (False)
        toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

        self.show_find = self.create_find_action()
        toolbar.addAction(self.show_find)
        toolbar.addAction(self.create_toggle_view_mode())
        self.view_refresh = self.create_refresh_action(allow_refresh)
        if allow_refresh:
            toolbar.addAction(self.view_refresh)
            
        if has_ext_diff():
            show_ext_diff_menu = self.create_ext_diff_action()
            toolbar.addAction(show_ext_diff_menu)
            widget = toolbar.widgetForAction(show_ext_diff_menu)
            widget.setPopupMode(QtGui.QToolButton.InstantPopup)
            widget.setShortcut("Alt+E")
            show_shortcut_hint(widget)

        show_view_menu = self.create_view_menu()
        toolbar.addAction(show_view_menu)
        widget = toolbar.widgetForAction(show_view_menu)
        widget.setPopupMode(QtGui.QToolButton.InstantPopup)
        widget.setShortcut("Alt+V")
        show_shortcut_hint(widget)

        spacer = QtGui.QWidget()
        spacer.setSizePolicy(QtGui.QSizePolicy.Expanding,
                QtGui.QSizePolicy.Expanding)
        toolbar.addWidget(spacer)

        self.throbber = ToolBarThrobberWidget(self)
        toolbar.addWidget(self.throbber)
        return toolbar

    def create_find_action(self):
        action = QtGui.QAction(get_icon("edit-find"),
                gettext("&Find"), self)
        action.setShortcut(QtGui.QKeySequence.Find)
        action.setToolTip(gettext("Find on active panel"))
        show_shortcut_hint(action)
        action.setCheckable(True)
        return action

    def create_toggle_view_mode(self):
        action = QtGui.QAction(get_icon("view-split-left-right"),
                gettext("Unidiff"), self)
        action.setToolTip(
                gettext("Toggle between Side by side and Unidiff view modes"))
        action.setShortcut("Ctrl+U")
        show_shortcut_hint(action)
        action.setCheckable(True)
        action.setChecked(False);
        self.connect(action,
                     QtCore.SIGNAL("toggled (bool)"),
                     self.click_toggle_view_mode)
        return action

    def create_refresh_action(self, allow_refresh=True):
        action = QtGui.QAction(get_icon("view-refresh"),
                gettext("&Refresh"), self)
        action.setShortcut("Ctrl+R")
        show_shortcut_hint(action)
        self.connect(action,
                     QtCore.SIGNAL("triggered (bool)"),
                     self.click_refresh)
        action.setEnabled(allow_refresh)
        return action

    def create_ext_diff_action(self):
        action = QtGui.QAction(get_icon("system-run"),
                gettext("&External Diff"), self)
        action.setToolTip(
            gettext("Launch an external diff application"))
        ext_diff_menu = ExtDiffMenu(parent=self, include_builtin = False)
        action.setMenu(ext_diff_menu)
        self.connect(ext_diff_menu,
                QtCore.SIGNAL("triggered(QString)"),
                self.ext_diff_triggered)
        return action


    def create_view_menu(self):
        show_view_menu = QtGui.QAction(get_icon("document-properties"), gettext("&View Options"), self)
        view_menu = QtGui.QMenu(gettext('View Options'), self)
        show_view_menu.setMenu(view_menu)

        view_complete = QtGui.QAction(gettext("&Complete"), self)
        view_complete.setCheckable(True)
        self.connect(view_complete,
                     QtCore.SIGNAL("toggled (bool)"),
                     self.click_complete)
        view_menu.addAction(view_complete)

        self.ignore_whitespace_action = self.create_ignore_ws_action()
        view_menu.addAction(self.ignore_whitespace_action)

        def on_left_encoding_changed(encoding):
            if self.branches:
                get_set_encoding(encoding, self.branches[0])
            self.click_refresh()

        self.encoding_selector_left = EncodingMenuSelector(self.encoding,
            gettext("Left side encoding"),
            on_left_encoding_changed)
        view_menu.addMenu(self.encoding_selector_left)

        def on_right_encoding_changed(encoding):
            if self.branches:
                get_set_encoding(encoding, self.branches[1])
            self.click_refresh()

        self.encoding_selector_right = EncodingMenuSelector(self.encoding,
            gettext("Right side encoding"),
            on_right_encoding_changed)
        view_menu.addMenu(self.encoding_selector_right)
        return show_view_menu

    def create_ignore_ws_action(self):
        action = QtGui.QAction(gettext("&Ignore whitespace changes"), self)
        action.setCheckable(True)
        action.setChecked(self.ignore_whitespace);
        self.connect_later(action,
                     QtCore.SIGNAL("toggled (bool)"),
                     self.click_ignore_whitespace)
        return action

    def eventFilter(self, object, event):
        if event.type() == QtCore.QEvent.FocusIn:
            if object in self.diffview.browsers:
                self.find_toolbar.text_edit = object
        return QBzrWindow.eventFilter(self, object, event)
        # Why doesn't this work?
        #return super(DiffWindow, self).eventFilter(object, event)

    def show(self):
        QBzrWindow.show(self)
        QtCore.QTimer.singleShot(1, self.initial_load)

    @runs_in_loading_queue
    @ui_current_widget
    @reports_exception()
    def initial_load(self):
        """Called to perform the initial load of the form.  Enables a
        throbber window, then loads the branches etc if they weren't specified
        in our constructor.
        """
        op = cleanup.OperationWithCleanups(self._initial_load)
        self.throbber.show()
        op.add_cleanup(self.throbber.hide)
        op.run()

    def _initial_load(self, op):
        args = self.arg_provider.get_diff_window_args(self.processEvents, op.add_cleanup)

        self.trees = (args["old_tree"], args["new_tree"])
        self.branches = (args.get("old_branch", None), args.get("new_branch",None))
        self.specific_files = args.get("specific_files", None)
        self.ignore_whitespace = args.get("ignore_whitespace", False)
        self.ignore_whitespace_action.setChecked(self.ignore_whitespace)

        self.process_delayed_connections()
        self.load_branch_info()
        self.setup_tab_width()
        self.load_diff()

    def load_branch_info(self):
        self.set_diff_title()
        self.encoding_selector_left.encoding = get_set_encoding(self.encoding, self.branches[0])
        self.encoding_selector_right.encoding = get_set_encoding(self.encoding, self.branches[1])
        self.processEvents()

    def set_diff_title(self):
        rev1_title = get_title_for_tree(self.trees[0], self.branches[0],
                                        self.branches[1])
        rev2_title = get_title_for_tree(self.trees[1], self.branches[1],
                                        self.branches[0])

        title = [gettext("Diff"), "%s..%s" % (rev1_title, rev2_title)]

        if self.specific_files:
            nfiles = len(self.specific_files)
            if nfiles > 2:
                title.append(
                    ngettext("%d file", "%d files", nfiles) % nfiles)
            else:
                title.append(", ".join(self.specific_files))
        else:
            if self.filter_options and not self.filter_options.is_all_enable():
                title.append(self.filter_options.to_str())

        self.set_title_and_icon(title)
        self.processEvents()

    def setup_tab_width(self):
        tabWidths = (get_tab_width_pixels(self.branches[0]),
                     get_tab_width_pixels(self.branches[1]))
        self.diffview.setTabStopWidths(tabWidths)
        self.sdiffview.setTabStopWidth(tabWidths[0])

    def load_diff(self):
        self.view_refresh.setEnabled(False)
        for tree in self.trees: tree.lock_read()
        self.processEvents()
        try:
            changes = self.trees[1].iter_changes(self.trees[0],
                                                 specific_files=self.specific_files,
                                                 require_versioned=True)
            def changes_key(change):
                old_path, new_path = change[1]
                path = new_path
                if path is None:
                    path = old_path
                return path

            try:
                no_changes = True   # if there is no changes found we need to inform the user
                for (file_id, paths, changed_content, versioned, parent, name, kind,
                     executable) in sorted(changes, key=changes_key):
                    # file_id         -> ascii string
                    # paths           -> 2-tuple (old, new) fullpaths unicode/None
                    # changed_content -> bool
                    # versioned       -> 2-tuple (bool, bool)
                    # parent          -> 2-tuple
                    # name            -> 2-tuple (old_name, new_name) utf-8?/None
                    # kind            -> 2-tuple (string/None, string/None)
                    # executable      -> 2-tuple (bool/None, bool/None)
                    # NOTE: None value used for non-existing entry in corresponding
                    #       tree, e.g. for added/deleted file

                    self.processEvents()
                    di = DiffItem.create(self.trees, file_id, paths, changed_content,
                            versioned, parent, name, kind, executable, 
                            filter = self.filter_options.check)
                    if not di:
                        continue

                    lines = di.lines
                    self.processEvents()
                    groups = di.groups(self.complete, self.ignore_whitespace)
                    self.processEvents()
                    ulines = di.encode([self.encoding_selector_left.encoding,
                                        self.encoding_selector_right.encoding])
                    data = [''.join(l) for l in ulines]

                    for view in self.views:
                        view.append_diff(list(di.paths), di.file_id, di.kind, di.status,
                                         di.dates, di.versioned, di.binary, ulines, groups,
                                         data, di.properties_changed)
                        self.processEvents()
                    no_changes = False
            except PathsNotVersionedError, e:
                    QtGui.QMessageBox.critical(self, gettext('Diff'),
                        gettext(u'File %s is not versioned.\n'
                            'Operation aborted.') % e.paths_as_string,
                        gettext('&Close'))
                    self.close()
        finally:
            for tree in self.trees: tree.unlock()
        if no_changes:
            QtGui.QMessageBox.information(self, gettext('Diff'),
                gettext('No changes found.'),
                gettext('&OK'))
        self.view_refresh.setEnabled(self.can_refresh())

    def click_toggle_view_mode(self, checked):
        if checked:
            view = self.sdiffview
            self.find_toolbar.text_edit = view
        else:
            view = self.diffview
            self.find_toolbar.text_edit = view.browsers[0]
        view.rewind()
        index = self.stack.indexOf(view)
        self.stack.setCurrentIndex(index)

    def click_complete(self, checked ):
        self.complete = checked
        #Has the side effect of refreshing...
        self.diffview.clear()
        self.sdiffview.clear()
        run_in_loading_queue(self.load_diff)

    def click_refresh(self):
        self.diffview.clear()
        self.sdiffview.clear()
        run_in_loading_queue(self.load_diff)

    def can_refresh(self):
        """Does any of tree is Mutanble/Working tree."""
        if self.trees is None: # we might still be loading...
            return False
        tree1, tree2 = self.trees
        if isinstance(tree1, MutableTree) or isinstance(tree2, MutableTree):
            return True
        return False

    def ext_diff_triggered(self, ext_diff):
        """@param ext_diff: path to external diff executable."""
        show_diff(self.arg_provider, ext_diff=ext_diff, parent_window = self)

    def click_ignore_whitespace(self, checked ):
        self.ignore_whitespace = checked
        #Has the side effect of refreshing...
        self.diffview.clear()
        self.sdiffview.clear()
        run_in_loading_queue(self.load_diff)

