# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
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
from PyQt4 import QtCore, QtGui
import os

from bzrlib.commands import get_cmd_object

from bzrlib.plugins.qbzr.lib.i18n import gettext
from bzrlib.plugins.qbzr.lib.subprocess import SubProcessWindow
from bzrlib.plugins.qbzr.lib.ui_init import Ui_InitForm
from bzrlib.plugins.qbzr.lib.help import show_help

from bzrlib.plugins.qbzr.lib.util import (
    hookup_directory_picker,
    DIRECTORYPICKER_SOURCE,
    DIRECTORYPICKER_TARGET,
    )


class QBzrInitWindow(SubProcessWindow):

    def __init__(self, localdir=u".", parent=None, ui_mode=False):
        SubProcessWindow.__init__(self,
                                  gettext("Initialize"),
                                  name = "init",
                                  default_size = (400, 300),
                                  ui_mode = ui_mode,
                                  dialog = True,
                                  parent = parent)

        # One directory picker
        self.ui.location.setText(os.path.abspath(localdir))
        hookup_directory_picker(self,
                                self.ui.location_picker,
                                self.ui.location,
                                DIRECTORYPICKER_TARGET)

        # Combo box for repo format.
        cmd = get_cmd_object('init')
        opt = cmd.options()['format']
        fill_option_combo(self.ui.combo_format, opt, 'default',
                          self.ui.format_desc)

        self.ui.but_append_only.setToolTip(cmd.options()['append-revisions-only'].help)

        cmd = get_cmd_object('init-repo')
        opt = cmd.options()['no-trees']
        self.ui.but_no_trees.setToolTip(opt.help)

        self.connect(self.ui.but_init, QtCore.SIGNAL("toggled(bool)"),
                     self.init_toggled)
        self.ui.but_init.setChecked(True)

        self.connect(self.ui.link_help, QtCore.SIGNAL("linkActivated(const QString &)"),
                     self.link_help_activated)
        self.connect(self.ui.link_help_formats, QtCore.SIGNAL("linkActivated(const QString &)"),
                     self.link_help_activated)

        self.process_widget.hide_progress()
    
    def create_ui(self, parent):
        ui_widget = QtGui.QWidget(parent)
        self.ui = Ui_InitForm()
        self.ui.setupUi(ui_widget)
        return ui_widget

    def init_toggled(self, bool):
        # The widgets for normal 'init'
        for w in [self.ui.but_append_only]:
            w.setEnabled(bool)
        # The widgets for 'init-repo'
        for w in [self.ui.but_no_trees]:
            w.setEnabled(not bool)

    def link_help_activated(self, target):
        # Our help links all are of the form 'bzrtopic:topic-name'
        scheme, link = unicode(target).split(":", 1)
        if scheme != "bzrtopic":
            raise RuntimeError, "unknown scheme"
        show_help(link, self)

    def start(self):
        location = unicode(self.ui.location.text())
        if not location:
            self.process_widget.logMessage(gettext("You must specify a location"),
                                           error=True)
            self.failed()
            return

        if self.ui.but_init.isChecked():
            args = ['init']
            if self.ui.but_append_only.isChecked():
                args.append('--append-revisions-only')
        else:
            args = ['init-repo']
            if self.ui.but_no_trees.isChecked():
                args.append('--no-trees')
        args.append('--format=' + self.ui.combo_format.currentText())

        args.append(location)

        self.process_widget.start(None, *args)

# TODO: Move this to the 'utils' module - but let's wait until we have another
# user for this function, and we can see if it makes more sense to just
# pass the command and option names rather than the option object itself?
def fill_option_combo(combo, option, default, desc_widget=None):
    """Fill a widget with the values specified in a bzr.options.Option object.
    
    If default is specified, a string match is made.  Otherwise, the first
    option is the default.

    If desc_widget is specified, it is a widget which will be updated with
    the help text for the option as each option is selected.
    """

    def index_changed(index, combo=combo, desc_widget=desc_widget):
        help = combo.itemData(index).toString()
        desc_widget.setText(help)

    default_index = 0
    for i, info in enumerate(option.iter_switches()):
        if i==0:
            # this is the option itself
            continue
        name, short_name, argname, help = info
        if option.is_hidden(name):
            continue
        user_data = QtCore.QVariant(help or '')
        combo.addItem(name, user_data)
        if name == default:
            default_index = i - 1
        if desc_widget is not None:
            combo.parentWidget().connect(combo,
                                         QtCore.SIGNAL("currentIndexChanged(int)"),
                                         index_changed)

    combo.setCurrentIndex(default_index)