#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""label-print.py

derivated from prestaconsole.py project
  
Copyright 2014 DMeurisse <info@mchobby.be>
  
Print Labels on Zebra LP 2824 PLUS via the CUPS "zebra-raw" print queue
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

from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter

PRINTER_SHORTLABEL_QUEUE_NAME = 'zebra-raw'   # Small labels 25x30mm
PRINTER_LARGELABEL_QUEUE_NAME = 'zebra-raw-l' # Large labels 25x70mm
PRINTER_ENCODING = 'cp850'

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

def list_products( cachedphelper, key ):
	""" Search for a product base on its partial reference code + list them """
	assert isinstance( key, str ), 'Key must be a string'
	if len( key ) < 3:
		print( 'searching product requires at least 3 characters' )
		return
	
	result = cachedphelper.products.search_products_from_partialref( key )
	for item in result:
		print( '%4i : %s - %s' % (item.id,item.reference.ljust(20),item.name) )
		
def print_for_product( cachedphelper, id ):
	""" print the labels for a given ID product """
	item = cachedphelper.products.product_from_id( id )
	if item == None:
		print( 'Oups, %i is not a valid product' % id )
		return

	if len( item.ean13 )>0 :
		product_ean = item.ean13
		print( '%i : %s - %s ' % (id,item.reference,product_ean) )
	else:
		product_ean = '32321%07i' % id # prefix 3232 + product 1 + id_product
		product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
		print( '%i : %s - %s  *generated*' % (id,item.reference,product_ean) )
		
	value = raw_input( 'How many label for %s: ' % item.reference )
	if len(value)==0:
		value = '1'
	if value=='0':
		return
	if not value.isdigit():
		print( '%s is not a numeric value' % value )
		return
	
	if int(value) > 25:
		value2 = raw_input( 'Quantity > 25! Please confirm: ' )
		if not value2.isdigit():
			print( '%s is not a numeric value, ABORT!' % value2 )
			return
		elif int(value2) != int(value):
			print( 'inconsistant quantities %s & %s' % (value, value2) )
			return
			
	# collect the needed data to print the label
	product_id = id
	product_ref = item.reference
	
	print_product_label_large( product_id, product_ref, product_ean, int(value) )	 
	return
	 
def print_product_label( product_id, product_ref, product_ean, qty ):
	""" Print the Labels on the Zebra LP 2824 on 1.25" x 1" labels """
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	medium = PrinterCupsAdapter( printer_queue_name = PRINTER_SHORTLABEL_QUEUE_NAME )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,product_ref) )
	
	# Start a Print format
	d.format_start()
	
	# Set Quantity 
	if qty > 1:
		d.print_quantity( qty )

	# Write a BarCode field
	d.field( origin=(120,11), font=d.font('E'), data= unicode( product_ref.ljust(20)[:10] ) )
	d.field( origin=(120,42), font=d.font('E'), data= unicode( product_ref.ljust(20)[10:] ) )
	d.ean13( origin=(130,80), ean=unicode(product_ean), height_dots = 50 )
	
	d.field( origin=(130,160), font=d.font('C'), data=u'shop.mchobby.be' )
	d.field( origin=(98,185), font=d.font('C'), data=u'MC Hobby sprl' )
	
	d.field( origin=(265,185), font=d.font('E',17,8), data=unicode( product_id ).rjust(4) )
	# End Print format
	d.format_end()

	
	medium.open() # Open the media for transmission. 
				  # With CUPS medium this open a temporary file
	try:
		d.send()  # With CUPS medium this send the data to the temporary file
		medium.flush() # With CUPS medium this close the temporary file and
		               #   sends to file to the print queue  
	finally:
		medium.close()  
		               
	
	del( medium )
	
def print_product_label_large( product_id, product_ref, product_ean, qty ):
	""" Print the Labels on the GK420t on 70mm width x 2.5mm height labels """
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	medium = PrinterCupsAdapter( printer_queue_name = PRINTER_LARGELABEL_QUEUE_NAME )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,product_ref) )
	
	# Start a Print format
	d.format_start()
	
	# Set Quantity 
	if qty > 1:
		d.print_quantity( qty )

	# Write a BarCode field
	d.field( origin=(175,11), font=d.font('T',17,8), data= unicode( product_ref) ) # use font E as default
	
	d.ean13( origin=(500,62), ean=unicode(product_ean), height_dots = 50 )
	d.field( origin=(630,160), font=d.font('T',17,8), data=unicode( product_id ).rjust(4) ) # use font E by default
		
	d.field( origin=(225,150), font=d.font('C'), data=u'MC Hobby sprl - shop.mchobby.be' )
	d.field( origin=(255,175), font=d.font('C'), data=u'Happy Electronic Hacking!' )
	

	# End Print format
	d.format_end()

	
	medium.open() # Open the media for transmission. 
				  # With CUPS medium this open a temporary file
	try:
		d.send()  # With CUPS medium this send the data to the temporary file
		medium.flush() # With CUPS medium this close the temporary file and
		               #   sends to file to the print queue  
	finally:
		medium.close()  
		               
	
	del( medium )

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
	print( '******************************************************************' )
	print( '' )		
	#print('mise à jour des qty' )
	#cachedphelper.stock_availables.update_quantities()
	#print( 'Voila, c est fait' )
	
	value = ''
	while value != '+q':
		print( '' )
		print( '  +r : reload cache         | +s          : save cache' )
		print( '  +12: ean12 to ean13       | +e          : create ean13' )
		print( '  id : id product to print  | partial_code: to search' )
		print( '  +q : quit ' )
		print( '' )
		value = raw_input( 'What to do: ' )
		
		if value == '+q':
			pass
		elif value == '+r':
			print( 'Contacting WebShop and reloading...' )
			cachedphelper.load_from_webshop()
		elif value == '+s':
			print( 'Saving cache...' )
			cachedphelper.save_cache_file()
		elif value == '+12':
			ean12_to_ean13()
		elif value == '+e':
			product_id_to_ean13()
		elif value.isdigit():
			print_for_product( cachedphelper, int(value) )
		else:
			print( 'Looking for product %s...' % value )
			list_products( cachedphelper, value )

	return

if __name__ == '__main__':
	main()

