##############################################################################
#
# Copyright (c) 2003-2005 Nexedi SARL and Contributors. All Rights Reserved.
#                         Kevin DELDYCKE    <kevin@nexedi.com>
#                         Guillaume MICHON  <guillaume@nexedi.com>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

from Products.PythonScripts.Utility import allow_class
from ZPublisher.HTTPRequest import FileUpload
from xml.dom.ext.reader import PyExpat
from xml.dom import Node
from AccessControl import ClassSecurityInfo
from Globals import InitializeClass
from zipfile import ZipFile
from zLOG import LOG
import imghdr
import random



class CorruptedOOoFile(Exception): pass



class OOoParser:
  """
    General purpose tools to parse and handle OpenOffice v1.x documents.
  """


  # Declarative security
  security = ClassSecurityInfo()


  security.declarePrivate('__init__')
  def __init__(self):
    # Create the PyExpat reader
    self.reader = PyExpat.Reader()
    self.oo_content_dom = None
    self.oo_styles_dom  = None
    self.oo_files = {}
    self.pictures = {}
    self.ns = {}


  security.declareProtected('Import/Export objects', 'openFile')
  def openFile(self, file_descriptor):
    """
      Load all files in the zipped OpenOffice document
    """
    # Try to unzip the Open Office doc
    try:
      oo_unzipped = ZipFile(file_descriptor, mode="r")
    except:
      raise CorruptedOOoFile
    # Test the integrity of the file
    if oo_unzipped.testzip() != None:
      raise CorruptedOOoFile

    # List and load the content of the zip file
    for name in oo_unzipped.namelist():
      self.oo_files[name] = oo_unzipped.read(name)
    oo_unzipped.close()

    # Get the main content and style definitions
    self.oo_content_dom = self.reader.fromString(self.oo_files["content.xml"])
    self.oo_styles_dom  = self.reader.fromString(self.oo_files["styles.xml"])

    # Create a namespace table
    doc_ns = self.oo_styles_dom.getElementsByTagName("office:document-styles")
    for i in range(doc_ns[0].attributes.length):
        if doc_ns[0].attributes.item(i).nodeType == Node.ATTRIBUTE_NODE:
            name = doc_ns[0].attributes.item(i).name
            if name[:5] == "xmlns":
                self.ns[name[6:]] = doc_ns[0].attributes.item(i).value


  security.declarePublic('getPicturesMapping')
  def getPicturesMapping(self):
    """
      Return a dictionnary of all pictures in the document
    """
    if len(self.pictures) <= 0:
      for file_name in self.oo_files:
        raw_data = self.oo_files[file_name]
        pict_type = imghdr.what(None, raw_data)
        if pict_type != None:
          self.pictures[file_name] = raw_data
    return self.pictures


  security.declarePublic('getContentDom')
  def getContentDom(self):
    """
      Return the DOM tree of the main OpenOffice content
    """
    return self.oo_content_dom


  security.declarePublic('getSpreadsheetsDom')
  def getSpreadsheetsDom(self, include_embedded=False):
    """
      Return a list of DOM tree spreadsheets (optionnaly included embedded ones)
    """
    spreadsheets = []
    spreadsheets = self.getPlainSpreadsheetsDom()
    if include_embedded == True:
      spreadsheets += self.getEmbeddedSpreadsheetsDom()
    return spreadsheets


  security.declarePublic('getSpreadsheetsMapping')
  def getSpreadsheetsMapping(self, include_embedded=False, no_empty_lines=False, normalize=True):
    """
      Return a list of table-like spreadsheets (optionnaly included embedded ones)
    """
    tables = {}
    tables = self.getPlainSpreadsheetsMapping(no_empty_lines, normalize)
    if include_embedded == True:
      embedded_tables = self.getEmbeddedSpreadsheetsMapping(no_empty_lines, normalize)
      tables = self._getTableListUnion(tables, embedded_tables)
    return tables


  security.declarePublic('getPlainSpreadsheetsDom')
  def getPlainSpreadsheetsDom(self):
    """
      Retrieve every spreadsheets from the document and get they DOM tree
    """
    spreadsheets = []
    # List all spreadsheets
    for table in self.oo_content_dom.getElementsByTagName("table:table"):
      spreadsheets.append(table)
    return spreadsheets


  security.declarePublic('getPlainSpreadsheetsMapping')
  def getPlainSpreadsheetsMapping(self, no_empty_lines=False, normalize=True):
    """
      Return a list of plain spreadsheets from the document and transform them as table
    """
    tables = {}
    for spreadsheet in self.getPlainSpreadsheetsDom():
      new_table = self.getSpreadsheetMapping(spreadsheet, no_empty_lines, normalize)
      if new_table != None:
        tables = self._getTableListUnion(tables, new_table)
    return tables


  security.declarePublic('getEmbeddedSpreadsheetsDom')
  def getEmbeddedSpreadsheetsDom(self):
    """
      Return a list of existing embedded spreadsheets in the file as DOM tree
    """
    spreadsheets = []
    # List all embedded spreadsheets
    emb_objects = self.oo_content_dom.getElementsByTagName("draw:object")
    for embedded in emb_objects:
      document = embedded.getAttributeNS(self.ns["xlink"], "href")
      if document:
        try:
          object_content = self.reader.fromString(self.oo_files[document[3:] + '/content.xml'])
          for table in object_content.getElementsByTagName("table:table"):
            spreadsheets.append(table)
        except:
          pass
    return spreadsheets


  security.declarePublic('getEmbeddedSpreadsheetsMapping')
  def getEmbeddedSpreadsheetsMapping(self, no_empty_lines=False, normalize=True):
    """
      Return a list of embedded spreadsheets in the document as table
    """
    tables = {}
    for spreadsheet in self.getEmbeddedSpreadsheetsDom():
      new_table = self.getSpreadsheetMapping(spreadsheet, no_empty_lines, normalize)
      if new_table != None:
        tables = self._getTableListUnion(tables, new_table)
    return tables


  security.declarePublic('getSpreadsheetMapping')
  def getSpreadsheetMapping(self, spreadsheet=None, no_empty_lines=False, normalize=True):
    """
      This method convert an OpenOffice spreadsheet to a simple table.
      This code is based on the oo2pt tool (http://cvs.sourceforge.net/viewcvs.py/collective/CMFReportTool/oo2pt).
    """
    if spreadsheet == None or spreadsheet.nodeName != 'table:table':
      return None

    table = []

    # Get the table name
    table_name = spreadsheet.getAttributeNS(self.ns["table"], "name")

    # Scan table and store usable informations
    for line in spreadsheet.getElementsByTagName("table:table-row"):

      # TODO : to the same as cell about abusive repeated lines

      line_group_found = line.getAttributeNS(self.ns["table"], "number-rows-repeated")
      if not line_group_found:
        lines_to_repeat = 1
      else:
        lines_to_repeat = int(line_group_found)

      for i in range(lines_to_repeat):
        table_line = []

        # Get all cells
        cells = line.getElementsByTagName("table:table-cell")
        cell_index_range = range(len(cells))

        for cell_index in cell_index_range:
          cell = cells[cell_index]

          # If the cell as no child, cells have no content
          # And if the cell is the last of the row, we don't need to add it to the line
          # So we can go to the next line (= exit this cells loop)
          #
          # I must do this test because sometimes the following cell group
          #   can be found in OOo documents : <table:table-cell table:number-columns-repeated='246'/>
          # This is bad because it create too much irrevelent content that slow down the process
          # So it's a good idea to break the loop in this case
          if cell.childNodes.length == 0 and cell_index == cell_index_range[-1]:
            break

          # Handle cells group
          cell_group_found = cell.getAttributeNS(self.ns["table"], "number-columns-repeated")
          if not cell_group_found:
            cells_to_repeat = 1
          else:
            cells_to_repeat = int(cell_group_found)

          # Ungroup repeated cells
          for j in range(cells_to_repeat):
            # Get the cell content
            cell_text = None
            text_tags = cell.getElementsByTagName("text:p")
            for text in text_tags:
              for k in range(text.childNodes.length):
                child = text.childNodes[k]
                if child.nodeType == Node.TEXT_NODE:
                  if cell_text == None:
                    cell_text = ''
                  cell_text += child.nodeValue

            # Add the cell to the line
            table_line.append(cell_text)

        # Delete empty lines if needed
        if no_empty_lines:
          empty_cell = 0
          for table_cell in table_line:
            if table_cell == None:
              empty_cell += 1
          if empty_cell == len(table_line):
            table_line = None

        # Add the line to the table
        if table_line != None:
          table.append(table_line)

    # Reduce the table to the minimum
    new_table = self._getReducedTable(table)

    # Get a homogenized table
    if normalize:
      table_size = self._getTableSizeDict(new_table)
      new_table = self._getNormalizedBoundsTable( table  = new_table
                                                , width  = table_size['width']
                                                , height = table_size['height']
                                                )
    return {table_name: new_table}


  security.declarePrivate('_getReducedTable')
  def _getReducedTable(self, table):
    """
      Reduce the table to its minimum size
    """
    empty_lines = 0
    no_more_empty_lines = 0

    # Eliminate all empty cells at the ends of lines and columns
    # Browse the table starting from the bottom for easy empty lines count
    for line in range(len(table)-1, -1, -1):
      empty_cells = 0
      line_content = table[line]
      for cell in range(len(line_content)-1, -1, -1):
        if line_content[cell] in ('', None):
          empty_cells += 1
        else:
          break

      if (not no_more_empty_lines) and (empty_cells == len(line_content)):
        empty_lines += 1
      else:
        line_size = len(line_content) - empty_cells
        table[line] = line_content[:line_size]
        no_more_empty_lines = 1

    table_height = len(table) - empty_lines

    return table[:table_height]


  security.declarePrivate('_getTableSizeDict')
  def _getTableSizeDict(self, table):
    """
      Get table dimension as dictionnary contain both height and width
    """
    max_cols = 0
    for line_index in range(len(table)):
      line = table[line_index]
      if len(line) > max_cols:
        max_cols = len(line)

    return { 'width' : max_cols
           , 'height': len(table)
           }


  security.declarePrivate('_getNormalizedBoundsTable')
  def _getNormalizedBoundsTable(self, table, width=0, height=0):
    """
      Add necessary cells and lines to obtain given bounds
    """
    while height > len(table):
      table.append([])
    for line in range(height):
      while width > len(table[line]):
        table[line].append(None)
    return table


  security.declarePrivate('_getTableListUnion')
  def _getTableListUnion(self, list1, list2):
    """
      Coerce two dict containing tables structures.
      We need to use this method because a OpenOffice document can hold
        several embedded spreadsheets with the same id. This explain the
        use of random suffix in such extreme case.
    """
    for list2_key in list2.keys():
      # Generate a new table ID if needed
      new_key = list2_key
      while new_key in list1.keys():
        new_key = list2_key + '_' + str(random.randint(1000,9999))
      list1[new_key] = list2[list2_key]
    return list1



InitializeClass(OOoParser)
allow_class(OOoParser)
