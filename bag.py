#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""bag.py

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

import re
import xml.etree.cElementTree as etree

RE_ADD_REMOVE_SEVERAL_ID= "^(\+|\-)(\d+)\*(\d+)$"          # +3*125 OU -4*1024
RE_ADD_REMOVE_SEVERAL_TEXT = "^(\+|\-)(\d+)\*([a-zA-Z].+)$" # +3*gsm OU +3*g125 OU -2xdemo
RE_ADD_REMOVE_ID           = "^(\+|\-)(\d+)$"              # +123   OU -123

re_add_remove_several_id = re.compile( RE_ADD_REMOVE_SEVERAL_ID )
re_add_remove_several_text = re.compile( RE_ADD_REMOVE_SEVERAL_TEXT )
re_add_remove_ID = re.compile( RE_ADD_REMOVE_ID )

class ToteBag( list ):
	""" A Tote Bag is a Basket """

	def clear( self ):
		""" Clear all the items in the list """
		del( self[:] )
	
	def get_tote_item( self, product ):
		""" Retreive an article from the tote_bag if it exists inside """
		for _item in self:
			if _item.product.id == product.id:
				return _item # return a ToteItem
		return None

	def add_product( self, qty, product ):
		""" Add the given quantity of an article to bag and return the tote_item.
		    :param product: a product object """
		item = self.get_tote_item( product )
		if item:
			item.qty = item.qty + qty
		elif qty>0: # create one only if qty > 0
			item = ToteItem( self )
			item.qty = qty
			item.product = product
			self.append( item )

		# Remove the item form the bag if qty <= 0
		if item and item.qty <= 0:
			self.remove( item )
			item=None
		return item

	def is_bag_command( self, sCmd ):
		""" Check if the sCmd string contains a bag manipulation command.
				
			add/remove IDs       with +3*125 or -4*1024
            add/remove TEXT      with +3*gsm or +3*g125 or -2*demo
            add/remove single ID with +123   or -123
		 """
		return ( re_add_remove_several_id.match( sCmd ) != None ) or \
		 	   ( re_add_remove_several_text.match( sCmd ) != None ) or \
		 	   ( re_add_remove_ID.match( sCmd ) != None )

	def manipulate( self, cachedphelper, sCmd ):
		""" Manipulate the content of the bag based on the sCmd content 

		    :returns: list of messages"""
		# -- ADD/REMOVE ID -------------------------------------
		g = re_add_remove_ID.match( sCmd )
		if g:
			
			# Qty and ID
			sign = g.groups()[0]
			id = int( g.groups()[1] )
			# locate product
			p = cachedphelper.products.product_from_id( id )
			if p:
				qty = 1 if sign=='+' else -1
				_r = self.add_product( qty, p )
				return [ ('%s in bag' % _r.as_text) if _r else ('%s REMOVED from bag.' %  p.reference) ]
			else:
				return ['[ERROR] ID!' ] 

		# -- ADD/REMOVE SEVERAL ID --------------------------
		g = re_add_remove_several_id.match( sCmd )
		if g:
			
			# Qty and ID
			sign = g.groups()[0] 
			qty  = int( g.groups()[1] )
			id  = int( g.groups()[2] ) 
			# locate product
			p = cachedphelper.products.product_from_id( id )
			if p:
				qty = qty if sign=='+' else -1*qty
				_r = self.add_product( qty, p )
				return [ ('%s in bag' % _r.as_text) if _r else ('%s REMOVED from bag.' %  p.reference) ]
			else:
				return ['[ERROR] ID!'] 

		# -- ADD/REMOVE SEVERAL Text -------------------------
		g = re_add_remove_several_text.match( sCmd )
		if g:
			# Qty and ID
			sign = g.groups()[0] 
			qty  = int( g.groups()[1] )
			txt  = g.groups()[2] 
			# locate product
			lst = cachedphelper.products.search_products_from_partialref( txt )
			if len(lst) == 1:
				qty = qty if sign=='+' else -1*qty
				_r = self.add_product( qty, lst[0] )
				return [ ('%s in bag' % _r.as_text) if _r else ('%s REMOVED from bag.' %  lst[0].reference) ]
			else:
				return ['bag NOT updated!']+list( \
					       [ '%7i : %s - %s' % (item.product_data.id,item.product_data.reference.ljust(30),item.product_data.name) for \
					         item in cachedphelper.search_products_from_partialref( txt, include_inactives = False ) \
					       ] )

	def export_to_xmltree( self, decimal_separator=',' ):
		""" Export the content of a Tote Bag into an XML structure """
		root = etree.Element( 'tote-bag' )
		for tote_item in self:
			item = etree.SubElement( root, "tote-item" )

	        # __slots__ = ["id", "active", "reference", "name", "wholesale_price",
	        #     "price", "id_supplier", "id_category_default", "advanced_stock_management", 
	        #     "available_for_order", "ean13" ]

			# add values for the Row
			etree.SubElement( item, "id" ).text = "%s" % tote_item.product.id
			etree.SubElement( item, "libelle" ).text = "%s" % tote_item.product.name
			etree.SubElement( item, "reference" ).text = "%s" % tote_item.product.reference
			etree.SubElement( item, "quantite"  ).text = "%s" % tote_item.qty	
			etree.SubElement( item, "PVHT_par_P").text = ("%s" % tote_item.product.price).replace('.', decimal_separator)	
			etree.SubElement( item, "Total_PVHT").text = '---'
			etree.SubElement( item, "PAHT_P"    ).text = ("%s" % tote_item.product.wholesale_price).replace('.', decimal_separator)	 
			etree.SubElement( item, "Reduction" ).text = "0 %"
			etree.SubElement( item, "PV2_PV_Red").text = '---'	
			etree.SubElement( item, "Marge"     ).text = '---'	
			etree.SubElement( item, "Total_PAHT").text = '---'	
			etree.SubElement( item, "Total_PV2"	).text = '---' 
			etree.SubElement( item, "TVA"       ).text = 'todo'	
			etree.SubElement( item, "Total_TTC" ).text = '---'
		return root

	def import_from_xmltree( self, cachedphelper, xml_root ):
		""" Enumerate XML tree and reload products in the Tote-Bag

			:param cachedphelper: used to retreives the product reference
			:param xml_root: xml root node 
		"""
		for item in xml_root.iter('tote-item'):
			ref = item.find('reference').text # référence produit
			id  = int( item.find('id').text )
			qty = int( item.find('quantite').text )
			# Find the produt
			p = cachedphelper.products.product_from_id( id )
			if p:
				self.add_product( qty, p )
			else:
				raise Exception( '[ERROR] unable to reload product ID %i for reference %s' %(id,ref) )


class ToteItem( object ):
	__slots__ = '_bag', 'qty', 'product'

	def __init__( self, bag ):
		""" bag is the owner (a ToteBag) owning the instance """
		self._bag = bag

	def __str__( self ):
		return '<%s product.id %s, qty %s>' % (self.__class__.__name__, self.product.id, self.qty)

	@property 
	def as_text( self ):
		""" Return human frienddly description of the content """
		return "%3i x %-30s" % (self.qty, self.product.reference )
