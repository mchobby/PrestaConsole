#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""lcdordertrack.py
  
Copyright 2014 DMeurisse <info@mchobby.be>
  
Presta Shop Order Tracker - Version alpha

Track new incoming order on the WebShop and display the results
on a USB 16x2 LCD
 
Use a USB+TTL 16x2 RGB LCD available at MCHobby
  http://shop.mchobby.be/product.php?id_product=475 

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

from prestaapi import PrestaHelper, CachedPrestaHelper, OrderStateList
from lcdmtrx import *
from config import Config
import logging
import time
import math

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

UPDATE_DELAY = 180 # seconds delay to reread the last order in the WebShop
cachedHelper = None
lcd = None

def showOrderInfo( lcd, cachedHelper, order_data ):
	""" Just display informations about the order """
	
	# Write Order ID
	sValid = 'VALID'
	if order_data.valid == 0:
		sValid = 'INVAL'
	sOrder = u'Order:%i %s' % (order_data.id, sValid)
	sOrder = sOrder[:16]
	sOrder.ljust( 16 )
	lcd.write_european_pos( 2, 1, sOrder )
	time.sleep( 2 )
	# Write Carrier 
	sCarrier = cachedHelper.carriers.name_from_id( order_data.id_carrier )
	sCarrier = (sCarrier[:16]).ljust( 16 )
	lcd.write_european_pos( 2, 1, sCarrier )
	time.sleep( 2 )
	# Write Status
	sOrderState = cachedHelper.order_states.name_from_id( order_data.current_state )
	sOrderState = (sOrderState[:16]).ljust( 16 )
	lcd.write_european_pos( 2, 1, sOrderState )
	time.sleep( 2 )
	# Write Type of Payment
	sPayment = order_data.payment
	sPayment = (sPayment[:16]).ljust( 16 )
	lcd.write_european_pos( 2, 1, sPayment )
	time.sleep( 2 )
	# Write Amount
	sAmount = (u'%.2f Eur' % order_data.total_paid)
	sAmount = (sAmount[:16]).rjust( 16 )
	lcd.write_european_pos( 2, 1, sAmount )
	time.sleep( 3 )
	
def setLcdColor( lcd, cachedHelper, order_data ):
	""" Set le LCD background color depending on order status """
	LcdColor = (255, 120, 120 ) # plutot blanc (Les LEDs vertes & bleues sont dominantes!) 
	# bOpenOrder = cachedHelper.order_states.is_open_order( order_data.current_state )
	bNewPayment = cachedHelper.order_states.is_new_order( order_data.current_state )
	if bNewPayment:
		sCarrier = cachedHelper.carriers.name_from_id( order_data.id_carrier )
		sCarrier = sCarrier.upper()
		# si Poste/Collisimo/UPS --> Urgent
		if sCarrier.find(u'UPS') >= 0:
			LcdColor = (255, 100, 0) # Jaune
		elif (sCarrier.find( u'BPACK' ) >= 0 ) or ( sCarrier.find( u'COLIS' ) >= 0 ) or ( sCarrier.find( u'HOME DELIVERY' ) >= 0 ) or ( sCarrier.find( u'PICK-UP POINT' ) >= 0 ) or ( sCarrier.find( u'PARCEL LOCKER' ) >= 0 ):
			LcdColor = (230, 10, 10) # Rouge leger
		elif sCarrier.find( u'MONDIAL' ) >= 0:
			LcdColor = (20, 135, 20 ) # Vert léger
		elif sCarrier.find( u'PICK' ) >= 0:
			LcdColor = (21, 153, 255 ) # Bleu pastel
		else:
			LcdColor = (255, 120, 120 ) # plutot blanc
	
		lcd.color( LcdColor[0], LcdColor[1], LcdColor[2] )  
	
def main():
	cachedHelper = CachedPrestaHelper( config.presta_api_url, config.presta_api_key, debug = False )
	lcd = EuropeLcdMatrix( config.lcd_device )
	lcd.create_european_charset()
	
	lcd.clear_screen()
	lcd.autoscroll( False );
	lcd.activate_lcd( True );
	lcd.write_european_pos( 1, 1, u'LcdOrderTrack' )
	lcd.write_european_pos( 2, 1, u'     starting...' )
		
	# default values for variable
	last_order_id = -1
	last_order_data = None
	bNewPayment     = False
	paid_count		= 0
	bankwire_count  = 0

	# Locate the ID_Payment for "Paiement par carte sur place"
	PAY_AT_MCH = None
	for order_state in cachedHelper.order_states:
		if cachedHelper.order_states.name_from_id( order_state.id ).upper().find(u'CARTE SUR PLACE') >= 0:
			PAY_AT_MCH = order_state.id

	try:
		# Force initial update
		last_update_time = time.time() - UPDATE_DELAY
		while True:
			if math.floor( time.time() - last_update_time ) >= UPDATE_DELAY:
				lcd.clear_screen()
				lcd.write_european( u'Updating...' )

				# Identifying the last Order!
				last_order_id = cachedHelper.get_lastorder_id()
				last_orders_data = cachedHelper.get_last_orders( last_order_id, count = 1 )
				# bOpenOrder = cachedHelper.order_states.is_open_order( last_orders_data[0].current_state )
				#   Exclude the REAPPROVISIONNEMENT state from light
				#   the LCD. Payment is effectively DONE but
				#   no work/shipping has to be prepared
				# New order with "Payment sur place" will deliver money shortly
				#   so it is also like a "new payment" --> switch on the light
				bNewPayment = (cachedHelper.order_states.is_new_order( last_orders_data[0].current_state) or (cachedHelper.order_states.name_from_id( last_orders_data[0].current_state ).upper().find(u'CARTE SUR PLACE')>=0 )) and ( last_orders_data[0].current_state != OrderStateList.ORDER_STATE_REPLENISH )
				
				# Activate LCD when receiving a new payment 
				setLcdColor( lcd, cachedHelper, last_orders_data[0] )
				lcd.activate_lcd( bNewPayment )
				paid_count = len( cachedHelper.get_order_ids( cachedHelper.order_states.ORDER_STATE_PAID ) )
				bankwire_count = len( cachedHelper.get_order_ids( cachedHelper.order_states.ORDER_STATE_WAIT_BANKWIRE ) )
				# Also add the "Paiement par carte sur place" in Bankwire count
				if PAY_AT_MCH:
					bankwire_count += len( cachedHelper.get_order_ids(PAY_AT_MCH))

				last_update_time = time.time()
			else: 
				sInfo = u'upd in %i sec' % int( UPDATE_DELAY - math.floor( time.time() - last_update_time ) )
				sInfo = (sInfo[:16]).ljust( 16 )
				lcd.write_european_pos( 2, 1, sInfo )
				time.sleep( 2 ) 
			
			# Show Count of payments
			sPayInfo = u'Pay %s | Vir %s' % (paid_count, bankwire_count)
			sPayInfo = sPayInfo.center( 16 )  
			lcd.write_european_pos( 1, 1, sPayInfo )
		
			# Show information about last Order
			showOrderInfo( lcd, cachedHelper, last_orders_data[0] )
			
	except Exception, e:
		lcd.clear_screen()
		lcd.write_european_pos( 'KABOUM!!' )
		lcd.write_european_pos( 2, 1, u'Restart in 5 Min' )
		logging.exception( e )
		time.sleep( 5*60 )
		os.system( 'sudo reboot' )
		return 0
	return 0

if __name__ == '__main__':
	logging.info( 'LcdOrderTrack Started' )
	main()
	logging.info( 'LcdOrderTrack End' )	
