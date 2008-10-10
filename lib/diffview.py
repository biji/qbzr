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

from PyQt4 import QtGui, QtCore

import re
from bzrlib import timestamp
from bzrlib.patiencediff import PatienceSequenceMatcher as SequenceMatcher
from bzrlib.plugins.qbzr.lib.i18n import gettext
from bzrlib.plugins.qbzr.lib.util import htmlencode
from bzrlib.plugins.qbzr.lib.util import (
    file_extension,
    format_timestamp,
    split_tokens_at_lines,
    format_for_ttype,
    QBzrGlobalConfig,
		QBzrConfig,
    )

have_pygments = True
try:
    from pygments import lex
    from pygments.util import ClassNotFound
    from pygments.lexers import get_lexer_for_filename
except ImportError:
    have_pygments = False

colors = {
    'delete': [QtGui.QColor(255, 160, 180), QtGui.QColor(200, 60, 90)],
    'insert': [QtGui.QColor(180, 255, 180), QtGui.QColor(80, 210, 80)],
    'replace': [QtGui.QColor(206, 226, 250), QtGui.QColor(90, 130, 180)],
    'blank': [QtGui.QColor(240, 240, 240), QtGui.QColor(171, 171, 171)],
}

#load user-defined colour mapping from configuration file.
#For each kind, there can be two entries in the configuration file,
#under the [QDIFF COLOURS] section:
#  kind_bound -- the colour of the boundary of the rectangle this kind refers to.
#  kind_fill  -- the colour of the filling of that same rectangle.
#The colors should be given in a R, G, B format. For example:
#   [QDIFF COLOURS]
#   delete_fill  = 255, 160, 180
#   delete_bound = 200, 60, 90

#Utility function:
#  If val is a list of 3 strings, each one representing an integer less than 256, then the RGB colour they represent is returned.
# Otherwise, ValueError is raised.
def colour_value_to_RGB(val):
  if list != type(val) or 3 != len(val) or not \
    reduce(lambda x,y: x and y.isdigit(), val, True):
        raise ValueError(
            "Adhere to colour format: red, green, blue")
    
  #Being here guarantees that colour_value is a list
  #of three elements that represent numbers.
  colour_components = map(int, colour_value)
  if not reduce(lambda x,y: x and y < 256, colour_components, True):
      raise ValueError("Colour components are in the range 0..255 only. Given: " + str(colour_components))
      
  #Now we know the given colour is safe to use.
  return apply(QtGui.QColor, colour_components)
    
config = QBzrConfig()
component_dict = {0:'fill', 1:'bound'}
for key in colors.iterkeys():
    for comp in [0,1]:
        colour_value = config.getOption(key + '_' + component_dict[comp],
                                        'QDIFF COLOURS')
        if None != colour_value:
            # Check validity of input.
            # I'm not sure which error handling policy we're using,
            # so here's a generic framework.
            try:
                colors[key][comp] = colour_value_to_RGB(colour_value)
            except ValueError:
                #error handling.
                pass

#The background colour of the replacement text in a replacement group.
replacement_text_background = QtGui.QColor(180, 210, 250)

#Get a user-defined replacement text background
colour_value = config.getOption('replacement_text_background', 
                                'QDIFF COLOURS')
if None != colour_value:
    try:
        replacement_text_background = colour_value_to_RGB(colour_value)
    except ValueError:
        #error handling.
        pass

brushes = {}
for kind, cols in colors.items():
    brushes[kind] = (QtGui.QBrush(cols[0]), QtGui.QBrush(cols[1]))


class DiffSourceView(QtGui.QTextBrowser):

    def __init__(self, parent=None):
        QtGui.QTextBrowser.__init__(self, parent)
        self.setLineWrapMode(QtGui.QTextEdit.NoWrap)
        self.clear()

    def clear(self):
        self.changes = []
        self.infoBlocks = []

    def paintEvent(self, event):
        w = self.width()
        y = self.verticalScrollBar().value()
        painter = QtGui.QPainter(self.viewport())
        painter.setClipRect(event.rect())
        pen = QtGui.QPen(QtCore.Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)
        for block in self.infoBlocks:
            block_y = block.position().y() - y
            painter.drawLine(0, block_y, w, block_y)
            
        for block0, block1, kind in self.changes:
            y1 = block0.position().y()
            y2 = block1.position().y()
            if y1 <= 0 or y2 <= 0:
                continue
            y1 -= y
            y2 -= y
            painter.fillRect(0, y1, w, y2 - y1, brushes[kind][0])
        del painter
        QtGui.QTextBrowser.paintEvent(self, event)        

        painter = QtGui.QPainter(self.viewport())
        painter.setClipRect(event.rect())
        for block0, block1, kind in self.changes:
            y1 = block0.position().y()
            y2 = block1.position().y()
            if y1 <= 0 or y2 <= 0:
                continue
            y1 -= y
            y2 -= y
            painter.setPen(colors[kind][1])
            painter.drawLine(0, y1, w, y1)
            if y1 != y2:
                painter.drawLine(0, y2 - 1, w, y2 - 1)
       


class DiffViewHandle(QtGui.QSplitterHandle):

    def __init__(self, parent=None):
        QtGui.QSplitterHandle.__init__(self, QtCore.Qt.Horizontal, parent)
        self.view = parent
        self.clear()
        
    def clear(self):
        self.changes = []
        self.infoBlocks = []

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setClipRect(event.rect())
        frame = QtGui.QApplication.style().pixelMetric(QtGui.QStyle.PM_DefaultFrameWidth)
        value1 = self.view.browsers[0].verticalScrollBar().value() - frame
        value2 = self.view.browsers[1].verticalScrollBar().value() - frame
        w = self.width()
        
        pen = QtGui.QPen(QtCore.Qt.black)
        pen.setWidth(2)
        painter.setPen(pen)
        for block0, block1 in self.infoBlocks:
            block0_y = block0.position().y() - value1
            block1_y = block1.position().y() - value2
            painter.drawLine(0, block0_y, w, block1_y)

        for blocka0, blockb0, blocka1, blockb1, kind in self.changes:
            ly1 = blocka0.position().y()
            ly2 = blocka1.position().y()
            ry1 = blockb0.position().y()
            ry2 = blockb1.position().y()
            if ly1 <= 0 or ly2 <= 0 or ry1 <= 0 or ry2 <= 0:
                continue

            ly1 -= value1
            ly2 -= value1 + 1
            ry1 -= value2
            ry2 -= value2 + 1

            polygon = QtGui.QPolygon(4)
            polygon.setPoints(0, ly1, w, ry1, w, ry2, 0, ly2)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(brushes[kind][0])
            painter.drawConvexPolygon(polygon)

            painter.setPen(colors[kind][1])
            painter.setRenderHints(QtGui.QPainter.Antialiasing, ly1 != ry1)
            painter.drawLine(0, ly1, w, ry1)
            painter.setRenderHints(QtGui.QPainter.Antialiasing, ly2 != ry2)
            painter.drawLine(0, ly2, w, ry2)
        del painter


class SidebySideDiffView(QtGui.QSplitter):
    """Widget to show differences in side-by-side format."""

    def __init__(self, parent=None):
        QtGui.QSplitter.__init__(self, QtCore.Qt.Horizontal, parent)
        self.setHandleWidth(30)

        titleFont = QtGui.QFont(self.font())
        titleFont.setPointSize(titleFont.pointSize() * 140 / 100)
        titleFont.setBold(True)
        
        self.monospacedFont = QtGui.QFont("Courier New, Courier",
                                     self.font().pointSize())
        metadataFont = QtGui.QFont(self.font())
        metadataFont.setPointSize(titleFont.pointSize() * 70 / 100)
        metadataLabelFont = QtGui.QFont(metadataFont)
        metadataLabelFont.setBold(True)
    
        self.monospacedFormat = QtGui.QTextCharFormat()
        self.monospacedFormat.setFont(self.monospacedFont)
        self.titleFormat = QtGui.QTextCharFormat()
        self.titleFormat.setFont(titleFont)
        self.metadataFormat = QtGui.QTextCharFormat()
        self.metadataFormat.setFont(metadataFont)
        self.metadataLabelFormat = QtGui.QTextCharFormat()
        self.metadataLabelFormat.setFont(metadataLabelFont)

        self.docs = (QtGui.QTextDocument(),
                     QtGui.QTextDocument())
        self.browsers = (DiffSourceView(self),
                         DiffSourceView(self))
        self.cursors = [QtGui.QTextCursor(doc) for doc in self.docs]
        
        for i, (browser, doc, cursor) in enumerate(zip(self.browsers, self.docs, self.cursors)):
            doc.setUndoRedoEnabled(False)
            doc.setDefaultFont(self.monospacedFont)
            
            self.setCollapsible(i, False)
            browser.setDocument(doc)
            self.addWidget(browser)
            
            format = QtGui.QTextCharFormat()
            format.setAnchorNames(["top"])
            cursor.insertText("", format)

        self.ignoreUpdate = False
        self.connect(self.browsers[0].verticalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.updateHandle1)
        self.connect(self.browsers[1].verticalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.updateHandle2)
        self.connect(self.browsers[0].horizontalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.syncHorizontalSlider1)
        self.connect(self.browsers[1].horizontalScrollBar(), QtCore.SIGNAL("valueChanged(int)"), self.syncHorizontalSlider2)

        self.rewinded = False
        
        self.lastModifiedLabel = gettext('Last modified:')
        self.statusLabel = gettext('Status:')
        self.kindLabel = gettext('Kind:')
        self.propertiesLabel = gettext('Properties:')
        
        self.image_exts = ['.'+str(i)
            for i in QtGui.QImageReader.supportedImageFormats()]
        
        config = QBzrGlobalConfig()
        self.show_intergroup_colors = config.get_user_option("diff_show_intergroup_colors") in ("True", "1")
    
    def clear(self):
        
        self.browsers[0].clear()
        self.browsers[1].clear()
        self.handle(1).clear()
        for doc in self.docs:
            doc.clear()
        self.update()
        
    def append_diff(self, paths, file_id, kind, status, dates,
                    present, binary, lines, groups, data, properties_changed):
        cursors = self.cursors
        for i in range(2):
            cursor = cursors[i]
            cursor.beginEditBlock()
            cursor.insertText(paths[i] or " ", self.titleFormat)    # None or " " => " "
            cursor.insertBlock()
            if present[i]:
                cursor.insertText(self.lastModifiedLabel, self.metadataLabelFormat)
                cursor.insertText(" %s, " % format_timestamp(dates[i]), self.metadataFormat)
                cursor.insertText(self.statusLabel, self.metadataLabelFormat)
                cursor.insertText(" %s, " % gettext(status), self.metadataFormat)
                cursor.insertText(self.kindLabel, self.metadataLabelFormat)
                cursor.insertText(" %s" % gettext(kind[i]), self.metadataFormat)
                if properties_changed:
                    cursor.insertText(", ", self.metadataFormat)
                    cursor.insertText(self.propertiesLabel, self.metadataLabelFormat)
                    cursor.insertText(" ", self.metadataFormat)
                    cursor.insertText(", ".join([p[i] for p in properties_changed]), self.metadataFormat)
            else:
                cursor.insertText(" ", self.metadataFormat)
            cursor.insertBlock()
            self.browsers[i].infoBlocks.append(cursor.block().layout())
        
        self.handle(1).infoBlocks.append((cursors[0].block().layout(),
                                          cursors[1].block().layout()))
            
        if not binary:
            for cursor in cursors:
                cursor.setCharFormat(self.monospacedFormat)
                cursor.insertBlock()
            changes = []
            
            def fix_last_line(lines):
                """Fix last line if there is no new line.

                @param  lines:  list of lines
                @return:    original lines if lastline is OK,
                            or new list with fixed last line.
                """
                if lines:
                    last = lines[-1]
                    if last and last[-1] not in ('\r', '\n'):
                        lines = lines[:-1] + [last+'\n']
                return lines
            
            if have_pygments:
                use_pygments = True
                try:
                    def getTokens(p, d, path):
                        if not p:
                            return []
                        lexer = get_lexer_for_filename(path)
                        return list(split_tokens_at_lines(lex(d, lexer)))
                    
                    display_lines = [getTokens(p, d, path)
                                     for p, d, path in zip(present,
                                                           data,
                                                           paths)]
                except ClassNotFound:
                    use_pygments = False
                    display_lines = [fix_last_line(l) for l in lines]
            else:
                use_pygments = False
                display_lines = [fix_last_line(l) for l in lines]
            
            def insertLine(cursor, line):
                if use_pygments:
                    for ttype, value in line:
                        cursor.insertText(value.rstrip('\n'),
                                          format_for_ttype(ttype,
                                                           QtGui.QTextCharFormat(self.monospacedFormat)))
                    
                    # Use this format for the new line char, so that all line
                    # heights are the same.
                    format = QtGui.QTextCharFormat()
                    format.setFont(self.monospacedFont)
                    format.setFontItalic (True)
                    cursor.insertText(" \n",format)
                else:
                    cursor.insertText(line)
            
            def insertIxs(ixs):
                for cursor, line, ix in zip(cursors, display_lines, ixs):
                    for l in line[ix[0]:ix[1]]:
                        insertLine(cursor, l)
            
            def modifyFormatForTag (format, tag):
                if tag == "replace":
                    format.setBackground(replacement_text_background)
                elif not tag == "equal":
                    if self.show_intergroup_colors:
                        format.setBackground(brushes[tag][0])
                    else:
                        format.setBackground(QtGui.QColor.fromRgb(180, 210, 250))
            
            split_words = re.compile(r"\w+|\n\r|\r\n|\W")
            def insertIxsWithChangesHighlighted(ixs):
                texts = ["".join(l[ix[0]:ix[1]]) for l, ix in zip(lines, ixs)]
                if use_pygments:
                    # This is what the pygments lexer does, so we need to do the
                    # same incase we have \r\n line endings.
                    texts = ["\n".join(t.splitlines()) for t in texts]
                
                texts = [split_words.findall(t) for t in texts]
                
                if use_pygments:
                    groups = ([], [])
                    for tag, i0, i1, j0, j1 in SequenceMatcher(None,
                                                                tuple(texts[0]),
                                                                tuple(texts[1]),
                                                                ).get_opcodes():
                        groups[0].append((tag, len("".join(texts[0][i0:i1]))))
                        groups[1].append((tag, len("".join(texts[1][j0:j1]))))
                    for cursor, ls, ix, g in zip(cursors, display_lines, ixs, groups):
                        tag, n = g.pop(0)
                        for l in ls[ix[0]:ix[1]]:
                            for ttype, value in l:
                                while value:
                                    format = format_for_ttype(ttype,
                                                QtGui.QTextCharFormat(self.monospacedFormat))
                                    modifyFormatForTag(format, tag)
                                    t = value[0:n]
                                    cursor.insertText(t.rstrip('\n'), format)
                                    if t.endswith('\n'):
                                        # Use this format for the new line char, so that all line
                                        # heights are the same.
                                        format = QtGui.QTextCharFormat()
                                        format.setFont(self.monospacedFont)
                                        format.setFontItalic (True)
                                        cursor.insertText(" \n",format)
                                    value = value[len(t):]
                                    n -= len(t)
                                    if n<=0:
                                        if g:
                                            tag, n = g.pop(0)
                                        else:
                                            # why would this happen?????
                                            tag = 'equal'
                                            n = len(value)
                else:
                    for tag, i0, i1, j0, j1 in SequenceMatcher(None,
                                                               tuple(texts[0]),
                                                               tuple(texts[1]),
                                                               ).get_opcodes():
                        format = QtGui.QTextCharFormat()
                        format.setFont(self.monospacedFont)
                        modifyFormatForTag(format, tag)
                        
                        cursors[0].insertText("".join(texts[0][i0:i1]),format)
                        cursors[1].insertText("".join(texts[1][j0:j1]),format)
                    
                    for cursor in cursors:
                        cursor.setCharFormat (self.monospacedFormat)

            
            for i, group in enumerate(groups):
                if i > 0:
                    block0 = [cursor.block().layout() for cursor in self.cursors]
                    for cursor in cursors:
                        cursor.insertBlock()
                    block1 = [cursor.block().layout() for cursor in self.cursors]
                    changes.append((block0[0], block0[1], block1[0], block1[1], 'blank'))
                linediff = 0
                for g in group:
                    tag = g[0]
                    # indexes
                    ixs = ((g[1], g[2]), (g[3], g[4]))
                    n = [ix[1]-ix[0] for ix in ixs]
                    if tag == "equal":
                        insertIxs(ixs)
                    else:
                        block0 = [cursor.block().layout() for cursor in self.cursors]
                        if tag == "replace":
                            insertIxsWithChangesHighlighted(ixs)
                        else:
                            insertIxs(ixs)
                        linediff += n[0] - n[1]
                        block1 = [cursor.block().layout() for cursor in self.cursors]
                        changes.append((block0[0], block0[1], block1[0], block1[1], tag))
                
                if linediff == 0:
                    continue
                if linediff < 0:
                    i0 = group[-1][2]
                    i1 = i0 - linediff
                    exlines = display_lines[0][i0:i1]
                    linediff = -linediff - len(exlines)
                    cursor = cursors[0]
                else:
                    j0 = group[-1][4]
                    j1 = j0 + linediff
                    exlines = display_lines[1][j0:j1]
                    linediff = linediff - len(exlines)
                    cursor = cursors[1]
                if use_pygments:
                    exlines.extend([((None,"\n"),)] * linediff)
                else:
                    exlines.extend(["\n"] * linediff)
                for l in exlines:
                    insertLine(cursor, l)
            
            self.browsers[0].changes.extend([(line[0], line[2], line[4]) for line in changes])
            self.browsers[1].changes.extend([(line[1], line[3], line[4]) for line in changes])
            self.handle(1).changes.extend(changes)
        else:
            heights = [0,0]
            is_images = [False, False]
            for i in range(2):
                if present[i]:
                    ext = file_extension(paths[i]).lower()
                    if ext in self.image_exts:
                        is_images[i] = True
                        image = QtGui.QImage()
                        image.loadFromData(data[i])
                        heights[i] = image.height() + 4 # QTextDocument seems to add 1 pixel when layouting the text
                        self.docs[i].addResource(QtGui.QTextDocument.ImageResource,
                                        QtCore.QUrl(file_id),
                                        QtCore.QVariant(image))
            
            max_height = max(heights)
            for i, cursor in enumerate(self.cursors):
                format = QtGui.QTextBlockFormat()
                format.setBottomMargin(max_height - heights[i])
                cursor.setBlockFormat(format)
                if present[i]:
                    if is_images[i]:
                        cursor.insertText("\n")
                        cursor.insertImage(file_id)
                    else:
                        cursor.insertText(gettext('[binary file]'))
                else:
                    cursor.insertText(" ")
                cursor.insertBlock(QtGui.QTextBlockFormat())
        
        for cursor in self.cursors:
            cursor.insertText("\n")
            cursor.endEditBlock()
        # check horizontal scrollbars and force both if scrollbar visible only at one side
        if (self.browsers[0].horizontalScrollBar().isVisible()
            or self.browsers[1].horizontalScrollBar().isVisible()):
            self.browsers[0].setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
            self.browsers[1].setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.update()

    def rewind(self):
        if not self.rewinded:
            self.rewinded = True
            self.browsers[0].scrollToAnchor("top")
            self.browsers[1].scrollToAnchor("top")

    def _syncSliders(self, slider1, slider2, value):
        m = slider1.maximum()
        if m:
            value = slider2.minimum() + slider2.maximum() * (value - slider1.minimum()) / m
            self.ignoreUpdate = True
            slider2.setValue(value)
            self.ignoreUpdate = False

    def updateHandle1(self, value):
        if not self.ignoreUpdate:
            slider1 = self.browsers[0].verticalScrollBar()
            slider2 = self.browsers[1].verticalScrollBar()
            self._syncSliders(slider1, slider2, value)
            self.handle(1).update()

    def updateHandle2(self, value):
        if not self.ignoreUpdate:
            slider1 = self.browsers[0].verticalScrollBar()
            slider2 = self.browsers[1].verticalScrollBar()
            self._syncSliders(slider2, slider1, value)
            self.handle(1).update()

    def syncHorizontalSlider1(self, value):
        if not self.ignoreUpdate:
            slider1 = self.browsers[0].horizontalScrollBar()
            slider2 = self.browsers[1].horizontalScrollBar()
            self._syncSliders(slider1, slider2, value)
            self.handle(1).update()

    def syncHorizontalSlider2(self, value):
        if not self.ignoreUpdate:
            slider1 = self.browsers[0].horizontalScrollBar()
            slider2 = self.browsers[1].horizontalScrollBar()
            self._syncSliders(slider2, slider1, value)
            self.handle(1).update()

    def createHandle(self):
        return DiffViewHandle(self)


class SimpleDiffView(QtGui.QTextBrowser):
    """Widget to show differences in unidiff format."""

    def __init__(self, parent=None):
        QtGui.QTextBrowser.__init__(self, parent)
        self.doc = QtGui.QTextDocument(parent)
        self.doc.setUndoRedoEnabled(False)
        self.setDocument(self.doc)
        option = self.doc.defaultTextOption()
        option.setWrapMode(QtGui.QTextOption.NoWrap)
        self.doc.setDefaultTextOption(option)
        self.rewinded = False
        self.cursor = QtGui.QTextCursor(self.doc)
        format = QtGui.QTextCharFormat()
        format.setAnchorNames(["top"])
        self.cursor.insertText("", format)
        monospacedFont = QtGui.QFont("Courier New, Courier",
                                     self.font().pointSize())
        self.monospacedFormat = QtGui.QTextCharFormat()
        self.monospacedFormat.setFont(monospacedFont)

        self.monospacedInsertFormat = QtGui.QTextCharFormat(self.monospacedFormat)
        self.monospacedInsertFormat.setForeground(QtGui.QColor(0, 136, 11))
        self.monospacedDeleteFormat = QtGui.QTextCharFormat(self.monospacedFormat)
        self.monospacedDeleteFormat.setForeground(QtGui.QColor(204, 0, 0))
    
        monospacedBoldFont = QtGui.QFont(monospacedFont)
        monospacedBoldFont.setBold(True)
    
        monospacedItalicFont = QtGui.QFont(monospacedFont)
        monospacedItalicFont.setItalic(True)
    
        self.monospacedBoldInsertFormat = QtGui.QTextCharFormat(self.monospacedInsertFormat)
        self.monospacedBoldInsertFormat.setFont(monospacedBoldFont)
        self.monospacedBoldDeleteFormat = QtGui.QTextCharFormat(self.monospacedDeleteFormat)
        self.monospacedBoldDeleteFormat.setFont(monospacedBoldFont)
    
        self.monospacedHeaderFormat = QtGui.QTextCharFormat()
        self.monospacedHeaderFormat.setFont(monospacedBoldFont)
        self.monospacedHeaderFormat.setBackground(QtGui.QColor(246, 245, 238))
        self.monospacedHeaderFormat.setForeground(QtGui.QColor(117, 117, 117))
    
        self.monospacedHunkFormat = QtGui.QTextCharFormat()
        self.monospacedHunkFormat.setFont(monospacedItalicFont)
        self.monospacedHunkFormat.setForeground(QtGui.QColor(153, 30, 199))

    def rewind(self):
        if not self.rewinded:
            self.rewinded = True
            self.scrollToAnchor("top")

    def append_diff(self, paths, file_id, kind, status, dates,
                    present, binary, lines, groups, data, properties_changed):
        self.cursor.beginEditBlock()
        path_info = paths[1] or paths[0]
        if status in ('renamed', 'renamed and modified'):
            path_info = paths[0] + ' => ' + paths[1]
        kind_info = kind[0] or kind[1]
        self.cursor.insertText("=== %s %s %s" % (gettext(status),
            gettext(kind_info), path_info),
            self.monospacedHeaderFormat)
        if properties_changed:
            prop_str = []
            for pair in properties_changed:
                if None not in pair:
                    prop_str.append("%s to %s" % pair)
            if prop_str:
                self.cursor.insertText(
                    " (properties changed: %s)" % (", ".join(prop_str)))
        self.cursor.insertText("\n")
        
        # GNU Patch uses the epoch date to detect files that are being added
        # or removed in a diff.
        EPOCH_DATE = '1970-01-01 00:00:00 +0000'
        for i in range(2):
            if present[i]:
                dates[i] = timestamp.format_patch_date(dates[i])
            else:
                paths[i] = paths[(i+1)%2]
                dates[i] = EPOCH_DATE
        
        if not binary:
            self.cursor.insertText('--- %s %s\n' % (paths[0], dates[0]),
                                      self.monospacedBoldInsertFormat)
            self.cursor.insertText('+++ %s %s\n' % (paths[1], dates[1]),
                                   self.monospacedBoldDeleteFormat)

            def fix_last_line(lines):
                """Fix last line if there is no new line.

                @param  lines:  original list of lines
                @return:    lines if lastline is OK,
                            or new list with fixed last line.
                """
                if lines:
                    last = lines[-1]
                    if last and last[-1] not in ('\r', '\n'):
                        last += ('\n' +
                                 gettext('\\ No newline at end of file') +
                                 '\n')
                        lines = lines[:-1] + [last]
                return lines

            a = fix_last_line(lines[0])
            b = fix_last_line(lines[1])

            for i, group in enumerate(groups):
                i0, i1, j0, j1 = group[0][1], group[-1][2], group[0][3], group[-1][4]
                self.cursor.insertText("@@ -%d,%d +%d,%d @@\n" % (i0+1, i1-i0, j0+1, j1-j0), self.monospacedHunkFormat)
                for tag, i0, i1, j0, j1 in group:
                    ni = i1 - i0
                    nj = j1 - j0
                    if tag == "equal":
                        text = "".join(" " + l for l in a[i0:i1])
                        self.cursor.insertText(text, self.monospacedFormat)
                    else:
                        text = "".join("-" + l for l in a[i0:i1])
                        self.cursor.insertText(text, self.monospacedDeleteFormat)
                        text = "".join("+" + l for l in b[j0:j1])
                        self.cursor.insertText(text, self.monospacedInsertFormat)
        else:
            self.cursor.insertText("Binary files %s %s and %s %s differ\n" % \
                                   (paths[0], dates[0], paths[1], dates[1]))
        self.cursor.insertText("\n")
        self.cursor.endEditBlock()
        self.update()
