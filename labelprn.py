#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""labelprn.py

Label Printing Helpers for the Presta Console project

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

import logging
import sys
from pypcl import ZplDocument, PrinterCupsAdapter
from prestaapi import calculate_ean13

# Must be initialised with proper names
printer_shortlabel_queue_name = 'Undefined' # Small labels 25x30mm
printer_largelabel_queue_name = 'Undefined' # Large labels 25x70mm
printer_ticket_queue_name     = 'Undefined' # Large labels 25x70mm
PRINTER_ENCODING = 'cp850'

shop_info_small = [] # Shop information for small Label
shop_info_large = [] # Shop Information for Large Label

def request_qty( prompt = 'How many items ?'):
	""" Request a quantity and confirm it if greater than 25 """
	value = raw_input( prompt )
	if value == 0:
		return None
	if value == '+q':
		return None
	if value == '': # By default, 1 label
		value = 1

	qty = int( value )
	if qty > 25:
		value2 = raw_input( 'Quantity > 25! Please confirm: ' )
		if not value2.isdigit():
			print( '%s is not a numeric value, ABORT!' % value2 )
			return None
		elif int(value2) != int(qty):
			print( 'inconsistant values %s & %s' % (qty, value2) )
			return	None
	return qty

def handle_print_for_product( product, params, separator=False ):
	""" Manage the tickect printing for an ID product.
		May ask additionnal questions on on input

		:param product: the ProductData object to print
		:param params: the product parameter dictionnary (extracted from PARAMS supplier)
		:param seperator: Print a separator label before the product print
		:return: True if something has been printed
		"""
	# item = cachedphelper.products.product_from_id( id )
	assert product
	assert len( product.ean13 )>0 and (product.ean13 != '0'), 'Product must have an EAN13 !'

	# Detection de la largeur de l'étiquette dans LS:S (label size=small)
	label_size = 'large'
	if 'LS' in params:
		if params['LS']=='S':
			label_size = 'small'
		else:
			label_size = 'large'

	while True:
		print( 'Label format: %s (+ to change)' % label_size.upper() )
		value = raw_input( 'How many label for %s: ' % product.reference )
		if len(value)==0:
			value = '1'
		if value=='0':
			return False

		if value=='+': # change label size
			label_size = 'large' if label_size == 'small' else 'small'
			continue
		if value=='+q': #user abord
			return False

		if not value.isdigit():
			print( '%s is not a numeric value' % value )
			return False

		if int(value) > 25:
			value2 = raw_input( 'Quantity > 25! Please confirm: ' )
			if not value2.isdigit():
				print( '%s is not a numeric value, ABORT!' % value2 )
				return False
			elif int(value2) != int(value):
				print( 'inconsistant quantities %s & %s' % (value, value2) )
				return False

		if label_size == 'small':
			if separator:
				print_custom_label_small( '='*24, [u'%s x' % value, unicode(product.reference) ], 1 )
			# Print a SMALL label on the PRINTER_SHORTLABEL_QUEUE_NAME
			print_product_label_medium( product.id, product.reference, product.ean13, int(value) )
			return True
		else:
			# Print a LARGE label on the PRINTER_LARGELABEL_QUEUE_NAME
			if separator:
				print_custom_label_large(  '='*24, [u'%s x' % value, unicode(product.reference) ], 1 )
		print_product_label_large( product.id, product.reference, product.ean13, int(value) )
		return True

def handle_print_custom_label_large():
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

	qty = request_qty()
	if qty == None:
		return

	print_custom_label_large( title, lines, qty )

def handle_print_custom_label_king():
	""" Print King Size Label - 2 lines only """
	line1 = raw_input( 'Line 1: ' )
	if line1 == '+q' or line1 == '':
		return
	line2 = raw_input( 'Line 2: ' )
	qty = request_qty()
	if qty == None:
		return

	print_custom_label_king( line1, line2, qty )

def handle_print_custom_label_small():
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

	qty = request_qty()
	if qty == None:
		return

	print_custom_label_small( title, lines, qty )

def handle_print_warranty_label_large( product ):
	""" Manage the printing of warranty label for a given product.
		May ask additionnal questions on on input

		:param product: the ProductData object to print
	"""
	print( "Warranty label                         : %s" % product.reference )
	prefix_str = raw_input( 'Préfix ou +q (ex:ELI-MEGA)             : ' )
	if prefix_str == '+q':
		return
	counter_start = raw_input( 'N° première étiquette ou +q (ex:150021): ' )
	if counter_start == '+q':
		return
	counter_start = int( counter_start )
	how_many_label= raw_input( "Combien d'étiquette ou +q              : " )
	if how_many_label == '+q':
		return
	how_many_label = int( how_many_label )

	print_warranty_label_large( product = product, prefix_text = prefix_str, counter_start = counter_start, label_count = how_many_label )

def handle_print_vat_label_large():
	""" Ask the user for the data to print an OnDemand label for large format """
	lines = []
	title = 'Exempte de TVA Belge' # Title cannot be unicode

	# Decode the line otherwise the unicode quest an ascii string
	lines.append( u"Conformément à l'Article 39 bis du Code"  )
	lines.append( u"de la TVA."  )
	lines.append( u"Livraison Intracommunautaire de Biens."  )
	lines.append( u"Autoliquidation."  )

	qty = request_qty()
	if qty == None:
		return

	print_custom_label_large( title, lines, qty )

def handle_print_ean_label_large():
	""" Ask the user for the data to print a CUSTOM ean label for large format """
	title = raw_input( 'Title (sans accent) or +q: ' )
	if title == '+q': # user abord
		return
	label = raw_input( 'Label (sans accent) or +q: ' )
	if label == '+q': # user abord
		return
	ean = raw_input( 'EAN (sans accent) or +q: ' )
	if ean == '+q': # user abord
		return

	print_label_large( title, label, ean )

# ===================================================================
#
#      BASIC ***TICKET*** FUNCTIONS
#
# ===================================================================

def print_ticket_batch( batch, qty ):
	""" Print the ticket labels for a batch  """
	global printer_ticket_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_ticket_queue_name )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,batch.data.product_reference) )

	# Start a Print format
	d.format_start()
	d.label_home( x_mm = 0, y_mm=7 )
	d.label_length( length_mm=65 ) #40 mm
	d.print_mode( d.PRINT_MODE_CUTTER )
	d.media_tracking( d.MEDIA_TRACKING_CONTINUOUS )
	# Set Quantity
	if qty > 1:
		d.print_quantity( qty )
	_ref = batch.data.product_reference
	d.field( origin=(120,40 ), font=d.font('G'), data= unicode( _ref[:13] ) )
	d.field( origin=(120,100), font=d.font('G'), data= unicode( _ref[13:] ) )

	#d.field( origin=(140,10), font=d.font('E'), data= unicode( batch.data.product_reference ) )
	d.field( origin=(120,160), font=d.font('B'), data= unicode( batch.data.product_name ) )

	# Write a BarCode field
	d.ean13( origin=(200,185), ean=unicode( batch.data.product_ean), height_dots = 50 )

	#Expiration: 05/2020
	d.field( origin=(140,290), font=d.font('E'), data= unicode( 'Expire:') )
	d.field( origin=(280,280), font=d.font('G'), data= unicode( batch.data.expiration ) )
	# Write a BarCode field
	_exp_ean = calculate_ean13( '326200%s' % batch.data.expiration.replace('/','') )
	d.ean13( origin=(200,360), ean=unicode( _exp_ean ), height_dots = 20 )
	d.field( origin=(140,425), font=d.font('E'), data= unicode( 'Lot: %s' % batch.data.batch_id ) )
	# Draw a line
	d.draw_box( 140, 460, 550, 1 )

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

	for transformation in batch.transformations:
		print_ticket_transformation( batch.data.batch_id , transformation, qty=transformation.label_count )

def print_ticket_transformation( batch_id, transformation, qty ):
	""" Print the ticket labels for a batch  """
	global printer_ticket_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_ticket_queue_name )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,transformation.target_product_reference) )

	# Start a Print format
	d.format_start()
	d.label_home( x_mm = 0, y_mm=7 )
	d.label_length( length_mm=65 ) #40 mm
	d.print_mode( d.PRINT_MODE_CUTTER )
	d.media_tracking( d.MEDIA_TRACKING_CONTINUOUS )
	# Set Quantity
	if qty > 1:
		d.print_quantity( qty )
	_ref = transformation.target_product_reference
	d.field( origin=(120,40 ), font=d.font('G'), data= unicode( _ref[:13] ) )
	d.field( origin=(120,100), font=d.font('G'), data= unicode( _ref[13:] ) )

	#d.field( origin=(140,10), font=d.font('E'), data= unicode( batch.data.product_reference ) )
	d.field( origin=(120,160), font=d.font('B'), data= unicode( transformation.target_product_name ) )

	# Write a BarCode field
	d.ean13( origin=(200,185), ean=unicode( transformation.target_product_ean), height_dots = 50 )

	#Expiration: 05/2020
	d.field( origin=(140,290), font=d.font('E'), data= unicode( 'Expire:') )
	d.field( origin=(280,280), font=d.font('G'), data= unicode( transformation.expiration ) )
	# Write a BarCode field
	_exp_ean = calculate_ean13( '326200%s' % transformation.expiration.replace('/','') )
	d.ean13( origin=(200,360), ean=unicode( _exp_ean ), height_dots = 20 )
	d.field( origin=(140,425), font=d.font('E'), data= unicode( 'Lot: %s' % batch_id ) )
	# Draw T
	d.field( origin=(540,690), font=d.font('E'), data= unicode('T') )
	d.draw_circle( 540,690, 20, tickness=3 )
	# Draw a line
	d.draw_box( 140, 460, 550, 1 )

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

# ===================================================================
#
#      BASIC ***LABEL*** PRINT FUNCTIONS
#
# ===================================================================


def print_product_label( product_id, product_ref, product_ean, qty ):
	""" Print the Labels on the Zebra LP 2824 on 1.25" x 1" labels """
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	global printer_shortlabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_shortlabel_queue_name )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,product_ref) )

	# Start a Print format
	d.format_start()
	d.field( origin=(120,11), font=d.font('E'), data= unicode( 'This is a test' ) )

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

	global shop_info_small
	if shop_info_small: # A list of string
		for i in range( len(shop_info_small)):
			d.field( origin=(98,(160+i*25)), font=d.font('C'), data=unicode( shop_info_small[i] ) )
	#d.field( origin=(130,160), font=d.font('C'), data=u'shop.mchobby.be' )
	#d.field( origin=(98,185), font=d.font('C'), data=u'MC Hobby sprl' )

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
	global printer_shortlabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_shortlabel_queue_name )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,product_ref) )

	# Start a Print format
	d.format_start()

	# Set Quantity
	if qty > 1:
		d.print_quantity( qty )

	d.field( origin=(25,15), font=d.font('E'), data= unicode( product_ref ) )

	# Write a BarCode field
	d.ean13( origin=(210,60), ean=unicode(product_ean), height_dots = 50 )

	global shop_info_large
	if shop_info_small: # A list of string
		for i in range( len(shop_info_large)):
			d.field( origin=(35,(140+i*25)), font=d.font('C'), data=unicode( shop_info_large[i] ) )
	#d.field( origin=(35,140), font=d.font('C'), data=u'MC Hobby sprl - shop.mchobby.be' )
	#d.field( origin=(80,165), font=d.font('C'), data=u'Happy Electronic Hacking!' )

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
	global printer_largelabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_largelabel_queue_name )
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

	global shop_info_large
	if shop_info_large: # A list of string
		for i in range( len(shop_info_large)):
			d.field( origin=(225,(150+i*25)), font=d.font('C'), data=unicode( shop_info_large[i] ) )
	#d.field( origin=(225,150), font=d.font('C'), data=u'MC Hobby sprl - shop.mchobby.be' )
	#d.field( origin=(255,175), font=d.font('C'), data=u'Happy Electronic Hacking!' )


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

def print_label_large( title, label, ean, qty=1 ):
	""" Print the Labels on the GK420t on 70mm width x 2.5mm height labels """
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	global printer_largelabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_largelabel_queue_name )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,title) )

	# Start a Print format
	d.format_start()

	# Set Quantity
	if qty > 1:
		d.print_quantity( qty )

	# Write a BarCode field
	d.field( origin=(175,11), font=d.font('T',17,8), data= unicode(title) ) # use font E as default

	#d.ean13( origin=(500,62), ean=unicode(ean), height_dots = 50 )
	d.ean13( origin=(320,62), ean=unicode(ean), height_dots = 80 )

	#d.field( origin=(630,160), font=d.font('T',17,8), data=unicode( product_id ).rjust(4) ) # use font E by default

	d.field( origin=(225,175), font=d.font('C'), data=unicode( label ) )

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


def print_warranty_label_large( product, prefix_text, counter_start, label_count ):
	""" Print the Warranty Label on the GK420t on 70mm width x 2.5mm height labels """
	global printer_largelabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_largelabel_queue_name )

	for label_counter in range( label_count ):
		d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = 'Warranty %s for %i' % (prefix_text, counter_start+counter_start + label_counter) )

		# Start a Print format
		d.format_start()

		# Write a BarCode field
		d.field( origin=(175,11), font=d.font('S',17,8), data= unicode( 'Garantie/Warranty') ) # use font E as default
		d.field( origin=(175,62), font=d.font('T',17,8), data= unicode( '%s-%i' % (prefix_text, counter_start + label_counter) ) )# use font E as default

		war_ean = "325%09d" % (counter_start + label_counter,)  #EAN12: 325<ID_warranty>
		d.ean13( origin=(500,11), ean=unicode(calculate_ean13(war_ean)), height_dots = 20 )
		# d.field( origin=(630,160), font=d.font('T',17,8), data=unicode( product_id ).rjust(4) ) # use font E by default

		d.field( origin=(175,120), font=d.font('C'), data=u'Pour vos garanties, voir les conditions' )
		d.field( origin=(175,145), font=d.font('C'), data=u'générales de ventes sur shop.mchobby.be' )

		d.field( origin=(400,170), font=d.font('S',17,8), data=unicode(str(product.reference)) )
		d.ean13( origin=(175,165), ean=unicode(product.ean13), height_dots = 20 )

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

def print_custom_label_large( label_title, label_lines, qty ):
	""" Print the Labels on the GK420t on 70mm width x 2.5mm height labels

	label_title: title on the label, first line in extra bold
	label_lines: list of unicode to be printed (up to 5 lines)"""
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	global printer_largelabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_largelabel_queue_name )
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

def print_custom_label_king( label_title, label_title2, qty=1 ):
	""" Print the Labels on the GK420t on 70mm width x 2.5mm height labels

	label_title: title on the label (the only text to print) """
	global printer_largelabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_largelabel_queue_name )
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


def print_custom_label_small( label_title, label_lines, qty, ean=None ):
	""" Print the Labels on the LP2824 on small labels

	label_title: title on the label, lines 1 & two in extra bold
	label_lines: list of unicode to be printed (up to 5 lines)
	ean        : ean12 or ean13 (as string) to print. ean12 is automatically transformed to ean13! """
	#print product_id
	#print product_ref
	#print product_ean
	#print qty
	global printer_shortlabel_queue_name
	medium = PrinterCupsAdapter( printer_queue_name = printer_shortlabel_queue_name )
	d = ZplDocument( target_encoding = PRINTER_ENCODING, printer_adapter = medium, title = '%i x %s' % (qty,label_title) )

	# Start a Print format
	d.format_start()

	# Set Quantity
	if qty > 1:
		d.print_quantity( qty )

	# Write a BarCode field
	#   Change d.font('E') to d.font('T',17,8 )
	d.field( origin=(40,11), font=d.font('T',17,8), data= unicode( label_title.ljust(20)[:24] ) )
	d.field( origin=(40,45), font=d.font('T',17,8), data= unicode( label_title.ljust(20)[24:] ) )
	top = 95
	for line in label_lines:
		d.field( origin=(40, top), font=d.font('C'), data=line )
		top = top + 25

	# Write a BarCode field
	if ean:
		if len(ean)!=13:
			ean = calculate_ean13(ean) # Transform ean12 to ean13 --> append check digit
		d.ean13( origin=(120,140), ean=unicode(ean), height_dots = 50 )

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

#def product_combination_to_ean13():
#	""" Create an ean13 from the mchobby product id + combination id """
#	value = raw_input( 'Product ID: ' )
#	if not( value.isdigit() ):
#		print 'Product ID can only have digits!'
#		return
#
#	value2 = raw_input( 'Combination ID: ' )
#	if not( value2.isdigit() ):
#		print 'Combination ID can only have digits!'
#		return
#
#	product_ean = '32322%02i%05i' % (int(value2),int(value)) # prefix 3232 + combination 2 + id_combination + id_product
#	product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
#	print( 'Ean13: %s' % product_ean )



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




if __name__ == '__main__':
	print( 'This file only contains helper functions!' )
	print( 'Nothing to run here!' )
