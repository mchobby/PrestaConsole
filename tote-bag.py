#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""tote-bag.py

derivated from prestaconsole.py project
  
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

from prestaapi import PrestaHelper, CachedPrestaHelper
from prestaapi.prestahelpertest import run_prestahelper_tests
from config import Config
from pprint import pprint
import logging
import sys
import signal
import re
import traceback
import xml.etree.cElementTree as etree

from Tkinter import *
import Tkinter, Tkconstants, tkFileDialog
 


# from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter

RE_ADD_REMOVE_SEVERAL_ID= "^(\+|\-)(\d+)\*(\d+)$"          # +3*125 OU -4*1024
RE_ADD_REMOVE_SEVERAL_TEXT = "^(\+|\-)(\d+)\*([a-zA-Z].+)$" # +3*gsm OU +3*g125 OU -2xdemo
RE_ADD_REMOVE_ID           = "^(\+|\-)(\d+)$"              # +123   OU -123
RE_SEARCH_ID               = "^(\d+)$"                     # (search ) 123  
RE_SEARCH_TEXT             = "^([a-zA-Z].+)|\/(-.*)$"      # (search ) demo  OU /-GSM  OU a125 
RE_COMMAND                 = "^\+([a-zA-Z])$"              # (command) +r OU +s 

re_add_remove_several_id = re.compile( RE_ADD_REMOVE_SEVERAL_ID )
re_add_remove_several_text = re.compile( RE_ADD_REMOVE_SEVERAL_TEXT )
re_add_remove_ID = re.compile( RE_ADD_REMOVE_ID )
re_search_id     = re.compile( RE_SEARCH_ID )
re_search_text   = re.compile( RE_SEARCH_TEXT )
re_command       = re.compile( RE_COMMAND )

def catch_ctrl_C(sig,frame):
    print "Il est hors de question d'autoriser la sortie sauvage!"
signal.signal(signal.SIGINT, catch_ctrl_C)

#PRINTER_SHORTLABEL_QUEUE_NAME = 'zebra-raw'   # Small labels 25x30mm
#PRINTER_LARGELABEL_QUEUE_NAME = 'zebra-raw-l' # Large labels 25x70mm
#PRINTER_ENCODING = 'cp850'

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

# LABEL Size is stored into the article reference of the "PARAMS" supplier.
ID_SUPPLIER_PARAMS = None

class ToteBag( list ):
	""" A Tote Bag is a Basket """
	
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


class ToteItem( object ):
	__slots__ = '_bag', 'qty', 'product'

	def __init__( self, bag ):
		""" bag is the owner (a ToteBag) owning the instance """
		self._bag = bag

	def __str__( self ):
		return '<%s product.id %s, qty %s>' % (self.__class__.__name__, self.product.id, self.qty)

def list_products( cachedphelper, key ):
	""" Search for a product base on its partial reference code + list them """
	assert isinstance( key, str ), 'Key must be a string'
	if len( key ) < 3:
		print( 'searching product requires at least 3 characters' )
		return
	
	result = cachedphelper.products.search_products_from_partialref( key, include_inactives = True )
	for item in result:
		print( '%7i : %s - %s' % (item.id,item.reference.ljust(30),item.name) )

def list_product( cachedphelper, id ):
	""" Search for a product base on its ID + list it """
	assert isinstance( id, int ), 'in must be a int'
	
	item = cachedphelper.products.product_from_id( id_product = id  )
	if item:
		print( '%7i : %s - %s' % (item.id,item.reference.ljust(30),item.name) )

def view_bag( cachedphelper, bag, max_row=None, desc=False ):
	""" View bag content with max display, display ascending (or descending) """
	assert isinstance( bag, ToteBag )
	if len( bag )==0:
		print( '> (empty)' )
	for idx, item in enumerate( reversed(bag) if desc else bag ):
		if max_row and (idx>=max_row):
			print( '> ...' ) # indicates the presence of more items in the bag
			break;
		print( '> %3i x %7i : %s - %s' % (item.qty, item.product.id,item.product.reference.ljust(30),item.product.name) ) 

def export_to_xmltree( tote_bag, decimal_separator=',' ):
	""" Export the content of a Tote Bag into an XML structure """
	root = etree.Element( 'tote-bag' )
	for tote_item in tote_bag:
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

def import_from_xmltree( cachedphelper, tote_bag, xml_root ):
	""" Enumerate XML tree and reload products in the Tote-Bag """
	for item in xml_root.iter('tote-item'):
		ref = item.find('reference').text # référence produit
		id  = int( item.find('id').text )
		qty = int( item.find('quantite').text )
		# Find the produt
		p = cachedphelper.products.product_from_id( id )
		if p:
			tote_bag.add_product( qty, p )
		else:
			print( '[ERROR] unable to reload product ID %i for reference %s' %(id,ref) )

def get_product_params_dic( cachedpHelper,id_product ):
	""" Locate the product parameter stored in the PARAMS supplier
	    reference on the product. The reference is coded as follow
	    param1:value1,param2:value2 """
	
	# If this special PARAMS supplier is not yet identified then
	#   not possible to locate the special product parameter
	#   stored there 
	if ID_SUPPLIER_PARAMS == None:
		return {}
	
	reference = ''
	try:	
		reference = cachedpHelper.product_suppliers.reference_for( id_product, ID_SUPPLIER_PARAMS )
		# print( 'reference: %s' % reference )
		if len(reference )==0:
			return {}
		
		result = {}
		lst = reference.split(',')
		for item in lst:
			vals = item.split(':')
			if len( vals )!= 2:
				raise Exception( 'a parameter must have 2 parts!' )
			result[vals[0]] = vals[1]
		
		return result
		
	except Exception as e:
		print( 'Error while processing param %s with message %s ' % (reference,str(e)) )	
		return {}

def help():
	""" Display Help """		
	print( '== HELP %s' % ('='*34) )
	print( '  +r : reload cache           | +s          : save cache' )
	print( '  +c : clear bag              | +v          : view Bag' )
	print( '  +e : export bag             | +i          : reimport bag' )    
	print( '  <id>        : to search     | partial_code: to search' )  
	print( '  +q : quit ' )
	print( '-'*40 )
	print( '+<id>   , -<id>   : add/remove a product id' )
	print( '+3*<id> , -3*<id> : add/remove multiple time')
	print( '+2*<partial_code> : add the article based on search (only if unique result)')
	print( '='*40 )

def main():
	def progressHandler( prestaProgressEvent ):
		if prestaProgressEvent.is_finished:
			print( '%s' %prestaProgressEvent.msg )
		else:
			print( '%i/%i - %s' % ( prestaProgressEvent.current_step, prestaProgressEvent.max_step, prestaProgressEvent.msg ) )

	def initialize_globals():
		""" Initialize the global var @ startup or @ reload """
		global ID_SUPPLIER_PARAMS
		_item = cachedphelper.suppliers.supplier_from_name( "PARAMS" )
		#for _item in cachedphelper.suppliers:
		#	print( '%i - %s' % (_item.id,_item.name) )
		if _item != None:
			ID_SUPPLIER_PARAMS = _item.id
			print( 'Catched PARAMS supplier :-). ID: %i' % ID_SUPPLIER_PARAMS )	
    
    # A CachedPrestaHelper is a PrestaHelper with cache capabilities	
	cachedphelper = CachedPrestaHelper( config.presta_api_url, config.presta_api_key, debug = False, progressCallback = progressHandler )
	# Force loading cache
	#   cachedphelper.load_from_webshop()
	
	#tester = CachedPrestaHelperTest( cachedphelper )
	#tester.test_cache()
	print( '******************************************************************' )
	print( '*  Cache statistics                                              *' )
	print( '******************************************************************' )
	print( 'Type of Helper is %s' % type(cachedphelper) )
	print( '#Carriers = %s' % len(cachedphelper.carriers) )
	print( '#OrderStates = %s' % len( cachedphelper.order_states ) )
	print( '#Products = %i' % len( cachedphelper.products ) )
	print( '#suppliers = %i' % len( cachedphelper.suppliers ) )
	print( '#categories = %i' % len( cachedphelper.categories ) )
	print( '#stock availables = %i' % len( cachedphelper.stock_availables ) )
	print( '#product suppliers available = %i' % len( cachedphelper.product_suppliers ) )
	print( '******************************************************************' )
	print( '' )		
	initialize_globals()

	#print('mise à jour des qty' )
	#cachedphelper.stock_availables.update_quantities()
	#print( 'Voila, c est fait' )
	
	bag = ToteBag()
	value = ''
	view_full_bag = False # swicth on by +v command 
	while value != '+q':
		try:
			if view_full_bag:
				# Show the bag as filled (upin +v request)
				print( '= TOTE BAG (full) %s' % ('='*22) )
				view_bag( cachedphelper, bag )
				view_full_bag = False
			else:
				# show an encoding summary
				print( '= TOTE BAG %s' % ('='*29) )
				view_bag( cachedphelper, bag, max_row=10, desc=True )
			print( '='*40 )
			value = raw_input( 'What to do: ' )

			       
			# -- COMMANDS ------------------------------------------
			# +q, +s, +r
			g = re_command.match( value )
			if g:
				cmd = g.groups()[0]
				if cmd == 'q':
					return
				if cmd == 's':
					print( 'Saving cache...' )
					cachedphelper.save_cache_file()
				if cmd == 'r':
					print( 'Contacting WebShop and reloading...' )
					cachedphelper.load_from_webshop()
					initialize_globals() # reinit global variables
				if cmd == 'v': 
					# next bag display must be complete and precise
					view_full_bag = True
				if cmd == 'c':
					# Clear the bag
					del(bag)
					bag = ToteBag()
				if cmd == 'e':
					# export the bag
					root = export_to_xmltree( bag )
					tree = etree.ElementTree( root )

					root = Tk()
					root.filename = tkFileDialog.asksaveasfilename(initialdir = config.tote_bag_export_path,title = "Exporter vers fichier XML",filetypes = (("xml","*.xml"),("all files","*.*")))
					if (root.filename == u'') or (root.filename == config.tote_bag_export_path):
						print( 'User abort!')
						root.destroy()
						continue
					tree.write( root.filename )
					root.destroy()
					print( 'exported to %s' % root.filename )
				if cmd == 'i':
					root = Tk()
					root.filename = tkFileDialog.askopenfilename(initialdir = config.tote_bag_export_path,title = "Recharger un fichier XML",filetypes = (("xml","*.xml"),("all files","*.*")))
					if (root.filename == u'') or (root.filename == config.tote_bag_export_path):
						print( 'User abort!')
						root.destroy()
						continue
					
					tree = etree.parse( root.filename )
					xml_root = tree.getroot()
					# Clear the bag
					del(bag)
					bag = ToteBag()
					# reload content from xml into the tote-bag
					import_from_xmltree(cachedphelper, bag, xml_root )
					root.destroy()
					# next bag display must be complete and precise
					view_full_bag = True
					# display information to user
					print( 'reloaded from %s' % root.filename )

				if cmd == 'h': 
					help()

				# restart loop
				continue

			# -- SEARCH -------------------------------------------
			# GSM,  /-LIPO,    
			g = re_search_text.match( value )
			if g:
				# Text to search = groups()[0] if "demo" or groups()[1] if "/-lipo"  
				txt = g.groups()[0] if g.groups()[0] else g.groups()[1]
				list_products( cachedphelper, key = txt )
				continue
			g = re_search_id.match( value )
			if g:
				# ID to search 
				id = int( g.groups()[0] )
				list_product( cachedphelper, id=id )
				continue

			# -- ADD/REMOVE ID -------------------------------------
			g = re_add_remove_ID.match( value )
			if g:
				
				# Qty and ID
				sign = g.groups()[0]
				id = int( g.groups()[1] )
				# locate product
				p = cachedphelper.products.product_from_id( id )
				if p:
					qty = 1 if sign=='+' else -1
					bag.add_product( qty, p )
				else:
					print( "[ERROR] ID!") 

			# -- ADD/REMOVE SEVERAL ID --------------------------
			g = re_add_remove_several_id.match( value )
			if g:
				
				# Qty and ID
				sign = g.groups()[0] 
				qty  = int( g.groups()[1] )
				id  = int( g.groups()[2] ) 
				# locate product
				p = cachedphelper.products.product_from_id( id )
				if p:
					qty = qty if sign=='+' else -1*qty
					bag.add_product( qty, p )
				else:
					print( "[ERROR] ID!") 

			# -- ADD/REMOVE SEVERAL Text -------------------------
			g = re_add_remove_several_text.match( value )
			if g:
				# Qty and ID
				sign = g.groups()[0] 
				qty  = int( g.groups()[1] )
				txt  = g.groups()[2] 
				# locate product
				lst = cachedphelper.products.search_products_from_partialref( txt )
				if len(lst) == 1:
					qty = qty if sign=='+' else -1*qty
					bag.add_product( qty, lst[0] )
				else:
					list_products( cachedphelper, key=txt )
					print( "NOPE! too much results" )

		except Exception as err:
			print( '[ERROR] %s' % err )
			traceback.print_exc()
	# eof While

	return

if __name__ == '__main__':
	main()

