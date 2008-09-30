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

"""QBzr - Qt-based frontend for Bazaar

Provided commands:
    qannotate, qbrowse, qcat, qcommit, qconfig, qdiff, qlog, qpull, qpush.
"""

from bzrlib import registry
from bzrlib.commands import register_command


version_info = (0, 9, 5, 'dev', 0)
__version__ = '.'.join(map(str, version_info))


class LazyCommandProxy(registry._LazyObjectGetter):

    def __init__(self, module, name, aliases):
        super(LazyCommandProxy, self).__init__(module, name)
        self.aliases = aliases
        self.__name__ = name

    def __call__(self, *args, **kwargs):
        return self.get_obj()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.get_obj(), name)


def register_lazy_command(module, name, aliases, decorate=False):
    """Lazily register a command.

    :param module: Name of the module where is the command defined
    :param name: Name of the command class; this Command subclass must
        exist in `module`
    :param aliases: List of command aliases
    :param decorate: If true, allow overriding an existing command
        of the same name; the old command is returned by this function.
        Otherwise it is an error to try to override an existing command.
    """
    register_command(LazyCommandProxy(module, name, aliases), decorate)


register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_merge', [])  # provides merge --qpreview
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qadd', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qannotate', ['qann', 'qblame'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qbranch', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qbrowse', ['qbw'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qbzr', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qcat', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qcommit', ['qci'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qconfig', ['qconfigure'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qdiff', ['qdi'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qgetupdates', ['qgetu'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qgetnew', ['qgetn'])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qinfo', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qinit', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qhelp', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qlog', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qmerge', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qpull', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qpush', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qrevert', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.commands', 'cmd_qsubprocess', [])

register_lazy_command('bzrlib.plugins.qbzr.lib.extra.isignored', 'cmd_is_ignored', [])
register_lazy_command('bzrlib.plugins.qbzr.lib.extra.isversioned', 'cmd_is_versioned', [])


def load_tests(basic_tests, module, loader):
    from bzrlib.plugins.qbzr.lib.tests import load_tests
    return load_tests(basic_tests, module, loader)
