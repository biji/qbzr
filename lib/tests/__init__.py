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

import os
import sys
from bzrlib import trace

try:
    from PyQt4 import QtGui
except ImportError:
    _qt_app = "don't initialize it!"    # fake object to avoid QApplication call
else:
    _qt_app = None   # intended to hold global QApplication instance for tests.


def load_tests(basic_tests, module, loader):
    global _qt_app
    if _qt_app is None:
        _qt_app = QtGui.QApplication(sys.argv)
    
    testmod_names = [
        'mock',
        'test_annotate',
        'test_autocomplete',
        'test_bugs',
        'test_commit_data',
        #'test_diffview', - broken by API changes
        'test_extra_isignored',
        'test_extra_isversioned',
        'test_i18n',
        'test_log',
        'test_loggraphprovider',
        'test_logmodel',
        'test_qbzr',
        'test_revisionmessagebrowser',
        'test_spellcheck',
        'test_subprocess',
        'test_tree_branch',
        'test_treewidget',
        'test_util',
    ]
    for name in testmod_names:
        m = "%s.%s" % (__name__, name)
        try:
            basic_tests.addTests(loader.loadTestsFromModuleName(m))
        except ImportError, e:
            if str(e).endswith('PyQt4'):
                trace.note('QBzr: skip module %s '
                    'because PyQt4 is not installed' % m)
            else:
                raise
    return basic_tests


def replace_report_exception(test_case):
    import bzrlib.plugins.qbzr.lib.trace
    def report_exception(exc_info=None, type=None, window=None,
                         ui_mode=False):
        raise
    old_report_exception = bzrlib.plugins.qbzr.lib.trace.report_exception
    bzrlib.plugins.qbzr.lib.trace.report_exception = report_exception
    
    def restore_report_exception():
        bzrlib.plugins.qbzr.lib.trace.report_exception = old_report_exception
    
    test_case.addCleanup(restore_report_exception)
    
