# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/run.ui'
#
# Created: Sun Aug 23 20:03:41 2009
#      by: PyQt4 UI code generator 4.4.3
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui
from bzrlib.plugins.qbzr.lib.i18n import gettext


class Ui_RunDialog(object):
    def setupUi(self, RunDialog):
        RunDialog.setObjectName("RunDialog")
        RunDialog.resize(473, 367)
        self.main_v_layout = QtGui.QVBoxLayout(RunDialog)
        self.main_v_layout.setObjectName("main_v_layout")
        self.splitter = QtGui.QSplitter(RunDialog)
        self.splitter.setOrientation(QtCore.Qt.Vertical)
        self.splitter.setOpaqueResize(False)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setObjectName("splitter")
        self.frame = QtGui.QFrame(self.splitter)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtGui.QFrame.Raised)
        self.frame.setLineWidth(0)
        self.frame.setObjectName("frame")
        self.frame_layout = QtGui.QVBoxLayout(self.frame)
        self.frame_layout.setMargin(0)
        self.frame_layout.setObjectName("frame_layout")
        self.wd_layout = QtGui.QHBoxLayout()
        self.wd_layout.setObjectName("wd_layout")
        self.wd_label = QtGui.QLabel(self.frame)
        self.wd_label.setObjectName("wd_label")
        self.wd_layout.addWidget(self.wd_label)
        self.wd_edit = QtGui.QLineEdit(self.frame)
        self.wd_edit.setObjectName("wd_edit")
        self.wd_layout.addWidget(self.wd_edit)
        self.browse_button = QtGui.QPushButton(self.frame)
        self.browse_button.setObjectName("browse_button")
        self.wd_layout.addWidget(self.browse_button)
        self.frame_layout.addLayout(self.wd_layout)
        self.cmd_layout = QtGui.QGridLayout()
        self.cmd_layout.setObjectName("cmd_layout")
        self.cmd_label = QtGui.QLabel(self.frame)
        self.cmd_label.setObjectName("cmd_label")
        self.cmd_layout.addWidget(self.cmd_label, 0, 0, 1, 1)
        self.cmd_combobox = QtGui.QComboBox(self.frame)
        self.cmd_combobox.setMinimumSize(QtCore.QSize(170, 0))
        self.cmd_combobox.setEditable(True)
        self.cmd_combobox.setObjectName("cmd_combobox")
        self.cmd_layout.addWidget(self.cmd_combobox, 0, 1, 1, 1)
        self.hidden_checkbox = QtGui.QCheckBox(self.frame)
        self.hidden_checkbox.setObjectName("hidden_checkbox")
        self.cmd_layout.addWidget(self.hidden_checkbox, 0, 2, 1, 1)
        self.frame_layout.addLayout(self.cmd_layout)
        self.opt_arg_label = QtGui.QLabel(self.frame)
        self.opt_arg_label.setLineWidth(0)
        self.opt_arg_label.setObjectName("opt_arg_label")
        self.frame_layout.addWidget(self.opt_arg_label)
        self.opt_arg_edit = QtGui.QLineEdit(self.frame)
        self.opt_arg_edit.setObjectName("opt_arg_edit")
        self.frame_layout.addWidget(self.opt_arg_edit)
        self.opt_arg_btn_layout = QtGui.QHBoxLayout()
        self.opt_arg_btn_layout.setObjectName("opt_arg_btn_layout")
        self.directory_button = QtGui.QPushButton(self.frame)
        self.directory_button.setObjectName("directory_button")
        self.opt_arg_btn_layout.addWidget(self.directory_button)
        self.filenames_button = QtGui.QPushButton(self.frame)
        self.filenames_button.setObjectName("filenames_button")
        self.opt_arg_btn_layout.addWidget(self.filenames_button)
        spacerItem = QtGui.QSpacerItem(40, 20, QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Minimum)
        self.opt_arg_btn_layout.addItem(spacerItem)
        self.frame_layout.addLayout(self.opt_arg_btn_layout)
        self.help_browser = QtGui.QTextBrowser(self.splitter)
        self.help_browser.setObjectName("help_browser")
        self.main_v_layout.addWidget(self.splitter)
        self.wd_label.setBuddy(self.wd_edit)
        self.cmd_label.setBuddy(self.cmd_combobox)
        self.opt_arg_label.setBuddy(self.opt_arg_edit)

        self.retranslateUi(RunDialog)
        QtCore.QObject.connect(RunDialog, QtCore.SIGNAL("disableUi(bool)"), self.frame.setDisabled)
        QtCore.QMetaObject.connectSlotsByName(RunDialog)
        RunDialog.setTabOrder(self.wd_edit, self.browse_button)
        RunDialog.setTabOrder(self.browse_button, self.hidden_checkbox)
        RunDialog.setTabOrder(self.hidden_checkbox, self.cmd_combobox)
        RunDialog.setTabOrder(self.cmd_combobox, self.opt_arg_edit)
        RunDialog.setTabOrder(self.opt_arg_edit, self.directory_button)
        RunDialog.setTabOrder(self.directory_button, self.filenames_button)
        RunDialog.setTabOrder(self.filenames_button, self.help_browser)

    def retranslateUi(self, RunDialog):
        RunDialog.setWindowTitle(gettext("Run bzr command"))
        self.wd_label.setText(gettext("&Working directory:"))
        self.browse_button.setText(gettext("&Browse..."))
        self.cmd_label.setText(gettext("&Command:"))
        self.hidden_checkbox.setText(gettext("&Show hidden commands"))
        self.opt_arg_label.setText(gettext("&Options and arguments for command:"))
        self.directory_button.setText(gettext("Insert &directory..."))
        self.filenames_button.setText(gettext("Insert &filenames..."))
        self.help_browser.setHtml(QtGui.QApplication.translate("RunDialog", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'MS Shell Dlg 2\'; font-size:8.25pt; font-weight:400; font-style:normal;\">\n"
"<p style=\"-qt-paragraph-type:empty; margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px; font-size:8pt;\"></p></body></html>", None, QtGui.QApplication.UnicodeUTF8))

