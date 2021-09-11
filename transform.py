#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""transform.py

Copyright 2021 DMeurisse <info@mchobby.be>

Decode & store the transformation data as described in the transformation-encoding.odt

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

import re

RE_QTY_AND_REF = "((?:\+|-)(?:\d*|\d*\.?\d*))\*(.*)" # "([\+|-]\d*|\d*\.?\d*)\*(.*)"

re_qty_and_ref = re.compile( RE_QTY_AND_REF )

class TransformList( list ):
	""" A Tote Bag is a Basket """
	def __init__( self ):
		self._comments = [] # of strings
		self._multiplier = 1

	def clear( self ):
		""" Clear all the items in the list """
		del( self[:] )
		self._comments = []

	#def get_item( self, product ):
	#	""" Retreive an article from the tote_bag if it exists inside """
	#	for _item in self:
	#		if _item.product.id == product.id:
	#			return _item # return a ToteItem
	#	return None

	def parse_text( self, str ):
		self.parse_list( sl = str.split('\n') )

	def parse_list( self, sl ): # Parse a list of strings
		self.clear()
		for s in sl:
			s = s.replace('\t','').replace('\r','').strip()
			# Just an empty line?
			if len(s)==0:
				continue
			# Just a comment line starting with ?
			if s[0]==';':
				self.comments.append(s[1:])
				continue
			# Has comment ; ?
			comment = ''
			if ';' in s:
				__s = s.split(';')
				comment = __s[1].strip()
				s = __s[0].strip()
			# Décomposer
			g = re_qty_and_ref.match( s )
			if g==None:
				raise Exception("@DATA.[Transform]: Invalid syntax for %s" % s )
				# continue
			# Qty and reference
			sQty = g.groups()[0]
			sRef = g.groups()[1]
			# Append it
			self.add_line( float(sQty.strip()), sRef.strip(), comment )


	def add_line( self, qty, reference, comment='' ):
		r = TransformLine( self, qty, reference, comment )
		self.append( r )
		return r

	@property
	def comments( self ):
		return self._comments

	@property
	def multiplier( self ):
		return self._multiplier

	@multiplier.setter
	def multiplier( self, value ):
		self._multiplier = value

	@ property
	def sourcing( self ):
		""" List of items composing the product """
		return [ item for item in self if item.qty <= 0]

	@ property
	def creating( self ):
		""" product created (with multiplier!) """
		for item in self:
			if item.qty>0:
				return item
		# Can't reach here
		raise Exception( 'No creating entry in transform list (need an entry with + sign.)!')


class TransformLine( object ):
	# _owner : owner list
	# qty : quantity (+ final product to add, - part to remove)
	# reference : product reference as encoded in the TRANSFORM section
	# _product : None or resolved product object (once resolved)
	# comment : transformantion comment
	__slots__ = '_owner', 'qty', 'reference', '_product', 'comment'


	def __init__( self, owner, qty, reference, comment='' ):
		""" owner is a TransformList owning the instance """
		self._owner = owner
		self.qty = qty
		self.reference = reference # Product reference
		self._product = None
		self.comment = comment

	def __repr__( self ):
		return '<%s : %s * %s>' % (self.__class__.__name__, self.qty, self.reference)

	@property
	def as_text( self ):
		""" Return human frienddly description of the content """
		return "%4.2f x %-30s ; %s" % (self.qty, self.reference, self.comment )

	@property
	def required_qty( self ):
		""" Quantity required depending on the Transform multiplier """
		return self.qty * self._owner._multiplier

if __name__=='__main__':
	transform = TransformList()
	transform.parse_text( """+1*GRL-PYBOARD-UNIPI
-1*IT-PCB-UNIPI-PYBOARD
-1*IT-DIODE-SB560
-1*CON-IDC-BOX-2x5
-1*PIN-HEAD-NORM-2
-1*IT-SMALL-TACT
-1*MCP23017
-1*RASP-STACK-HEAD26
""" )
	print( 'Comment: %s' % transform.comments )
	transform.multiplier = 20
	print( "multiplier : %i" % transform.multiplier )
	for item in transform:
		print( "%6.2f : %-30s : %s" % (item.required_qty, item.reference, item.comment) )
