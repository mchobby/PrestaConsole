#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
""" output.py - output for prestashop console application

Copyright 2018 DMeurisse <info@mchobby.be>

Prepare a shopping basket (or Tote Bag) for several manipulation

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
MA 02110-1301, USA.
"""

import tempfile
import codecs
import json
import datetime

class PrestaOut( object ):
	""" Class to manage the ouput of data to various streams """

	def __init__( self ):
		self.fh = None # File handle
		self.filename = ''  #  filename for the file operation handling
		self.stdout_active = True # writeln display string on the terminal
		self.carbon_copy = None # used to keep a copy of the writeln() calls

	def writeln( self, obj ):
		#print( obj.decode( sys.stdout.encoding ) )
		# Write to std_out
		if self.stdout_active:
			print( obj )
		# Keep a carbon copy of the test ?
		if self.carbon_copy != None:
			# Safe Adding... for all situations
			try:
				self.carbon_copy.append( obj )
			except:
				try:
					self.carbon_copy.append( str(obj) )
				except:
					pass # Unable to add... do no report error

		# Write to file ?
		if self.fh != None:
			self.fh.write( obj )
			self.fh.write(  '\n' )

	def write_lines( self, lines ):
		""" just write all the lines contained in the list """
		for l in lines:
			self.writeln( l )

	def open_temp_file( self ):
		""" Open temportary file to write output content.
		    Later, this file will be used to content to the printer :-)

			:returns: the openned temporary filename
		"""
		if self.fh:
			return self.filename

		# Create a new temporary file
		self.filename = tempfile.mktemp( '-console-print.txt' )
		self.fh = codecs.open( self.filename, 'w', 'utf-8' )
		return self.filename

	def close_temp_file( self ):
		""" just close the temporary file.

			:returns: the just closed temporary filename. """
		if not self.fh:
			raise Exception( 'No printer file open!' )
		_r = self.filename
		self.fh.close()
		self.fh = None
		self.filename = None
		return _r

	def set_carbon_copy( self, activate=True ):
		""" Activate or deactive the carbon_copy """
		if activate:
			self.carbon_copy = []
		else:
			self.carbon_copy = None

	def reset_carbon_copy( self ):
		""" reinitialize the carbon_copy """
		self.carbon_copy = []

	def save_carbon_copy( self, filename ):
		""" Save the carbon copy to a text file """
		if self.carbon_copy:
			with open( filename, "w+") as f:
				for line in self.carbon_copy:
					try:
						f.write( line )
					except:
						try:
							f.write( str(line) )
						except:
							f.write( '...' )
					f.write( '\r\n' )

class SerialNumberData():
	__slots__ = ('scan_date', 'order_id','order_date', 'product_id','product_ref','sn', 'remark' )

	def __init__(self, order, product, sn, remark=None ):
		self.scan_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Same format as object
		self.order_id = order.id
		self.order_date = order.date_add
		self.product_id = product.id_product
		self.product_ref = product.reference
		self.sn = sn
		self.remark = remark

# subclass JSONEncoder
class SerialNumberDataEncoder(json.JSONEncoder):
	def default(self, o):
		return [ o.__class__.__name__, o.__dict__ ]

class SerialNumberLog( object ):
	""" Class to manage Serial Number Logs """

	def __init__( self ):
		self.items = None
		self.__idx = -1 # Iterator index
		self.reset()

	def reset( self ):
		self.items = []

	def __len__( self ):
		return len(self.items)

	def __iter__(self):
		return iter( self.items )

	#def __next__(self):
	#	self.__idx += 1
	#	if self.__idx >= len(self.items):
	#		raise StopIteration
	#	else:
	#		return self.items[self.__idx] # returns a SerialNumberData

	def append( self, order, product, sn, remark=None ):
		self.items.append( SerialNumberData( order, product, sn, remark ) )

	def save( self, filename ):
		""" Save the serials to a JSON file (only if something to be saved)"""
		if len( self.items )==0:
			return
		with codecs.open( filename, 'w', encoding='utf8' ) as f:
			json.dump( self.items, f , indent=4, cls=SerialNumberDataEncoder )

	def load ( self, filename ):
		""" Reload the serials from the saved JSON file """
		pass
