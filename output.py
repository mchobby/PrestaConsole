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

class PrestaOut( object ):
	""" Class to manage the ouput of data to various streams """

	def __init__( self ):
		self.fh = None # File handle
		self.filename = ''  #  filename for the file operation handling
		self.stdout_active = True # writeln display string on the terminal

	def writeln( self, obj ):
		#print( obj.decode( sys.stdout.encoding ) )
		# Write to std_out
		if self.stdout_active:
			print( obj )
		# Write to file
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
		self.fh = open( self.filename, 'w' )
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
