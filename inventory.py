#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""inventory.py

derivated from prestaconsole.py project

Copyright 2018 DMeurisse <info@mchobby.be>

Generate an inventory report for the shop

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

PRODUCT_EXCLUDE = ( 'BON-CADEAU', 'X-CTU', 'POINT' )

# from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter

RE_COMMAND                 = "^\+([a-zA-Z])$"              # (command) +r OU +s

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


def list_products( cachedphelper, key ):
	""" Search for a product base on its partial reference code + list them """
	assert isinstance( key, str ), 'Key must be a string'
	if len( key ) < 3:
		print( 'searching product requires at least 3 characters' )
		return

	result = cachedphelper.products.search_products_from_partialref( key, include_inactives = True )
	for item in result:
		print( '%7i : %s - %s' % (item.id,item.reference.ljust(30),item.name) )

class Product_cargo():
	__slot__ = ['id', 'reference', 'pa', 'pv', 'qty_stock', 'name', '_product_data' ]

	def __init__( self, product_data ):
		self.id = product_data.id
		self.reference = product_data.reference
		self.pa = product_data.wholesale_price
		self.pv = product_data.price
		self.qty_stock = 0

		self.name = product_data.name
		self._product_data = product_data

	def __repr__( self ):
		return '<Product_cargo %s, %s>'%(self.id,self.reference)

def list_product( cachedphelper, id ):
	""" Search for a product base on its ID + list it """
	assert isinstance( id, int ), 'in must be a int'

	item = cachedphelper.products.product_from_id( id_product = id  )
	if item:
		print( '%7i : %s - %s' % (item.id,item.reference.ljust(30),item.name) )

def export_to_xmltree( lst , decimal_separator=',' ):
	""" Export the content of a list of product_cargo into an XML structure """
	root = etree.Element( 'inventory' )
	for item in lst:
		el = etree.SubElement( root, "product" )

        # __slots__ = ["id", "active", "reference", "name", "wholesale_price",
        #     "price", "id_supplier", "id_category_default", "advanced_stock_management",
        #     "available_for_order", "ean13" ]

		# add values for the Row
		etree.SubElement( el, "id" ).text = "%s" % item.id
		etree.SubElement( el, "reference" ).text = "%s" % item.reference
		etree.SubElement( el, "PA_HTVA"   ).text = ("%s" % item.pa).replace('.', decimal_separator)
		etree.SubElement( el, "PV_HTVA"   ).text = ("%s" % item.pv).replace('.', decimal_separator)
		etree.SubElement( el, "qty_stock" ).text = "%s" % item.qty_stock
		etree.SubElement( el, "Valeur_PA" ).text = ("%s" % (item.pa*item.qty_stock)).replace('.', decimal_separator)
		etree.SubElement( el, "Remarque"  ).text = ""
		etree.SubElement( el, "Nom"       ).text = "%s" % item.name

	return root

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

def build_inventory_list( cachedphelper ):
	r = []
	products = cachedphelper.get_products()
	for item in products:
		if item.reference in PRODUCT_EXCLUDE:
			continue
		_cargo = Product_cargo( item )
		# Identify stock information
		stock = cachedphelper.stock_availables.stockavailable_from_id_product( _cargo.id )
		if stock:
			_cargo.qty_stock = stock.quantity
		r.append( _cargo )
	# Also locates all the IT-xxx articles.
	# They are NOT ACTIVE so we would not duplicate them
	for item in products.inactivelist:
		if item.reference and (item.reference.find( 'IT-' ) == 0):
			_cargo = Product_cargo( item )
			# Identify stock information
			stock = cachedphelper.stock_availables.stockavailable_from_id_product( _cargo.id )
			if stock:
				_cargo.qty_stock = stock.quantity
			r.append( _cargo )
	return r

def help():
	""" Display Help """
	print( '== HELP %s' % ('='*34) )
	print( '  +r : reload cache           | +s          : save cache' )
	print( '  +e : export inventory       | ' )
	print( '  +q : quit ' )
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

	value = ''
	while value != '+q':
		try:
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
				if cmd == 'e':
					# export the inventory list
					lst = build_inventory_list( cachedphelper )
					sorted_lst = sorted( lst, key=lambda cargo:cargo.reference )
					root = export_to_xmltree( sorted_lst )
					tree = etree.ElementTree( root )

					root = Tk()
					root.filename = tkFileDialog.asksaveasfilename( title = "Exporter vers fichier XML",filetypes = (("xml","*.xml"),("all files","*.*")))
					if (root.filename == u''):
						print( 'User abort!')
						root.destroy()
						continue
					tree.write( root.filename )
					root.destroy()
					print( 'exported to %s' % root.filename )


				if cmd == 'h':
					help()

				# restart loop
				continue

			# -- SEARCH -------------------------------------------
			# GSM,  /-LIPO,
			#g = re_search_text.match( value )
			#if g:
			#	# Text to search = groups()[0] if "demo" or groups()[1] if "/-lipo"
			#	txt = g.groups()[0] if g.groups()[0] else g.groups()[1]
			#	list_products( cachedphelper, key = txt )
			#	continue

		except Exception as err:
			print( '[ERROR] %s' % err )
			traceback.print_exc()
	# eof While

	return

if __name__ == '__main__':
	main()
