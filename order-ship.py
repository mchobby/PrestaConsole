#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

from prestaapi import PrestaHelper, CachedPrestaHelper, OrderStateList
from output import PrestaOut
from config import Config
from pprint import pprint
import logging
import sys, os, codecs
import re, subprocess
import signal
import datetime
# debugging
from xml.etree import ElementTree
#
from enum import Enum

config = Config()
h = CachedPrestaHelper( config.presta_api_url, config.presta_api_key, debug= False )
#print ("#products = %i" % ( len( h.products ) ) )

class AppState( Enum ):
	WAIT_ORDER    = 0
	CONTROL_ORDER = 1
	WAIT_SHIPPING = 2
	CONTROLED     = 3
	APPEND_ORDER  = 4 # Wait state to append an order

class CMD( Enum ):
	RAW = 0
	VERB = 1 # The text value is one of the Verbs dic
	SET_CARRIER = 2 # Setting the CARRIERS (one of CARRIERS dic), so setting the CARRIER
	LOAD_ORDER  = 3 # Loading an ORDER
	SCAN_PRODUCT= 4 # Scanning a product
	APPEND_ORDER= 5 # Append ANOTHER order to existing one

# Code barre verbs
VERBS = { '3232900000010' : 'CANCEL'   , # 1:
 		  '3232900000027' : 'OK'       , # 2:
		  '3232900000034' : 'CHECK'    , # 3: check (if shipping is ok)
		  '3232900000041' : 'FINALIZE' , # 4: finalize (the shipping by sending mail & archiving)
		  '3232900000058' : 'RESET'    , # 5: Reset
		  '3232900000065' : 'APPEND'     # 6: Append an order to shipping
		  }

CARRIERS = { '3232800010003' : 'POSTE'  , # 1000
			 '3232800010010' : 'MR'     , # 1001
			 '3232800010027' : 'UPS'    , # 1002
			 '3232800010034' : 'DHL'    , # 1003
			 '3232800010041' : 'PICKUP'   # 1004
}

class EanType( Enum ):
	# Used to detect the type of ean_barcode
	UNDEFINED = 0
	VERB = 1
	CARRIER = 2
	PRODUCT = 3
	ORDER = 4

def ean_type( ean ):
	""" Try to figure out which is the type of ean enclosed within the EAN string """
	if ean.startswith("32321"):
		return EanType.PRODUCT
	elif ean.startswith("324"):
		return EanType.ORDER
	elif ean.startswith("32329"):
		return EanType.VERB
	elif ean.startswith("32328"):
		return EanType.CARRIER
	else:
		return EanType.UNDEFINED

RE_ADD_REMOVE_SEVERAL_ID= "^(\+|\-)(\d+)\*(\d+)$"          # +3*125 OU -4*1024
re_add_remove_several_id = re.compile( RE_ADD_REMOVE_SEVERAL_ID )

class OrderShipApp():
	def __init__( self ):
		self.config = Config()
		self.h = CachedPrestaHelper( self.config.presta_api_url, self.config.presta_api_key, debug= False )
		self.output = PrestaOut()
		self.state  = AppState.WAIT_ORDER
		# Loaded order
		self.order    = None
		self.joined_order = [] # other order joined to the shipping
		self.customer = None
		self.carrier  = ''
		self.shipping_number = ''
		self.output.writeln( "Application initialized" )

	def test_storage_paths( self ):
		# Test the existence of data path and write access, raise exception in case of error
		self.output.writeln( "Testing paths..." )
		with open( os.path.join(self.config.order_ship_data_path, 'testfile.txt'), "a") as f:
			f.write( 'test access @ %s \r\n' % datetime.datetime.now() )

	def order_filename( self, order ):
		""" Return a tuple (filepath, filename) to use in order to store the order-data """
		# order.date_add have the format '2019-08-21 16:02:29'
		# '2019-08-21 16:02:29' => '201908'... Store by year and month
		return ( os.path.join( self.config.order_ship_data_path, order.date_add.replace('-','')[0:6] ), '%s.scan' % order.id )

	def is_order_file_exists( self, order ):
		""" Check if a data file is already stored for that order """
		path, filename = self.order_filename( order )
		try:
			os.makedirs( path )
		except:
			pass # don't raise error is path already exists
		return os.path.exists( os.path.join(path, filename) )

	def beep( self, success=False, notif=False ):
		""" Rely of audio output to signal error """
		#os.system( "mpg123 %s" % "error.mp3" )
		_name = 'error.mp3'
		if success:
			_name = 'tada.mp3'
		if notif:
			_name = 'notif.mp3'
		r_ = subprocess.Popen(['mpg123',_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE )

	def get_cmd( self, prompt='> ', debug=False ):
		""" request an command. Return a tuple (cmd_type, cmd_texte) """
		global re_add_remove_several_id
		v = ''
		while len(v)==0:
			v = v = raw_input( prompt )
			v = v.strip()

		# Manage the multiplier case
		_cmd_multiplier = 1
		g = re_add_remove_several_id.match( v )
		if g:
			# Extract the data - Qty and ID
			sign   = g.groups()[0]
			qty    = int( g.groups()[1] )
			remain = g.groups()[2]
			# Evaluate Multiplier
			_cmd_multiplier = qty if sign!="-" else -1*qty
			v = remain # command = everything after * sign

		# decode command
		_cmd_type = None
		_cmd_data = None
		_ean_type = ean_type( v )
		if _ean_type == EanType.VERB:
			# decode a VERB barre code
			_cmd_type = CMD.VERB
			_cmd_data = VERBS[v] # Convert ean to VERB text
			# Special VERB to translate in action
			if _cmd_data == 'APPEND':
				_cmd_type = CMD.APPEND_ORDER

		elif _ean_type == EanType.CARRIER:
			# decode the CARRIER barre code
			_cmd_type = CMD.SET_CARRIER
			_cmd_data = CARRIERS[v] # Convert ean to CARRIER name
		elif _ean_type == EanType.PRODUCT:
			# Retreive the product ID from EAN
			_lst = self.h.products.search_products_for_ean( v )
			if len(_lst)==0:
				_cmd_type = CMD.RAW
				_cmd_data = v
			else:
				_cmd_type = CMD.SCAN_PRODUCT
				_cmd_data = _lst[0].id
		elif _ean_type == EanType.ORDER:
			# Extract the order ID
			_cmd_type = CMD.LOAD_ORDER
			_cmd_data = int(v[-8:-1]) # Extract order ID from ean
		else: # it is EanType.UNDEFINED
			_cmd_type = CMD.RAW
			_cmd_data = v
		if debug:
			print( "Cmd type, data, mult : %s, %s, %i   - EanType %s" % (CMD(_cmd_type).name, _cmd_data, _cmd_multiplier,EanType(_ean_type).name) )
		return (_cmd_type, _cmd_data, _cmd_multiplier ) # , _ean_type )


	def check_scanned( self ):
		# Check if the scanned items correspond to the order !
		_flag = True
		self.output.writeln( '-'*80)
		self.output.writeln( 'Order   : %s' % self.order.id )
		for _joined_order in self.joined_order:
			self.output.writeln( '          joined %s' % _joined_order.id )
		self.output.writeln( 'Carrier : %s' % (self.carrier if self.carrier else '-!-') )
		if len(self.carrier)==0:
			_flag = False
		self.output.writeln( 'Ship Nr : %s' % (self.shipping_number if self.shipping_number else '-!-') )
		if len(self.shipping_number)==0:
			_flag = False
		self.output.writeln( '-'*80)
		self.output.writeln( 'Status| Scan | Order | Detail ' )
		self.output.writeln( '-'*80)
		for row in self.order.rows:
			_ok     = row.ordered_qty == self.scan[row.id_product]
			_status = 'OK' if _ok else '-!-'
			if not(_ok):
				_flag = False
			self.output.writeln( '%5s | %4i | %5i | %s ' % (_status,self.scan[row.id_product],row.ordered_qty,row) )
		return _flag

	def reset_all( self ):
		self.order = None
		self.joined_order = [] # Other order added to the shipping
		self.scan  = None
		self.customer = None
		self.state = AppState.WAIT_ORDER
		self.carrier  = ''
		self.shipping_number = ''
		self.output.reset_carbon_copy()
		for i in range( 5 ):
			print( " " ) # Do not register this message
		self.output.writeln( "Reset done!" )
		for i in range( 5 ):
			print( " " ) # Do not register this message


	def run( self ):
		""" Main application loop """
		# Test access to data_path
		self.test_storage_paths()
		self.output.set_carbon_copy()

		cmd_type,cmd_data, cmd_mult = CMD.RAW, '', 1
		while not((cmd_type==CMD.RAW) and (cmd_data.upper()=='EXIT')):
			cmd_type,cmd_data,cmd_mult = self.get_cmd( prompt="%-13s > "%AppState(self.state).name, debug=False)

			# -- Append extra info to CarbonCopy -------------------------------
			self.output.carbon_copy.append(  'CMD: %s, %s, %s' % (cmd_type,cmd_data,cmd_mult))
			# -- Reset All -----------------------------------------------------
			if (cmd_type == CMD.VERB and cmd_data == 'RESET' ):
				self.reset_all()
				continue

			# -- Loading an order ----------------------------------------------
			if (self.state == AppState.WAIT_ORDER) and (cmd_type == CMD.LOAD_ORDER):
				self.output.writeln( "Loading order %s" % cmd_data )
				# load the order
				orders = self.h.get_last_orders( int(cmd_data), 1 )
				if len( orders ) <= 0:
					self.output.writeln( "[ERROR] order %s not found!" % (cmd_data) )
					self.beep()
					continue
				# Check if the order has already been managed
				if self.is_order_file_exists( orders[0] ):
					self.output.writeln( "[ERROR] scanfile already exists for this order!" )
					self.output.writeln( "[ERROR] %s/%s" % self.order_filename( orders[0]) )
					self.beep()
					continue # Skip remaining of loading

				# Start managing the order
				self.order = orders[0]
				self.joined_order = []
				self.carrier  = ''
				self.shipping_number = ''
				self.customer = self.h.get_customer( self.order.id_customer )
				self.state    = AppState.CONTROL_ORDER

				self.output.reset_carbon_copy() # we will keep a copy of everything
				self.output.writeln( '--- Order ID : %i ---' % self.order.id )
				# self.output.writeln( 'Shop ID      : %s' % order.id_shop )
				self.output.writeln( 'Customer     : %s' % self.customer.customer_name )
				self.output.writeln( 'Cust.EMail   : %s' % self.customer.email )
				self.output.writeln( 'Order Date   : %s' % self.order.date_add )


				# Content the order
				self.scan = {}
				for row in self.order.rows:
					self.output.writeln( row )
					self.scan[row.id_product] = 0
				continue

			# -- Scan Product --------------------------------------------------
			if (cmd_type == CMD.SCAN_PRODUCT):
				if self.state != AppState.CONTROL_ORDER:
					self.output.writeln("[ERROR] No order loaded")
					self.beep()
				else:
					# Is the product in the order list
					if any( [ int(cmd_data) == int(product.id_product) for product in self.order.rows ] ):
						_items = [ product for product in self.order.rows if int(cmd_data) == int(product.id_product) ]
						_product = _items[0]
						if cmd_mult + self.scan[_product.id_product] > _product.ordered_qty :
							self.output.writeln( '[ERROR] %i * %s (%s) product CANNOT BE ADDED!' % (cmd_mult, _product.reference, _product.id_product) )
							self.output.writeln( '[ERROR] Ordered: %i, Current Scan: %i' %(_product.ordered_qty,self.scan[_product.id_product]) )
							self.beep()
						else:
							self.scan[_product.id_product] = self.scan[_product.id_product] + cmd_mult
					else:
						self.output.writeln( "[ERROR] Product %s not in the order!" % cmd_data )
						self.beep()
				continue

			# -- Append order --------------------------------------------------
			# User selected APPEND ORDER carcode
			if (cmd_type == CMD.APPEND_ORDER):
				if self.state != AppState.CONTROL_ORDER:
					self.output.writeln("[ERROR] No order loaded")
					self.beep()
				else:
					self.output.writeln("SELECT order TO APPEND to shipping!")
					self.state = AppState.APPEND_ORDER
					self.beep( notif=True )
				continue

			# user selected an order
			if (self.state == AppState.APPEND_ORDER) and (cmd_type == CMD.LOAD_ORDER):
				self.output.writeln( "Append order %s" % cmd_data )
				# load the order
				orders = self.h.get_last_orders( int(cmd_data), 1 )
				if len( orders ) <= 0:
					self.output.writeln( "[ERROR] order %s not found!" % (cmd_data) )
					self.beep()
					continue
				# Check if the order has already been managed
				if self.is_order_file_exists( orders[0] ):
					self.output.writeln( "[ERROR] scanfile already exists for this order!" )
					self.output.writeln( "[ERROR] %s/%s" % self.order_filename( orders[0]) )
					self.beep()
					continue # Skip remaining of loading

				# Start appending the loaded order
				self.joined_order.append( orders[0] )
				for row in orders[0].rows: # rows in joined order
					self.output.writeln( "Append %s" % row )
					if not( row.id_product in self.scan ):
						self.scan[row.id_product] = 0
					_matching_rows = [ _row for _row in self.order.rows if _row.id_product == row.id_product ]
					if len( _matching_rows )>0:
						_matching_rows[0].ordered_qty += row.ordered_qty # Appending qty to existing order's row
					else:
						self.order.rows.append( row )


				self.output.writeln( "Order %i succesfuly added" % orders[0].id )
				self.state = AppState.CONTROL_ORDER # Return to control order state
				continue

			# user selected CANCEL BarCode
			if (self.state == AppState.APPEND_ORDER) and (cmd_type == CMD.VERB and cmd_data == 'CANCEL' ):
				self.output.writeln( "Order appending canceled!")
				self.state = AppState.CONTROL_ORDER
				continue

			# -- Capture Carrier -----------------------------------------------
			if (cmd_type == CMD.SET_CARRIER ):
				if self.state != AppState.CONTROL_ORDER:
					self.output.writeln("[ERROR] No order loaded")
					self.beep()
				else:
					self.state = AppState.WAIT_SHIPPING
					self.carrier = cmd_data
					self.beep( notif=True )
				continue

			# -- Capture Number -----------------------------------------------
			if ((cmd_type == CMD.RAW) and (self.state == AppState.WAIT_SHIPPING) ):
				if len(cmd_data)>0 :
					self.shipping_number = cmd_data
					# GetBack to previous state
					self.state = AppState.CONTROL_ORDER
				continue

			# -- Check ---------------------------------------------------------
			if (cmd_type == CMD.VERB and cmd_data == 'CHECK' ):
				if self.state != AppState.CONTROL_ORDER:
					self.output.writeln("[ERROR] No order loaded")
					self.beep()
				else:
					# Did it worked properly ?
					if not( self.check_scanned() ):
						self.beep()
					else:
						self.beep( success=True )
				continue

			# -- Finalize ------------------------------------------------------
			if (cmd_type == CMD.VERB and cmd_data == 'FINALIZE' ):
				if self.state != AppState.CONTROL_ORDER:
					self.output.writeln("[ERROR] No order loaded")
					self.beep()
				else:
					if not( self.check_scanned() ):
						self.beep()
						continue
					self.output.writeln("")
					self.output.writeln("ORDER CHECK SUCCESSFULLY")
					self.output.writeln("")
					self.output.writeln( 'OPERATION DATE : %s' % datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") )
					# Save the scan file.
					_path, _filename = self.order_filename(self.order)
					self.output.save_carbon_copy( os.path.join( _path, _filename ) )
					# Save all the joined order
					for _joined_order in self.joined_order:
						_joined_filename =  os.path.join( *(self.order_filename(_joined_order) ))
						with codecs.open( _joined_filename , 'w', 'utf-8' ) as f:
							f.write( '--- Order ID : %s ---\r\n' % _joined_order.id )
							f.write( 'JOINED TO ORDER : %s\r\n' % self.order.id )
							f.write( 'SEE SCAN : %s\r\n' % os.path.join( _path, _filename ) ) # Mention original filename1
							f.write( 'OPERATION DATE : %s' % datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S") )
					# Reset for next scan session
					self.reset_all()
					self.beep( success=True )
					continue

			# == Reaching this Point --> Error ===s==============================
			self.output.writeln("[ERROR] UNKNOWN instruction scan or ean scan!")
			self.beep()

		self.output.writeln( 'User exit!' )

app = OrderShipApp()
app.run()
sys.exit(0)

# Cmd de test 8042
cmd_nr = raw_input( '#Commande: ' )
if not cmd_nr.isdigit():
   raise ValueError( '%s is not a number' % cmd_nr )


orders = h.get_last_orders( int(cmd_nr), 1 )
if len( orders ) <= 0:
    raise ValueError( 'order %s not found' % cmd_nr )

order = orders[0]
customer = h.get_customer( order.id_customer )

print( '--- Order ID : %i ---' % order.id )
print( 'Shop ID      : %s' % order.id_shop )
# print( 'Carrier   ID : %i' % order.id_carrier )
# print( 'current state: %i' % order.current_state )
# print( 'Customer  ID : %i' % order.id_customer )
print( 'Customer     : %s' % customer.customer_name )
print( 'Cust.EMail   : %s' % customer.email )
print( 'Carrier      : %s' % h.carriers.carrier_from_id( order.id_carrier ).name )
print( 'Current State: %s' % h.order_states.order_state_from_id( order.current_state ).name )
print( 'valid        : %i' % order.valid )
print( 'payment      : %s' % order.payment )
print( 'total HTVA   : %.2f' % order.total_paid_tax_excl )
print( 'total Paid   : %.2f' % order.total_paid )
print( 'Shipping Nr  : %s'   % order.shipping_number )
# Content the order
for row in order.rows:
	print( row )


# Update the order current_status
"""order = list( el_prestashop )[0]
order_properties = list( order )
order_current_state = [ order_property for order_property in order_properties if order_property.tag == 'current_state' ]
order_current_state[0].text = str( OrderStateList.ORDER_STATE_SHIPPING )
#print( ElementTree.tostring( el_prestashop ) )
"""

""" Activate error detection
      http://stackoverflow.com/questions/14457470/prestapyt-error-on-edit
    A sample of XML to send
      http://nullege.com/codes/show/src%40p%40r%40prestapyt-HEAD%40examples%40prestapyt_xml.py/22/prestapyt.PrestaShopWebService.edit/python
"""
# Save the order
print( 'post_order_data() call deactivated' )
#h.post_order_data( int(cmd_nr), el_prestashop )

#print( order_properties[0].tag )
#print( order_properties[0].text )
#print( order_properties[0].attrib )
