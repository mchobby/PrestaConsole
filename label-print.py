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
import signal

from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter

def catch_ctrl_C(sig,frame):
    print "Il est hors de question d'autoriser la sortie sauvage!"
signal.signal(signal.SIGINT, catch_ctrl_C)

PRINTER_SHORTLABEL_QUEUE_NAME = 'zebra-raw'   # Small labels 25x30mm
PRINTER_LARGELABEL_QUEUE_NAME = 'zebra-raw-l' # Large labels 25x70mm
PRINTER_ENCODING = 'cp850'

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
		
		
def print_for_product( cachedphelper, id ):
	""" GO TO print the labels for a given ID product """
	item = cachedphelper.products.product_from_id( id )
	if item == None:
		print( 'Oups, %i is not a valid product' % id )
		return
	
	# Detection de la largeur de l'étiquette dans LS:S (label size=small)	
	params = get_product_params_dic( cachedphelper, id )
	label_size = 'large'
	if 'LS' in params:
		if params['LS']=='S':
			label_size = 'small'
		else:
			label_size = 'large'
	

	if len( item.ean13 )>0 and (item.ean13 != '0') :
		product_ean = item.ean13
		print( '%i : %s - %s ' % (id,item.reference,product_ean) )
	else:
		product_ean = '32321%07i' % id # prefix 3232 + product 1 + id_product
		product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
		print( '%i : %s - %s  *generated*' % (id,item.reference,product_ean) )
		
	while True:
		print( '-'*20 )
		print( '+ : switch label size ' )
		print( '+q: quit this print      | 0: quit this print ' )
		print( '' )
		print( 'Label format: %s' % label_size.upper() )
		value = raw_input( 'How many label for %s: ' % item.reference )
		if len(value)==0:
			value = '1'
		if value=='0':
			return
			
		if value=='+': # change label size
			label_size = 'large' if label_size == 'small' else 'small'
			continue 
		if value=='+q': #user abord
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
		
		if label_size == 'small':
			# Print a SMALL label on the PRINTER_SHORTLABEL_QUEUE_NAME
			print_product_label_medium( product_id, product_ref, product_ean, int(value) )
		else:
			# Print a LARGE label on the PRINTER_LARGELABEL_QUEUE_NAME
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

	# Label is printed with 2 lines of 10 characters
	l1 = product_ref[:10] 
	l2 = product_ref[10:]
	
	# Write product name
	#   we will try to offer a human redeable text (2x10 chars) on the  
	#   label properly cut the text around ' ', '-'
	iPos = max( l1.rfind( ' ' ), l1.rfind( '-' ) )
	if iPos == -1 or iPos == 9 or len( product_ref ) <= 10: 
		# The text too short or not appropriate to cute it.
        # Just cut it without care.
		l1 = product_ref.ljust(20)[:10] 
		l2 = product_ref.ljust(20)[10:]
	else:
		iShouldMove = 10 - (iPos+1)
		if len( l2 )+ iShouldMove <= 10: # if second line would not exceed max len ?
			# We go for nicely cutting it!
			l2 = l1[iPos+1:] + l2
			l1 = l1[:iPos+1] 
		else:
			# Keep the cut without care
			l1 = product_ref.ljust(20)[:10] 
			l2 = product_ref.ljust(20)[10:]
			
	
	d.field( origin=(120,11), font=d.font('E'), data= unicode( l1 ) )
	d.field( origin=(120,42), font=d.font('E'), data= unicode( l2 ) )
	# Write a BarCode field
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

def print_product_label_medium( product_id, product_ref, product_ean, qty ):
	""" Print the Labels on the Zebra LP 2824 on 50mm large. 2" x 1" labels """
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
	
	d.field( origin=(25,15), font=d.font('E'), data= unicode( product_ref ) )

	# Write a BarCode field
	d.ean13( origin=(210,60), ean=unicode(product_ean), height_dots = 50 )
	
	d.field( origin=(35,140), font=d.font('C'), data=u'MC Hobby sprl - shop.mchobby.be' )
	d.field( origin=(80,165), font=d.font('C'), data=u'Happy Electronic Hacking!' )
	
	d.field( origin=(325,187), font=d.font('E',17,8), data=unicode( product_id ).rjust(4) )
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

def print_warranty_label_large( prefix_text, counter_start, label_count ):
	""" Print the Warranty Label on the GK420t on 70mm width x 2.5mm height labels """
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	medium = PrinterCupsAdapter( printer_queue_name = PRINTER_LARGELABEL_QUEUE_NAME )

	for label_counter in range( label_count ):
		d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = 'Warranty %s for %i' % (prefix_text, counter_start+counter_start + label_counter) )
	
		# Start a Print format
		d.format_start()

		# Write a BarCode field
		d.field( origin=(175,11), font=d.font('T',17,8), data= unicode( 'Garantie / Warranty') ) # use font E as default
		d.field( origin=(175,62), font=d.font('T',17,8), data= unicode( '%s-%i' % (prefix_text, counter_start + label_counter) ) )# use font E as default
	
		#d.ean13( origin=(500,62), ean=unicode(product_ean), height_dots = 50 )
		# d.field( origin=(630,160), font=d.font('T',17,8), data=unicode( product_id ).rjust(4) ) # use font E by default
		
		d.field( origin=(175,120), font=d.font('C'), data=u'Pour vos garanties, vous les conditions' )
		d.field( origin=(175,145), font=d.font('C'), data=u'générales de ventes sur shop.mchobby.be' )
	

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
			del( d )  
		
	
	del( medium )

def print_ondemand_label_large( label_title, label_lines, qty ):
	""" Print the Labels on the GK420t on 70mm width x 2.5mm height labels 
	
	label_title: title on the label, first line in extra bold
	label_lines: list of unicode to be printed (up to 5 lines)"""
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	medium = PrinterCupsAdapter( printer_queue_name = PRINTER_LARGELABEL_QUEUE_NAME )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,label_title) )
	
	# Start a Print format
	d.format_start()
	
	# Set Quantity 
	if qty > 1:
		d.print_quantity( qty )

	# Write a BarCode field
	d.field( origin=(175,11), font=d.font('T',17,8), data= unicode(label_title) ) # use font E as default
	top = 62
	for line in label_lines:
		d.field( origin=(175, top), font=d.font('C'), data=line )
		top = top + 25
	
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
	
def print_ondemand_label_kingsize( label_title, label_title2, qty=1 ):
	""" Print the Labels on the GK420t on 70mm width x 2.5mm height labels 
	
	label_title: title on the label (the only text to print) """

	medium = PrinterCupsAdapter( printer_queue_name = PRINTER_LARGELABEL_QUEUE_NAME )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,label_title) )
	
	# Start a Print format
	d.format_start()
	
	# Set Quantity 
	if qty > 1:
		d.print_quantity( qty )	
	d.field( origin=(125,11), font=d.font('V',80,71), data= unicode(label_title) ) 
	if len( label_title2 )>0:
		d.field( origin=(125,11+80), font=d.font('V',80,71), data= unicode(label_title2) ) 
		
	#top = 62
	#for line in label_lines:
	#	d.field( origin=(175, top), font=d.font('C'), data=line )
	#	top = top + 25
	
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

def print_ondemand_label_short( label_title, label_lines, qty ):
	""" Print the Labels on the LP2824 on small labels 
	
	label_title: title on the label, lines 1 & two in extra bold
	label_lines: list of unicode to be printed (up to 5 lines)"""
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	medium = PrinterCupsAdapter( printer_queue_name = PRINTER_SHORTLABEL_QUEUE_NAME )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,label_title) )
	
	# Start a Print format
	d.format_start()
	
	# Set Quantity 
	if qty > 1:
		d.print_quantity( qty )

	# Write a BarCode field
	#   Change d.font('E') to d.font('T',17,8 )
	d.field( origin=(40,11), font=d.font('T',17,8), data= unicode( label_title.ljust(20)[:24] ) )
	d.field( origin=(40,42), font=d.font('T',17,8), data= unicode( label_title.ljust(20)[24:] ) )
	top = 95
	for line in label_lines:
		d.field( origin=(40, top), font=d.font('C'), data=line )
		top = top + 25
	
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
		
def product_combination_to_ean13():
	""" Create an ean13 from the mchobby product id + combination id """
	value = raw_input( 'Product ID: ' )
	if not( value.isdigit() ):
		print 'Product ID can only have digits!' 
		return

	value2 = raw_input( 'Combination ID: ' )
	if not( value2.isdigit() ):
		print 'Combination ID can only have digits!' 
		return

	product_ean = '32322%02i%05i' % (int(value2),int(value)) # prefix 3232 + combination 2 + id_combination + id_product
	product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
	print( 'Ean13: %s' % product_ean )

def ondemand_label_large():
	""" Ask the user for the data to print an OnDemand label for large format """
	lines = [] 
	title = 'My onDemand label test!' # Title cannot be unicode
	_size = 'large'
	 
	title = raw_input( 'Title (sans accent) or +q: ' )
	if title == '+q': # user abord
		return
	
	print( 'Key in the lines (6 lines max):' )
	print( '  +q to quit'        ) 
	print( '  empty to proceed)' )
	iLine = 0
	while True:
		iLine += 1
		aLine = raw_input( '%i: ' % iLine )
		if len( aLine ) == 0:
			break
		if aLine == '+q': # User abord
			return 
		
		# Decode the line otherwise the unicode quest an ascii string
		lines.append( unicode( aLine.decode( sys.stdin.encoding ) ) )
		if iLine == 6:
			break
	
	value = raw_input( 'How many labels ?' )
	if value == 0:
		return
	if value == '+q':
		return
	if value == '': # By default, 1 label
		value = 1
		
	qty = int( value )
	if qty > 25:
		print( 'Max 25 labels allowed! Value sharped to 25.' )
		qty = 25
		
	print_ondemand_label_large( title, lines, qty )

def print_vat_labels():
	""" Ask the user for the data to print an OnDemand label for large format """
	lines = [] 
	title = 'Exempte de TVA Belge' # Title cannot be unicode
	 
	# Decode the line otherwise the unicode quest an ascii string
	lines.append( u"Conformément à l'Article 39 bis du Code"  )
	lines.append( u"de la TVA."  )
	lines.append( u"Livraison Intracommunautaire de Biens."  )
	lines.append( u"Autoliquidation."  )
	
	value = raw_input( 'How many labels ?' )
	if value == 0:
		return
	if value == '': # By default, 1 label
		value = 1
		
	qty = int( value )
	if qty > 50:
		print( 'Max 50 labels allowed! Value sharped to 50.' )
		qty = 50
		
	print_ondemand_label_large( title, lines, qty )

def ondemand_label_short():
	""" Ask the user for the data to print an OnDemand label for short format """
	lines = [] 
	title = 'My onDemand label test!' # Title cannot be unicode
	 
	title = raw_input( 'Title (sans accent) or +q: ' )
	if title == '+q': # user abord
		return
	
	print( 'Key in the lines (+q to quit, empty to proceed)' )
	iLine = 0
	while True:
		iLine += 1
		aLine = raw_input( '%i: ' % iLine )
		if len( aLine ) == 0:
			break
		if aLine == '+q': # User abord
			return  
		
		# Decode the line otherwise the unicode quest an ascii string
		lines.append( unicode( aLine.decode( sys.stdin.encoding ) ) )
		if iLine == 6:
			break
	
	value = raw_input( 'How many labels ?' )
	if value == 0:
		return
	if value == '+q':
		return
	if value == '': # By default, 1 label
		value = 1
		
	qty = int( value )
	if qty > 25:
		print( 'Max 25 labels allowed! Value sharped to 25.' )
		qty = 25
		
	print_ondemand_label_short( title, lines, qty )
	
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
		print( '  +12: ean12 to ean13         | +e          : create ean13' )
		print( '  id : id product to print    | +f          : create comb. ean13' )
		print( '  +ol: On demand label (Large)| +al         : address label' )
		print( '  +os: On demand label (Short)| +openl      : open for... label' )
		print( '  +ok: On demand label (King) | +w          : Warranty')
		print( '  partial_code: to search     | +vat        : vat intracom text' )
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
		elif value == '+12':
			ean12_to_ean13()
		elif value == '+e':
			product_id_to_ean13()
		elif value == '+f':
			product_combination_to_ean13()
		elif value == '+ol': #On_demand Large label
			ondemand_label_large()
		elif value == '+os': #On_demand Short label
			ondemand_label_short()
		elif value == '+ok': #On_demand King Size Label
			line1 = raw_input( 'Line 1: ' )
			if line1 == '+q' or line1 == '':
				continue
			line2 = raw_input( 'Line 2: ' )
                        value = raw_input( 'How many lables or +q: ' )
                        if value == '+q' or value == '0':
                                continue
                        if value == '':
			        value = '1'
                        qty = int( value )
                        if qty > 25:
                                qty = 25
                                print( 'Max 25 labels allowed! Value sharped to 25' )
                                
			print_ondemand_label_kingsize( line1, line2, qty )

		elif value == '+al': # adress Label
			value = raw_input( 'How many labels or +q: ' )
			if value == '+q' or value=='0':
				continue
			if value == '':
				value = '1'
			qty = int( value )
			if qty > 25:
				qty = 25
				print( 'Max 25 labels allowed! Value sharped to 25.' )
				
			print_ondemand_label_large( 'MC Hobby SPRL',
				[ unicode( config.company_address[0]  ),
				unicode( config.company_address[1]  ),
				unicode( config.company_address[2]  ),
				unicode( u'TVA/VAT: %s' % config.company_vat   ), 
				unicode( u'Phone  : %s' % config.company_phone ),
				unicode( u'Web    : %s' % config.company_url   )
				], qty )

		elif value == '+openl': 
			value = raw_input( 'How many labels or +q: ' )
			if value == '+q' or value=='0':
				continue
			if value == '':
				value = '1'
			qty = int( value )
			if qty > 25:
				qty = 25
				print( 'Max 25 labels allowed! Value sharped to 25.' )

			print_ondemand_label_large( 'Votre produit ouvert pour:',
				[u'[  ] ajout de matériel',
				u'[  ] contrôle qualité',
				u'',
				u'',
				u'MC Hobby SPRL' ], qty )
		elif value == '+w':
			prefix_str = raw_input(    'Préfix ou +q (ex:ELI-MEGA)             : ' )
			if value == '+q':
				continue
			counter_start = raw_input( 'N° première étiquette ou +q (ex:150021): ' )
			if counter_start == '+q':
				continue
			counter_start = int( counter_start ) 
			how_many_label= raw_input( "Combien d'étiquette ou +q             : " )
			if how_many_label == '+q':
				continue
			how_many_label = int( how_many_label )

			print_warranty_label_large( prefix_text = prefix_str, counter_start = counter_start, label_count = how_many_label )
		
		elif value == '+vat':
			print_vat_labels()
				
		elif value.isdigit():
			print_for_product( cachedphelper, int(value) )
		else:
			print( 'Looking for product %s...' % value )
			list_products( cachedphelper, value )

	return

if __name__ == '__main__':
	main()

