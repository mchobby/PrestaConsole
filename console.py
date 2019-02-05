#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
""" console.py - prestashop console application

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
import warnings 
warnings.filterwarnings("ignore")

from prestaapi import PrestaHelper, CachedPrestaHelper, calculate_ean13
from prestaapi.prestahelpertest import run_prestahelper_tests
from config import Config
from pprint import pprint
import logging
import sys
import signal
import re
import traceback
import os
import xml.etree.cElementTree as etree

try:
	#from Tkinter import *
	import Tkinter, Tkconstants, tkFileDialog
except Exception as err:
	print( '[ERROR] Unable to load TKinter dependencies! %s' % err )

 
from labelprn import handle_print_for_product, handle_print_custom_label_large, handle_print_custom_label_small, handle_print_custom_label_king, \
		handle_print_warranty_label_large, handle_print_vat_label_large
# from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter

#RE_COMMAND                = "^\+([a-zA-Z])$"       # (command) +r OU +s 
#RE_COMMAND                 = "^(\w*)\s*(.*)\s*$"  # (command) +r ou +s 
                                                    # (command) <+demo> <param1 param2 paramN> 

#re_command       = re.compile( RE_COMMAND )

def catch_ctrl_C(sig,frame):
    print "Il est hors de question d'autoriser la sortie sauvage!"
signal.signal(signal.SIGINT, catch_ctrl_C)

#PRINTER_SHORTLABEL_QUEUE_NAME = 'zebra-raw'   # Small labels 25x30mm
#PRINTER_LARGELABEL_QUEUE_NAME = 'zebra-raw-l' # Large labels 25x70mm
#PRINTER_ENCODING = 'cp850'


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


def build_supplier_product_list( cachedphelper ):
	""" Build a list of product for that supplier (the default supplier) """
	r = []
	products = cachedphelper.get_products()
	for item in products:
		_cargo = Product_cargo( item )
		# Identify stock information
		stock = cachedphelper.stock_availables.stockavailable_from_id_product( _cargo.id )
		if stock:
			_cargo.qty_stock = stock.quantity
		r.append( _cargo )
	# Also locates all the IT-xxx articles.
	# They are NOT ACTIVE so we would not duplicate them 
	for item in products.inactivelist:
		if item.reference.find( 'IT-' ) == 0:
			_cargo = Product_cargo( item )
			# Identify stock information
			stock = cachedphelper.stock_availables.stockavailable_from_id_product( _cargo.id )
			if stock:
				_cargo.qty_stock = stock.quantity
			r.append( _cargo )			
	return r



def progressHandler( prestaProgressEvent ):
	if prestaProgressEvent.is_finished:
		print( '%s' %prestaProgressEvent.msg )
	else:
		print( '%i/%i - %s' % ( prestaProgressEvent.current_step, prestaProgressEvent.max_step, prestaProgressEvent.msg ) )


class BaseApp( object ):
	""" Basic Applicative class """

	def __init__( self, keywords, commands ):
		""" Initialize the application

		:params keywords: keywords and their equivalent
		:params commands: supported commands and parameters count
		"""
		self.config = Config()
		self.KEYWORDS = keywords
		self.COMMANDS = commands


		# initialize the logging
		logging.basicConfig( filename=self.config.logfile, level=logging.INFO, 
							 format='%(asctime)s - [%(levelname)s] %(message)s',
							 datefmt='%d/%m/%y %H:%M:%S.%f' )



		# A CachedPrestaHelper is a PrestaHelper with cache capabilities	
		self.cachedphelper = CachedPrestaHelper( self.config.presta_api_url, self.config.presta_api_key, debug = False, progressCallback = progressHandler )
		# Force loading cache
		#   cachedphelper.load_from_webshop()
		# Update Stock quantities
		#   cachedphelper.stock_availables.update_quantities()
		#tester = CachedPrestaHelperTest( cachedphelper )
		#tester.test_cache()

	def _normalize_keyword( self, sCmd ):
		""" try to replace each item of a command by it normalized item (otherwise the original value) """
		_s = sCmd.lower().strip()
		for key, values in self.KEYWORDS.iteritems():
			if (_s == key) or (_s in values):
				return key  
		return sCmd

	def _decode_command( self, sCmd ):
		""" Extract the command and parameters from the command string. """
		if len( sCmd.strip() )==0:
			return( None, [] )

		keywords = sCmd.split() # fait déjà un strip des paramètres
		_r = []
		for word in keywords: 
			_normalized = self._normalize_keyword( word )
			if _normalized: # Some words (to from) are replaced by None 
				_r.append( _normalized )
		params = _r # apply the new parameter

		# Treat really special case 
		#   Backward compatibility
		if (len( params ) == 1) and not( params[0] in self.KEYWORDS ) and \
		    not( any([item for item in self.COMMANDS if item[0]==params[0]]) ): # Note: somes command makes only one word (and are not keyword)
			# we are looking for product OR having a product ID
			if params[0].isdigit(): # it is an ID
				params.insert(0, 'print')
				params.insert(1, 'product')
			else:  # it is a string ... so a product search
				params.insert(0, 'list')
				params.insert(1, 'product')

		# try to catch a command the normalized params
		r_cmd    = None # Command detected
		r_params = []   # Command parameters 
		r_func   = None # Command function to call
		sNormCmd = ' '.join( params )
		for a_cmd, param_count in self.COMMANDS:
			if (a_cmd in sNormCmd) and (sNormCmd.index(a_cmd)==0):
				r_cmd = a_cmd
				sNormCmd = sNormCmd.replace( a_cmd, '' )
				r_params = sNormCmd.split()
				# Check parameter count
				if param_count == '*':
					# 0..N parameter allowed 
					pass
				elif param_count == '+':
					if len(r_params)<1:
						raise Exeption( 'At least one parameter required for "%s"' % r_cmd )
				elif param_count == None:
					pass
				elif type(param_count) is int:
					if len(r_params) != int(param_count):
						raise ValueError( '%i parameters expected for "%s"' % ( int(param_count), r_cmd) )
				break

		return r_cmd, r_params # return the command in the list of keywords

	def evaluate_line( self, value ):
		""" Decode and execute a command line. Caller must handle Exception!!!

		:param value: the command line (string) to evaluate
		"""
		cmd, params = self._decode_command( value )
		if cmd == None:
			print( 'unknow command "%s"' % value )
			return

		# retreive the function to call
		sFuncName = 'do_%s' % cmd.replace( ' ', '_' )
		_func = getattr( self, sFuncName )

		# call it
		if self.cachedphelper.debug:
			print( 'calling %s with params %s (%s)' % (sFuncName, params, cmd) )
		_func( params )

	def evaluate_lines( self, lst ):
		""" Evaluate all the lines contained into a list (like run() does). """ 
		for value in lst:
			try:
				value = value.replace('\r','').replace('\n','')
				print( '> %s' % value )
				self.evaluate_line( value )
			except Exception as err:
				print( '[ERROR] %s' % err )
				if self.cachedphelper.debug:
					traceback.print_exc()

	def run( self ):
		""" Run the main cmd line requests loop """
		value = ''
		while value != 'quit':
			try:
				value = raw_input( '> ' )
				self.evaluate_line( value )
				print('')

			except Exception as err:
				print( '[ERROR] %s' % err )
				if self.cachedphelper.debug:
					traceback.print_exc()

# ===========================================================================
#
#       APPLICATION
#
# ===========================================================================

KEYWORDS = {
	'list'    : ['ls'],
	'product' : ['prod','arti', 'article'],
	'supplier': ['sup', 'supp', 'four'],
	'ean'     : ['ean'],
	'print'   : ['prn'],
	'reload'  : ['r'], # reload the data
	'update'  : ['u'], # update stock quantities
	'quit'    : ['q', 'exit'],
	'help'    : ['?', 'h'],
	'stock'   : ['s'],
	'1'       : ['true'],
    '0'       : ['false'],
	None      : ['to', 'from'] # remove any from and to

}

# Commands + Needed parameters + function to call
#    Needed Parameter '+': 1 or more, '*': 0 or mode, numeric (exactly X values)
COMMANDS = [
	('ean'            , 1   ), 
	('help keyword'   , 1   ),
	('help command'   , 0   ),
	('help'           , 0   ),
    ('list product'   , '+' ),  
	('list supplier'  , '*' ), 
	('print product'  , 1   ), 
	('print small'    , 0   ),
	('print large'    , 0   ),
	('print king'     , 0   ),
	('print war'      , 0   ),
	('print vat'      , 0   ),
	('quit'           , 0   ),
	('reload stock'   , 0   ),
	('reload'         , 0   ),
	('save'           , 0   ),
	('set debug'      , 1   ),
	('set option'     , 2   ),
	('show debug'     , 0   ),
	('show option'    , '*' ),
	('show stat'      , 0   ),
	('upgrade'        , 0   )
	]


class App( BaseApp ):
	""" Handle the application """

	def __init__( self ):
		super( App, self ).__init__( KEYWORDS, COMMANDS )
		self.ID_SUPPLIER_PARAMS = None  # LABEL Size is stored into the article reference of the "PARAMS" supplier.
		 # Maintains the application options
		self.options = { 'show-product-pa'   : '1',
						 'show-product-pv'   : '1',
						 'show-product-label': '0',
						 'inactive-product'  : '0',
						 'include-it'        : '0'
					   }

		# Init params from load data
		self.__init_from_loaded_data() 

	def __init_from_loaded_data( self ):
		""" Initialize special parameters the loaded webshop data (file of WebShop) """
		self.ID_SUPPLIER_PARAMS = None

		_item = self.cachedphelper.suppliers.supplier_from_name( "PARAMS" )
		if _item != None:
			self.ID_SUPPLIER_PARAMS = _item.id	

	def get_product_params( self, id_product ):
		""" Locate the product parameter stored in the PARAMS supplier reference for that product.
			The PARAMS supplier is encoded as follows:     param1:value1,param2:value2 """
		
		# If this special PARAMS supplier is not yet identified then
		#   not possible to locate the special product parameter
		#   stored there 
		if self.ID_SUPPLIER_PARAMS == None:
			return {}
		
		reference = self.cachedphelper.product_suppliers.reference_for( id_product, self.ID_SUPPLIER_PARAMS )
		# print( 'reference: %s' % reference )
		if len(reference )==0:
			return {}
		
		result = {}
		lst = reference.split(',')
		for item in lst:
			vals = item.split(':')
			if len( vals )!= 2:
				raise Exception( 'Invalid product PARAMS "%s" in "%s". it must have 2 parts (colon separated!)' % (vals, reference) )
			result[vals[0]] = vals[1]
		
		return result

	def output_product_search_result( self, psr_list ):
		""" output the list of product (ProductSearchResult list). The default destination is the screen (but may vary depending on options) """
		if len( psr_list )<=0:
			return

		sTitle = '%7s | %-30s | %5s' % ('ID', 'Reference', 'qty' )
		sPrint = '%7i | %-30s | %5i'
		if self.options['show-product-label'] == '1':
			sTitle += ' | %-50s' % 'Label'
			sPrint += ' | %-50s'
		if self.options['show-product-pa'] == '1':
			sTitle += ' | %6s' % 'P.A.'
			sPrint += ' | %6.2f'
		if self.options['show-product-pv'] == '1':
			sTitle += ' | %15s' % 'P.V. (PV ttc)'
			sPrint += ' | %6.2f (%6.2f)'
		sTitle += ' | %-20s' % 'Supp. Ref.'
		sPrint += ' | %-50s'

		show_IT_product = self.options['include-it'] == '1'
		show_inactive   = self.options['inactive-product'] == '1'

		print( sTitle )
		print( '-'*len(sTitle))
		_count = 0
		for psr in  psr_list : # Returns a list of ProductSearchResult
			if psr.product_data.is_IT and not(show_IT_product):
				continue
			if (psr.product_data.active==0) and not(show_inactive):
				continue 

			# prepare the data
			_lst = [psr.product_data.id, psr.product_data.reference, psr.qty ]
			if self.options['show-product-label'] == '1':
				_lst.append( psr.product_data.name )
			if self.options['show-product-pa'] == '1':
				_lst.append( psr.product_data.wholesale_price )
			if self.options['show-product-pv'] == '1':
				_lst.append( psr.product_data.price )
				_lst.append( psr.product_data.price * (1.06 if 'BK-' in psr.product_data.reference else 1.21) )
			_lst.append( psr.supplier_refs )

			# Go for display
			print( sPrint % tuple( _lst ) )
			_count += 1

		print( '%s items in result' % _count )

			#print( '%7i : %s : %5i : %s - %s' % ( \
			#	psr.product_data.id, \
			#	psr.product_data.reference.ljust(30), \
			#	psr.qty, \
			#	psr.product_data.name.ljust(50), \
			#	psr.supplier_refs ) )

	# ---------------------------------------------------------------------------
	#
	#   COMMANDs execution
	#
	# ---------------------------------------------------------------------------
	def do_ean( self, params ):
		""" Generates the EAN13 for the ID_Product """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID product'

		_id = int( params[0] )
		product_ean = '32321%07i' % _id  # prefix 3232 + product 1 + id_product
		product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
		print( '%s' % product_ean )				

	def do_help( self, params ):
		""" Display Help """
		os.system( 'less console.help' )	

	def do_help_keyword( self, params ):
		""" Display keyword equivalents for params """
		kw = params[0].lower()
		if not kw in self.KEYWORDS:
			raise ValueError( '%s is not a valid keyword!' % kw )
		print( '"%s" equivalence are %s' % (kw, ', '.join( self.KEYWORDS[kw])) )

	def do_help_command( self, params ):
		""" Display list of commands """
		for cmd, param_count in self.COMMANDS:
			print( "%s %s" % (cmd, "<%s>" % param_count if param_count!=0 else "" ) )

	def do_list_product( self, params ):
		""" Search for a product base on its partial reference code + list them """
		assert len(params)>0 and isinstance( params[0], str ), 'the parameter must be a string'
		key = params[0]
		if len( key ) < 3:
			raise ValueError( 'searching product requires at least 3 characters' )
		
		if key[0] == '/':  # search on Supplier Ref
			result = self.cachedphelper.search_products_from_supplier_ref( key[1:], include_inactives = True ) # Skip the /
		elif key[0] == '*': # search on label
			result = self.cachedphelper.search_products_from_label( key[1:], include_inactives = True ) # Skip the *
		else:
			result = self.cachedphelper.search_products_from_partialref( key, include_inactives = True )
		
		self.output_product_search_result( psr_list = result )


	def do_list_supplier( self, params ):
		""" Show the list of suppliers (or product inside the supplier if only one produc) """
		def show_product_list( id_supplier ):
			# build the product list
			print( '='*30 )
			print( '    %s supplier list (%i)' % (self.cachedphelper.suppliers.supplier_from_id(id_supplier).name, id_supplier)  )
			print( '='*30 )
			psr_lst = self.cachedphelper.search_products_from_supplier( id_supplier, include_inactives=(self.options['inactive-product']=='1') )
			sorted_lst = sorted( psr_lst, key=lambda item:item.product_data.reference.upper() )
			self.output_product_search_result( psr_list = sorted_lst )

		if ( len(params)>0 ) and ( params[0].isdigit() ):
			# we have an ID Supplier in parameter --> Show the products
			id_supplier = int( params[0] )
			show_product_list( id_supplier )
		else:
			# Sort the list
			sorted_lst = sorted( self.cachedphelper.suppliers, key=lambda item:item.name.lower() )
			# reduce the list
			if len(params)>0:
				_lst = [ item for item in sorted_lst if params[0].lower() in item.name.lower() ]
			else:
				_lst = sorted_lst
			# show the list of supplier
			for sup in _lst:
				print(  '%4i : %s ' % (sup.id, sup.name) )
			# show product list (if only one supplier returned)
			if len( _lst )==1:
				id_supplier = int( _lst[0].id )
				show_product_list( id_supplier )	

	def do_print_small( self, params ):
		handle_print_custom_label_small()

	def do_print_king( self, params ):
		handle_print_custom_label_king()

	def do_print_large( self, params ):
		handle_print_custom_label_large()

	def do_print_product( self, params ):
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID product'

		_id = int( params[0] )
		_product = self.cachedphelper.products.product_from_id( _id )
		handle_print_for_product( _product, self.get_product_params( _id ) )

	def do_print_war( self, params ):
		handle_print_warranty_label_large()

	def do_print_vat( self, params ):
		handle_print_vat_label_large()

	def do_quit( self, params ):
		print( "User exit!")
		sys.exit(0)

	def do_reload( self,  params ):
		""" Reload ALL the data from the WebShow """
		print( 'Contacting WebShop and reloading...' )
		self.cachedphelper.load_from_webshop()
		self.__init_from_loaded_data() # reinit global variables

	def do_reload_stock( self, params ):
		""" Reload the stock quantities only. """
		print( 'Refreshing stock quantities...' )
		self.cachedphelper.refresh_stock()

	def do_save( self, params ):
		""" Save the memory data to the cache file """
		print( 'Saving cache...' )
		self.cachedphelper.save_cache_file()

	def do_show_debug( self, params ):
		""" Show lot of information for inner debugging """
		print( 'debug              : %s' % ('True' if self.cachedphelper.debug else 'false') )
		print( 'last product id    : %s' % self.cachedphelper.products.last_id )

		print( 'PARAMS id_supplier : %i' % self.ID_SUPPLIER_PARAMS )
		print( 'list of option     :' )
		self.do_show_option( params=[], prefix='      ')

	def do_set_debug( self, params ):
		""" Toggle the debug flag """
		self.cachedphelper.debug = (params[0] == '1')

	def do_set_option( self, params ):
		""" Update the value of an option """
		sName = params[0]
		sValue = params[1]

		if not sName in self.options:
			raise ValueError( 'Invalid option name %s' % sName )

		if sValue == '\'\'':
			sValue = ''  # make empty string

		self.options[sName]=sValue

	def do_show_option( self, params, prefix = '' ):
		""" Show the console option (all or the mentionned one) """
		if len(params)>0:
			if params[0] in self.options:
				print( prefix+'%-20s = %s' % (params[0], self.options[params[0]]) )
			else:
				raise ValueError( '%s is not a valid option' % params[0] )
		else:
			# show all params	
			for key_val in self.options.iteritems():
				print( prefix+'%-20s = %s' % key_val )

	def do_show_stat( self, params ):
		""" Display the cachec helper statistics """
		print( '%6i Carriers' % len(self.cachedphelper.carriers) )
		print( '%6i OrderStates' % len( self.cachedphelper.order_states ) )
		print( '%6i Products' % len( self.cachedphelper.products ) )
		print( '%6i suppliers' % len( self.cachedphelper.suppliers ) )
		print( '%6i categories' % len( self.cachedphelper.categories ) )
		print( '%6i stock availables' % len( self.cachedphelper.stock_availables ) )
		print( '%6i product suppliers available' % len( self.cachedphelper.product_suppliers ) )
		print( '%6i last product id' % self.cachedphelper.products.last_id )

	def do_upgrade( self, params ):
		""" Just upgrade the software from GitHub depot. """
		if os.system( 'git fetch' )!=0:
			raise Exception( 'git fetching failure!' )
		if os.system( 'git pull' )!=0:
			raise Exception( 'git pulling failure!')


def main():
	app = App()
	if os.path.isfile( 'console.startup' ):
		with open( 'console.startup', 'r' ) as f:
			lines = f.readlines()
			app.evaluate_lines( lines )

	app.run()


if __name__ == '__main__':
	main()

