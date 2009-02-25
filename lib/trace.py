# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2009 Mark Hammond <mhammond@skippinet.com.au>
# Copyright (C) 2009 Gary van der Merwe <garyvdm@gmail.com>
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

from bzrlib import errors

from bzrlib.plugins.qbzr.lib.i18n import gettext, N_, ngettext

class StopException(Exception):
    """A exception that is ignored in our error reporting, which can be used
    to stop a process due to user action. (Similar to KeyInterupt)
    """
    pass

MAIN_LOAD_METHOD = 0
"""The exception is beening reported from the main loading method.
Causes the window to be closed.
"""
SUB_LOAD_METHOD = 1
"""The exception is beening reported from the sub loading method.
Does not cause the window to me closed. This is typicaly used when a user
enters a branch location on one of our forms, and we try load that branch.
"""
ITEM_OR_EVENT_METHOD = 2
"""The exception is beening reported from a method that is called per item.
The user is allowed to ignore the error, or close the window.
"""

closing_due_to_error = False

def report_exception(exc_info=None, type=MAIN_LOAD_METHOD, window=None):
    """Report an exception.

    The error is reported to the console or a message box, depending
    on the type. 
    """
    
    # We only want one error to show if the user chose Close
    global closing_due_to_error
    if closing_due_to_error or \
        getattr(window, 'closing_due_to_error', False):
        return
    
    from cStringIO import StringIO
    from bzrlib.trace import report_exception, print_exception

    if exc_info is None:
        exc_info = sys.exc_info()
    
    exc_type, exc_object, exc_tb = exc_info
    
    # Don't show error for StopException
    if isinstance(exc_object, StopException):
        # Do we maybe want to log this?
        return
    
    msg_box = (type == MAIN_LOAD_METHOD and window and window.ui_mode) \
              or not type == MAIN_LOAD_METHOD
    
    if msg_box:
        err_file = StringIO()
    else:
        err_file = sys.stderr
    
    # always tell bzr to report it, so it ends up in the log.        
    error_type = report_exception(exc_info, err_file)
    
    close = True
    if msg_box:
        if error_type == errors.EXIT_INTERNAL_ERROR:
            # this is a copy of bzrlib.trace.report_bug
            # but we seperate the message, and the trace back,
            # and addes a hyper link to the filebug page.
            import os
            import bzrlib            
            from bzrlib import (
                osutils,
                plugin,
                )
            
            message ="\
Bazaar has encountered an internal error. Please report a bug at \
<a href=\"https://bugs.launchpad.net/bzr/+filebug\">\
https://bugs.launchpad.net/bzr/+filebug</a> including this traceback, and a \
description of what you were doing when the error occurred."
            
            traceback_file = StringIO()
            print_exception(exc_info, traceback_file)
            traceback_file.write('\n')
            traceback_file.write('bzr %s on python %s (%s)\n' % \
                               (bzrlib.__version__,
                                bzrlib._format_version_tuple(sys.version_info),
                                sys.platform))
            traceback_file.write('arguments: %r\n' % sys.argv)
            traceback_file.write(
                'encoding: %r, fsenc: %r, lang: %r\n' % (
                    osutils.get_user_encoding(), sys.getfilesystemencoding(),
                    os.environ.get('LANG')))
            traceback_file.write("plugins:\n")
            for name, a_plugin in sorted(plugin.plugins().items()):
                traceback_file.write("  %-20s %s [%s]\n" %
                    (name, a_plugin.path(), a_plugin.__version__))
            
            
            # PyQt is stupid and thinks QMessageBox.StandardButton and
            # QDialogButtonBox.StandardButton are different, so we have to
            # duplicate this :-(
            if type == MAIN_LOAD_METHOD:
                buttons = QtGui.QDialogButtonBox.Close
            elif type == SUB_LOAD_METHOD:
                buttons = QtGui.QDialogButtonBox.Ok
            elif type == ITEM_OR_EVENT_METHOD:
                buttons = QtGui.QDialogButtonBox.Close | \
                          QtGui.QDialogButtonBox.Ignore
            
            msg_box = ErrorReport(gettext("Error"),
                                  message,
                                  traceback_file.getvalue(),
                                  buttons,
                                  window)
        else:
            if type == MAIN_LOAD_METHOD:
                buttons = QtGui.QMessageBox.Close
            elif type == SUB_LOAD_METHOD:
                buttons = QtGui.QMessageBox.Ok
            elif type == ITEM_OR_EVENT_METHOD:
                buttons = QtGui.QMessageBox.Close | QtGui.QMessageBox.Ignore
            
            msg_box = QtGui.QMessageBox(QtGui.QMessageBox.Warning,
                                        gettext("Error"),
                                        err_file.getvalue(),
                                        buttons,
                                        window)
        msg_box.exec_()
        
        if not msg_box.result() == QtGui.QDialog.Rejected and \
           not msg_box.result() == QtGui.QMessageBox.Close:
            close = False
    
    if close:
        if window is None:
            closing_due_to_error = True
            QtCore.QCoreApplication.instance().quit()
        else:
            window.closing_due_to_error = True
            window.close()

class ErrorReport(QtGui.QDialog):
    def __init__(self, title, message, trace_back, buttons,
                 parent=None):
        QtGui.QDialog.__init__ (self, parent)
        
        label = QtGui.QLabel(message)
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignTop|QtCore.Qt.AlignLeft)

        icon_label = QtGui.QLabel()
        icon_label.setPixmap(self.style().standardPixmap(
            QtGui.QStyle.SP_MessageBoxCritical))
        
        trace_back_label = QtGui.QTextEdit()
        trace_back_label.setPlainText (trace_back)
        trace_back_label.setReadOnly(True)
        
        buttonbox = QtGui.QDialogButtonBox(buttons)
        self.connect(buttonbox,
                     QtCore.SIGNAL("accepted ()"),
                     self.accept)
        self.connect(buttonbox,
                     QtCore.SIGNAL("rejected ()"),
                     self.reject)

        layout = QtGui.QGridLayout()
        layout.addWidget(icon_label, 0, 0)
        layout.addWidget(label, 0, 1)
        layout.setColumnStretch(1,1)
        
        layout.addWidget(trace_back_label, 1, 0, 2, 0)
        layout.setRowStretch(1,1)
        
        layout.addWidget(buttonbox, 3, 0, 2, 0)
        
        self.setLayout(layout)
        
        self.setWindowTitle(title)
        
        icon = QtGui.QIcon()
        icon.addFile(":/bzr-16.png", QtCore.QSize(16, 16))
        icon.addFile(":/bzr-32.png", QtCore.QSize(32, 32))
        icon.addFile(":/bzr-48.png", QtCore.QSize(48, 48))
        self.setWindowIcon(icon)
        
        screen = QtGui.QApplication.desktop().screenGeometry()
        self.resize (QtCore.QSize(screen.width()*0.8, screen.height()*0.8))

def reports_exception(type=MAIN_LOAD_METHOD):
    """Decorator to report Exceptions raised from the called method
    """
    def reports_exception_decorator(f):
        
        def reports_exception_decorate(*args, **kargs):
            try:
                return f(*args, **kargs)
            except Exception:
                # args[0] - typycaly self, may have it's own report_exception
                # method.
                if getattr(args[0], 'report_exception', None) is not None:
                    args[0].report_exception(type=type)
                else:
                    report_exception(type=type)
        
        return reports_exception_decorate
    
    return reports_exception_decorator

def excepthook(type, value, traceback):
    exc_info = (type, value, traceback)
    report_exception(exc_info=exc_info,
                     type=ITEM_OR_EVENT_METHOD)
