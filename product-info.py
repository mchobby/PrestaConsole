#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""product-info.py

derivated from prestaconsole.py project
  
Copyright 2014 DMeurisse <info@mchobby.be>
  
Search and print informations about products
Version alpha

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

# from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter

def catch_ctrl_C(sig,frame):
    print "Il est hors de question d'autoriser la sortie sauvage!"
signal.signal(signal.SIGINT, catch_ctrl_C)

PRINTER_ENCODING = 'cp850'

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

# LABEL Size is stored into the article reference of the "PARAMS" supplier.
ID_SUPPLIER_PARAMS = None

def list_products( cachedphelper, key=None, ean=None, id=None ):
	""" Search for a product base on its partial reference code (key) -OR- its ean -OR- product ID + list them """
	
	if key:
		assert isinstance( key, str ), 'Key must be a string'
		if len( key ) < 3:
			print( 'searching product requires at least 3 characters' )
			return
		result = cachedphelper.products.search_products_from_partialref( key )
	elif ean:
		assert isinstance( ean, str ), 'Key must be a string'
		result = cachedphelper.products.search_products_for_ean( ean )
	elif id:
		assert isinstance( id, int ), 'ID must be an integer'
		_r = cachedphelper.products.product_from_id( id )
		result = [_r] if _r else None

	if result: 
		for item in result:
			print( '%4i : %s - %s' % (item.id,item.reference.ljust(20),item.name) )
	else:
		print( 'Nothing for %s' % ean )
		
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
		

def ean12_to_ean13():
	""" calculate the checksum of an ean12 to create an ean13 """
	value = raw_input( 'Ean12: ' )
	if not( value.isdigit() ) or not ( len(value)== 12 ):
		print 'EAN12 must have 12 digits!' 
		return
	print( 'Ean13: %s' % calculate_ean13( value ) )
		
def product_id_to_ean13():
	""" Create an ean13 from the mchobby product id """
	value = raw_input( 'Product ID: ' )
	if not( value.isdigit() ):
		print 'Product ID can only have digits!' 
		return
	product_ean = '32321%07i' % int(value) # prefix 3232 + product 1 + id_product
	product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
	print( 'Ean13: %s' % product_ean )
		

	
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
		print( '='*40 )
		print( '  +r : reload cache           | +s          : save cache' )
		print( '  +q : quit ' )
		print( '='*40 )
		print( '' )
		value = raw_input( 'What to do: ' )
		
		if value == '+q':
			pass
		elif value == '+r':
			print( 'Contacting WebShop and reloading...' )
			cachedphelper.load_from_webshop()
			initialize_globals() # reinit global variables	
		elif value == '+s':
			print( 'Saving cache...' )
			cachedphelper.save_cache_file()
				
		elif value.isdigit():
			if len(value)<=5: # we are looking for a product ID
				list_products( cachedphelper, id=int(value) )
			else:
				list_products( cachedphelper, ean=value )
		else:
			print( 'Looking for product %s...' % value )
			list_products( cachedphelper, key=value )

	return

if __name__ == '__main__':
	main()

