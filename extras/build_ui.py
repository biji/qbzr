# -*- coding: utf-8 -*-
#
# QBzr - Qt frontend to Bazaar commands
# Copyright (C) 2007 Lukáš Lalinský <lalinsky@gmail.com>
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

from distutils import log
from distutils.core import Command
from distutils.dep_util import newer
from StringIO import StringIO
import glob
import os
import re


_translate_re = re.compile(r'QtGui\.QApplication.translate\(.*?, (.*?), None, QtGui\.QApplication\.UnicodeUTF8\)')
_import_re = re.compile(r'(from PyQt4 import QtCore, QtGui)')


class build_ui(Command):
    description = "build Qt UI files"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        from PyQt4 import uic
        for uifile in glob.glob("ui/*.ui"):
            pyfile = "ui_%s.py" % os.path.splitext(os.path.basename(uifile))[0]
            if newer(uifile, pyfile):
                log.info("compiling %s -> %s", uifile, pyfile)
                tmp = StringIO()
                uic.compileUi(uifile, tmp)
                source = _translate_re.sub(r'gettext(\1)', tmp.getvalue())
                source = source.replace("from PyQt4 import QtCore, QtGui",
                    "from PyQt4 import QtCore, QtGui\n"
                    "from bzrlib.plugins.qbzr.i18n import gettext")
                f = open(pyfile, "w")
                f.write(source)
                f.close()
