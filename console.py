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

from prestaapi import PrestaHelper, CachedPrestaHelper, calculate_ean13, ProductSearchResult, ProductSearchResultList, OrderStateList, recompute_id_product, unmangle_id_product, is_combination
from output import PrestaOut
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
import tempfile
import datetime
from bag import ToteBag, ToteItem
from batch import BatchFactory, EBatch
import cmd
import sys
import re
import subprocess

try:
	from Tkinter import *
	import Tkinter, Tkconstants, tkFileDialog
except Exception as err:
	print( '[ERROR] Unable to load TKinter dependencies! %s' % err )


from labelprn import handle_print_for_product, print_custom_label_small, handle_print_custom_label_large, handle_print_custom_label_small, handle_print_custom_label_king, \
		handle_print_warranty_label_large, handle_print_vat_label_large, handle_print_ean_label_large, ean12_to_ean13, handle_print_conformity_label_small, \
		handle_print_esd_label_large
from labelprn import printer_shortlabel_queue_name, printer_largelabel_queue_name , printer_ticket_queue_name
from labelprn import print_ticket_batch, print_ticket_transformation

def catch_ctrl_C(sig,frame):
    print "Il est hors de question d'autoriser la sortie sauvage!"
signal.signal(signal.SIGINT, catch_ctrl_C)


def progressHandler( prestaProgressEvent ):
	if prestaProgressEvent.is_finished:
		print( '%s' %prestaProgressEvent.msg )
	else:
		print( '%i/%i - %s' % ( prestaProgressEvent.current_step, prestaProgressEvent.max_step, prestaProgressEvent.msg ) )

def request_text( prompt = 'text (+q to quit) ?', default=None ):
	""" Request a text """
	value = raw_input( prompt )
	if value == '+q':
		return None
	if (value == '') and default:
		return default
	return value

def request_re( prompt, re_string ):
	""" Request a value and check it against a RE expression """
	_re = re.compile( re_string )
	while True:
		value = request_text( prompt )
		# Empty result
		if value == None:
			return None
		# Re-match ?
		_match = _re.match( value )
		if not _match:
			continue
		return _match.string

def request_expiration( prompt ):
	""" Request an expiration date at format mm/yyyy """
	while True:
		value = request_re( prompt, re_string = "\d\d/\d\d\d\d")
		if value == None:
			return None
		# check Month value
		month, year = value.split( '/' )
		if not( 1 <= int(month)<= 12 ):
			print( "invalid month" )
			continue
		if not( 2019 <= int(year) <= 2034 ):
			print( "invalid year" )
			continue
		return value

def request_int( prompt = 'How many items ?', confirm_from_value=25 ):
	""" Request a quantity and confirm it if greater than confirm_from_value """
	value = raw_input( prompt )
	if value == 0:
		return None
	if value == '+q':
		return None
	if value == '': # By default, 1 label
		value = 1

	qty = int( value )
	if qty > confirm_from_value:
		value2 = raw_input( 'Quantity > %s! Please confirm: ' % confirm_from_value )
		if not value2.isdigit():
			print( '%s is not a numeric value, ABORT!' % value2 )
			return None
		elif int(value2) != int(qty):
			print( 'inconsistant values %s & %s' % (qty, value2) )
			return	None
	return qty

# No command to execute
NOPE = -1

class CmdParse(cmd.Cmd):
	# prompt = "? "
	#def do_listall(self, line):
	#	print(commands)
	def __init__( self, cmd_callback, prompt_prefix='' ):
		cmd.Cmd.__init__( self )
		cmd.Cmd.prompt = '%s> ' %  prompt_prefix
		self.cmd_callback = cmd_callback

	def default(self, line):
		self.cmd_callback( line )

	def do_help( self , line ):
		""" Overwrite help command to redirect it to the PrestaConsole help """
		self.cmd_callback( 'help' )

class BaseApp( object ):
	""" Basic Applicative class """

	def __init__( self, keywords, commands ):
		""" Initialize the application

		:params keywords: keywords and their equivalent
		:params commands: supported commands and parameters count
		"""
		self.config = Config()
		self.cmd_parse = CmdParse( self.cmd_parse_callback, self.config.prompt )
		self.KEYWORDS = keywords
		self.COMMANDS = commands
		self.output = PrestaOut()
		# Initialize Printer Queue Names
		import labelprn as lp
		lp.printer_shortlabel_queue_name = self.config.printer_shortlabel_queue_name
		lp.printer_largelabel_queue_name = self.config.printer_largelabel_queue_name
		lp.printer_ticket_queue_name 	 = self.config.printer_ticket_queue_name
		lp.shop_info_small = self.config.shop_info_small
		lp.shop_info_large = self.config.shop_info_large

		# initialize the logging
		logging.basicConfig( filename=self.config.logfile, level=logging.INFO,
							 format='%(asctime)s - [%(levelname)s] %(message)s',
							 datefmt='%d/%m/%y %H:%M:%S.%f' )
		# Just required to handle batch
		self._batches = None # Access it via the batches property
		if self.config.batch_path:
			self._batches = BatchFactory( storage_path = self.config.batch_path )

		# A CachedPrestaHelper is a PrestaHelper with cache capabilities
		self.cachedphelper = CachedPrestaHelper( self.config.presta_api_url, self.config.presta_api_key, debug = False, progressCallback = progressHandler )
		# Force loading cache
		#   cachedphelper.load_from_webshop()
		# Update Stock quantities
		#   cachedphelper.stock_availables.update_quantities()
		#tester = CachedPrestaHelperTest( cachedphelper )
		#tester.test_cache()

	@property
	def batches( self ):
		""" Retreive a reference to the batch factory """
		if not self._batches:
			raise Exception( "No BatchFactory available! The [APP].batch_path has not been defined in the config.ini")
		return self._batches

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
			return( None, [] ) # Unable to decode

		# Starting with = for evaluate a Python line
		if sCmd.startswith('='):
			self.output.writeln( "%s" % eval(sCmd[1:]) )
			# Now returns Nothing to execute (everything is already done)
			return ( NOPE, [] )

		# Start with ! to execute a basch command
		if sCmd.startswith('!'):
			os.system( sCmd[sCmd.index('!')+1:] )
			# Now returns Nothing to execute (everything is already done)
			return ( NOPE, [] )

		# Handle a PIPED command
		if ( '|' in sCmd ):
			sConsoleCmd = sCmd[:sCmd.index('|')]
			sPipeCmd    = sCmd[sCmd.index('|'):]
			old_stdout_active = self.output.stdout_active

			if not self.cachedphelper.debug :
				self.output.stdout_active = False
			try:
				self.do_file_begin( params=None )
				self.evaluate_line( sConsoleCmd )
				sFilename = self.do_file_end( params=None )
				sPipeCmd = 'cat %s %s' % (sFilename, sPipeCmd)
				# Should display the result directly on terminal whatever is the
				# internal self.output.stdout_active flag state
				os.system( sPipeCmd )
			finally:
				self.output.stdout_active = old_stdout_active

			# Now returns Nothing to execute (everything is already done)
			return ( NOPE, [] )

		# Handle the "Console command"
		keywords = sCmd.split() # fait déjà un strip des paramètres
		_r = []
		for word in keywords:
			_normalized = self._normalize_keyword( word )
			if _normalized: # Some words (to from) are replaced by None
				_r.append( _normalized )
		params = _r # apply the new parameter

		# Treat really special case
		#   Backward compatibility : ID -> label product, .xxx -> Show product, xxx -> list product
		if (len( params ) == 1) and not( params[0] in self.KEYWORDS ) and \
		    not( any([item for item in self.COMMANDS if item[0]==params[0]]) ): # Note: somes command makes only one word (and are not keyword)
			# we are looking for product OR having a product ID
			if params[0].isdigit(): # it is an ID
				params.insert(0, 'label')
				params.insert(1, 'product')
			elif  (params[0].find('.')==0) : # Start with a point  | and ( params[0][1:].isdigit() ): # Start with a point and contains digit... it is a show product <ID>
				params[0] = params[0][1:] # Keep the ID (remove the dot)
				params.insert( 0, 'show' )
				params.insert( 1, 'product' )
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
						raise Exception( 'At least one parameter required for "%s"' % r_cmd )
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
		if cmd == NOPE:
			return
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
				self.output.writeln( '> %s' % value )
				self.evaluate_line( value )
			except Exception as err:
				self.output.writeln( '[ERROR] %s' % err )
				if self.cachedphelper.debug:
					traceback.print_exc()

	def run( self ):
		""" Run the main cmd line requests loop """
		# it is delegated to cmd.Cmd miniframwork
		self.cmd_parse.cmdloop() # cmd.Cmd.cmdloop() --> see default()

	def cmd_parse_callback( self, line ):
		# Default command handler for cmd.Cmd.cmdloop()
		try:
			self.evaluate_line( line )
			self.output.writeln('')
		except Exception as err:
			self.output.writeln( '[ERROR] %s' % err )
			if self.cachedphelper.debug:
				traceback.print_exc()

# ===========================================================================
#
#       APPLICATION
#
# ===========================================================================

KEYWORDS = {
	'list'    : ['ls'],
	'links'    : ['link'],
	'product' : ['prod','arti', 'article'],
	'option'  : ['options'],
	'supplier': ['sup', 'supp', 'four'],
	'ean'     : ['ean'],
	'label'   : ['lb'],
	'reload'  : ['r'], # reload the data
	'update'  : ['u'], # update stock quantities
	'quit'    : ['q', 'exit'],
	'help'    : ['?', 'h'],
	'stock'   : ['s'],
	'1'       : ['true'],
    '0'       : ['false'],
	'batch new': ['nbatch'],
	'batch print' : ['pbatch'],
	'batch transform' : ['tbatch'],
	'batch list' : ['lbatch'],
	'batch view' : ['vbatch'],
	'batch search' : ['sbatch'],
	None       : ['from'] # remove any from and to

}

# Commands + Needed parameters + function to call
#    Needed Parameter '+': 1 or more, '*': 0 or mode, numeric (exactly X values)
COMMANDS = [
	('test'           , '*' ),
	('eand'           , 1   ),
	('ean'            , 1   ),
	('calc ean'       , 1   ),
	('help'           , 0   ),
	('bag clear'      , 0   ),
	('bag export'     , 0   ),
	('bag import'     , 0   ),
	('bag links'      , 0   ),
	('bag quote'      , 0   ),
	('bag rebate'     , 0   ),
	('bag comment del', 0   ),
	('bag comment'    , 0   ),
	('bag ship'       , 0   ),
	('bag'            , 0   ),
	('batch new'      , 1   ),
	('batch print'    , 1   ),
	('batch transform', 1   ),
	('batch list'     , '*' ),
	('batch view'     , 1   ),
	('batch search'   , '+' ),
	('check stock config',0 ),
	('editor begin'   , 0   ),
	('editor end'     , 0   ),
	('editor once'    , 0   ),
	('editor abort'   , 0   ),
	('file begin'     , 0   ),
	('file end'       , 0   ),
	('file abort'     , 0   ),
	('label product'  , 1   ),
	('label small'    , 0   ),
	('label large'    , 0   ),
	('label king'     , 0   ),
	('label war'      , 1   ),
	('label vat'      , 0   ),
	('label conf'     , 0   ),
	('label esd'      , 0   ),
	('label ean'      , 0   ),
	('label order'    , 1   ),
	('links'          , 1   ),
	('list order'     , '*' ),
	('list product'   , '+' ),
	('list supplier'  , '*' ),
	('order'          , '+'  ),
	('print once'     , 0   ),
	('print begin'    , 0   ),
	('print end'      , 0   ),
	('print abort'    , 0   ),
	('quit'           , 0   ),
	('reload stock'   , 0   ),
	('reload only'    , 0   ),
	('reload'         , 0   ),
	('save'           , 0   ),
	('set debug'      , 1   ),
	('set'            , 2   ),
	('show keyword'   , 1   ),
	('show command'   , 0   ),
	('show debug'     , 0   ),
	('show option'    , '*' ),
	('show product'   , 1   ),
	('show stat'      , 0   ),
	('upgrade'        , 0   )
	]

_last_tracability_info = ''

class App( BaseApp ):
	""" Handle the application """

	def __init__( self ):
		super( App, self ).__init__( KEYWORDS, COMMANDS )
		self.bag                = ToteBag()
		self.ID_SUPPLIER_PARAMS = None  # LABEL Size is stored into the article reference of the "PARAMS" supplier.
		self.print_once         = False
		self.editor_once        = False
		 # Maintains the application options
		self.options = { 'show-product-pa'   : '1',
						 'show-product-pv'   : '1',
						 'show-product-label': '0',
						 'show-product-qm'   : '0',
						 'show-product-qo'   : '0',
						 'show-product-ean'  : '0',
						 'inactive-product'  : '0',
						 'include-it'        : '0',
						 'label-separator'   : '0',
						 'print-landscape'   : '1',
						 'print-cpi'         : '12',
						 'print-lpi'         : '7',
						 'print-sides'       : 'one-sided',
						 'editor'			 : 'pluma',
						 'shop_url_product'  : 'https://shop.mchobby.be/product.php?id_product={id}'
					   }

		# Init params from load data
		self.__init_from_loaded_data()

	def __init_from_loaded_data( self ):
		""" Initialize special parameters the loaded webshop data (file of WebShop) """
		self.ID_SUPPLIER_PARAMS = None
		self.ID_SUPPLIER_TARIFF = None

		_item = self.cachedphelper.suppliers.supplier_from_name( "PARAMS" )
		if _item != None:
			self.ID_SUPPLIER_PARAMS = _item.id

		_item = self.cachedphelper.suppliers.supplier_from_name( "TARIFF-CODE" )
		if _item != None:
			self.ID_SUPPLIER_TARIFF = _item.id
		print( 'ID_SUPPLIER_PARAMS : %s' % self.ID_SUPPLIER_PARAMS )
		print( 'ID_SUPPLIER_TARIFF : %s' % self.ID_SUPPLIER_TARIFF )

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
				raise Exception( 'Invalid product PARAMS "%s" in "%s" for id_product %s. it must have 2 parts (colon separated!)' % (vals, reference,id_product) )
			result[vals[0]] = vals[1]

		return result

	def get_product_tariff( self, id_product ):
		""" Locate the Tariff Code for the product stored into the TARIFF supplier reference for that product.
			The PARAMS supplier is encoded as follows: country_ISO,tariff """
		assert type(id_product) is int, "is_product must be interger"
		# If this special TARIFF supplier is not yet identified then
		#   not possible to locate the special product parameter
		#   stored there
		if self.ID_SUPPLIER_TARIFF == None:
			return (None,None)

		tariff = self.cachedphelper.product_suppliers.reference_for( id_product, self.ID_SUPPLIER_TARIFF )
		# print( 'id_product %s -> tariff: %s' % (type(id_product),tariff) )
		if len(tariff)==0:
			return (None,None)

		lst = tariff.split(',')
		if len( lst )!= 2:
			raise Exception( 'Invalid product TARIFF "%s" for id_product %s. it must have 2 parts (country,tariff)' % (tariff, id_product) )

		return (lst[0],lst[1]) # Country ISO Code, tariff_code

	def get_qm_info( self, psr ):
		""" generate the 'Quantity Minimum Warning' message for a given product.

			:param psr: ProductSearchResult item for whom the QM Warning should be computed.
			:return: tuple of ( qm_value, qm_warning_message ) value. Note that qm_warning is empty string when there is no warning.
		"""
		# Attempt to retreive QM
		_params = self.get_product_params( psr.product_data.id )
		# The QM value
		_qm = None
		if 'QM' in _params:
			try:
				_qm = int(_params['QM'])
				value1 = _qm
			except:
				value1 = '???'
		else:
			value1 = '---'
		# The QM warning value
		if psr.qty <= 0:
			value2 = '%s' % psr.qty
		elif _qm and (psr.qty <= _qm):
			value2 = '!!!'
		else:
			value2 = ''

		return (value1, value2) # QM_value, QM_Warning_Message

	def get_qo_info( self, psr, as_int = False ):
		""" grab the 'Quantity Order' information for a given product.

			:param psr: ProductSearchResult item for whom the QM Warning should be computed.
			:return: QO value
		"""
		# Attempt to retreive QO
		_params = self.get_product_params( psr.product_data.id )
		# The QO value
		if 'QO' in _params:
			try:
				_qo = int(_params['QO'])
				value1 = _qo
			except:
				value1 = '???' if not(as_int) else 0
		else:
			value1 = '---' if not(as_int) else 0

		return value1 # QO_value

	def output_product_search_result( self, psr_list ):
		""" output the list of product (ProductSearchResult list). The default destination is the screen (but may vary depending on options)

		:param psr_list: a ProductSearchResult list of a ToteBag (also a list) """
		if len( psr_list )<=0:
			return

		sTitle = ''
		sPrint = ''
		if isinstance( psr_list[0], ToteItem ):
			sTitle += '%7s | ' % 'ordered'
			sPrint += '%7i | '
		sTitle += '%9s | %-30s | %5s' % ('ID', 'Reference', 'stock' )
		sPrint += '%9i | %-30s | %5i'
		if self.options['show-product-qm']=='1':
			sTitle += ' | %5s | %3s' % ('QM', '/!\\' )
			sPrint += ' | %5s | %3s'
		if self.options['show-product-qo']=='1':
			sTitle += ' | %5s' % 'QO'
			sPrint += ' | %5s'
		if self.options['show-product-label'] == '1':
			sTitle += ' | %-50s' % 'Label'
			sPrint += ' | %-50s'
		if self.options['show-product-pa'] == '1':
			sTitle += ' | %6s' % 'P.A.'
			sPrint += ' | %6.2f'
		if self.options['show-product-pv'] == '1':
			sTitle += ' | %15s' % 'P.V. (PV ttc)'
			sPrint += ' | %6.2f (%6.2f)'
		if self.options['show-product-ean'] == '1':
			sTitle += ' | %15s' % 'EAN'
			sPrint += ' | %15s'
		sTitle += ' | %-20s' % 'Supp. Ref.'
		sPrint += ' | %-50s'


		self.output.writeln( sTitle )
		self.output.writeln( '-'*len(sTitle))
		_count = 0
		for psr in  psr_list : # Returns a list of ProductSearchResult
			# If it isn't a ProductSearchResult, we will have to Mimic it!
			if isinstance( psr, ProductSearchResult ):
				pass
			elif isinstance( psr, ToteItem ):
				_item = psr # remind old ToteItem reference
				psr = self.cachedphelper.psr_instance( _item.product )
				psr.ordered_qty = _item.qty # set the ordered qty from ToteBag

			# --- prepare the data ---
			_lst = []
			# Order QTY come from ToteBag
			if psr.ordered_qty:
				_lst.append( psr.ordered_qty )

			# ID, Ref, QTY
			_lst = _lst + [psr.product_data.id, psr.product_data.reference, psr.qty ]

			# Minimal Quantity
			if self.options['show-product-qm']=='1':
				# Get 'Quantity Minimal', 'Quantity Minimal Warning' text
				QM, sQM_Warning = self.get_qm_info( psr )
				_lst.append( QM )
				_lst.append( sQM_Warning )
				# Attempt to retreive QM
				#_params = self.get_product_params( psr.product_data.id )
				#_qm = None
				#if 'QM' in _params:
				#	try:
				#		_qm = int(_params['QM'])
				#		_lst.append( _qm )
				#	except:
				#		_lst.append( '???')
				#else:
				#	_lst.append(  '---' )
				# Display QM warning column
				#if psr.qty <= 0:
				#	_lst.append( '%s' % psr.qty )
				#elif _qm and (psr.qty < _qm):
				#	_lst.append( '!!!' )
				#else:
				#	_lst.append( '' )
			if self.options['show-product-qo']=='1':
				QO = self.get_qo_info( psr )
				_lst.append( QO )

			if self.options['show-product-label'] == '1':
				_lst.append( psr.product_data.name )
			if self.options['show-product-pa'] == '1':
				_lst.append( psr.product_data.wholesale_price )
			if self.options['show-product-pv'] == '1':
				_lst.append( psr.product_data.price )
				_lst.append( psr.product_data.price_ttc )
			if self.options['show-product-ean'] == '1':
				_lst.append( psr.product_data.ean13 )
			_lst.append( psr.supplier_refs )

			# Go for display
			self.output.writeln( sPrint % tuple( _lst ) )
			_count += 1

		self.output.writeln( '%s rows in result' % _count )

			#print( '%7i : %s : %5i : %s - %s' % ( \
			#	psr.product_data.id, \
			#	psr.product_data.reference.ljust(30), \
			#	psr.qty, \
			#	psr.product_data.name.ljust(50), \
			#	psr.supplier_refs ) )

	def evaluate_line( self, value ):
		_print_once = self.print_once # was it activated before the command execution
		_editor_once = self.editor_once

		# Bag manipulation command ?
		if self.bag.is_bag_command( value ):
			# returns text line to displays
			lines = self.bag.manipulate( self.cachedphelper, value )
			self.output.write_lines( lines )
		else:
			# Standard command execution
			super( App, self ).evaluate_line( value )
		if _print_once:
			self.do_print_end( params = {} )
		if _editor_once:
			self.do_editor_end( params = {} )

	# ---------------------------------------------------------------------------
	#
	#   COMMANDs execution
	#
	# ---------------------------------------------------------------------------
	def do_test( self, params ):
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID cmd'
		_id = int( params[0] )

		# test_order_history( _id )
		# self.test_save_order( 14286 ) # An order from Dominique
		#self.cachedphelper.get_products( )
		batch = self.batches.new_batch()
		batch.data.product_id = 400
		batch.data.product_reference = 'SUCET-BOUCHE-B-POP'
		batch.data.product_name      = 'Sucette en forme de bouche - B-pop Mix'
		batch.data.product_ean       = '3232100004009'
		batch.data.creation_date     = datetime.datetime.now()
		batch.data.expiration        = '05/2021' # 'mm/yyyy'
		batch.data.label_count       = 2 # Number of printeed label
		batch.data.info = 'Blablabla'
		self.batches.save_batch( batch )

		print_ticket_batch( batch, batch.data.label_count )
		print( "Printed" )


	def save_shipping_nr( self, order_ids, shipping_nr ):
		""" TEST: read, set status=Shipping, set Shipping_nr THEN save the order.
			If configured proprely, this will also send the shipping mail.

			:param ids: list of order id (EG. [14286])
			:param shipping_nr: bacode with the shipping number """

		for _id in order_ids:
			# Load an order
			_data = self.cachedphelper.get_order_data( _id )
			from xml.etree import ElementTree
			# Change the Order Status
			order = list( _data )[0]
			order_properties = list( order )
			order_current_state = [ order_property for order_property in order_properties if order_property.tag == 'current_state' ]
			if order_current_state[0].text == str( OrderStateList.ORDER_STATE_SHIPPING ):
				raise Exception( 'Order %s already in SHIPPING status' % _id )
			# Update the status in XML Document
			# <current_state xmlns:ns0="http://www.w3.org/1999/xlink" ns0:href="https://dev.mchobby.be/api/order_states/3">4</current_state>
			order_current_state[0].text = str( OrderStateList.ORDER_STATE_SHIPPING )
			order_current_state[0].set( '{http://www.w3.org/1999/xlink}href', '%s/order_states/%s' % (self.config.presta_api_url,OrderStateList.ORDER_STATE_SHIPPING) )
			# Update Shipping Number --> Simplier way
			_el = _data.find('order').find('shipping_number')
			_el.text = "%s" % shipping_nr # Ensure it is a string.

			# Debugging
			# print( ElementTree.tostring(_data) )
			# import pdb; pdb.set_trace()

			# Send the Data to PrestaShop. It will reread the data and return it
			# (so the order) as an ElementTree
			result = self.cachedphelper.post_order_data( _data )
			self.output.writeln( 'Order %s updated to SHIPPING status' % _id )
			# print( ElementTree.tostring(result) )

	def test_order_history( self, _id ):
		""" TEST: order history inspection """
		# --- Historique de commande (changement de status) --------------------
		print( "ID : %s" % _id )
		_data = self.cachedphelper.get_order_data( _id )
		from xml.etree import ElementTree
		print( ElementTree.tostring(_data) )
		print( "-"*80 )

		#_data = self.cachedphelper.webservice.get( 'order_histories', 22887 )
		_data = self.cachedphelper.search( 'order_histories', options={'filter[id_order]': _id} )
		print( ElementTree.tostring(_data) )

		_data = self.cachedphelper.webservice.get( 'order_histories', 91240 )
		print( ElementTree.tostring(_data) )
		_data = self.cachedphelper.webservice.get( 'order_histories', 91241 )
		print( ElementTree.tostring(_data) )

	def do_bag( self, params ):
		""" View the content of the bag (shopping basket """
		#def view_bag( cachedphelper, bag, max_row=None, desc=False ):

		#_desc = False # Display in descending order

		if len( self.bag )==0:
			self.output.writeln( '' )
			self.output.writeln(  '(empty bag)' )
		else:
			self.output_product_search_result( psr_list = self.bag )
			# show the comments
			for comment in self.bag.comments:
				_qty = ('%7i'%comment.qty) if comment.qty!=None else ''
				_text = comment.text
				_price = ('%6.2f' % comment.price) if comment.price!=None else ''
				_price_ttc = ('%6.2f' % (comment.price*1.21)) if comment.price!=None else ''
				self.output.writeln( '%7s |           | %-61s | %6s (%6s ) | ' % (_qty,_text,_price,_price_ttc))
			# Prices
			totals = self.bag.total_price_ordered() # sum, sum_ttc, sum_wholesale_price, rebate_htva
			# Displays the comments
			self.output.writeln( 'Total (TTC) : %6.2f Eur (%6.2f TTC)' % (totals[0], totals[1]) )
			if totals[2]>0:
				self.output.writeln( 'Marge       : %6.2f Eur (%4.2f %%)' % (totals[0]-totals[2], ((totals[0]-totals[2])/totals[2])*100) )
			if self.bag.rebate > 0:
				# totals[3] = rebate_htva
				self.output.writeln( '+%s' % ('-'*40) )
				self.output.writeln( '| Rebate      : %5.2f %%  (%6.2f EUR HTVA)' % (self.bag.rebate, totals[3]) )
				self.output.writeln( '| Total (TTC) : %6.2f Eur (%6.2f TTC)' % (totals[0]-totals[3], (totals[0]-totals[3])*1.21) )
				if totals[2]>0: # If wholesale price available
					self.output.writeln( '| Marge revue : %6.2f Eur (%4.2f %%)' % (totals[0]-totals[2]-totals[3], ((totals[0]-totals[2]-totals[3])/totals[2])*100) )
				self.output.writeln( '+%s' % ('-'*40) )
			else:
				self.output.writeln( 'Rebate      : NO')
		#for idx, item in enumerate( reversed(self.bag) if _desc else self.bag ):
		#	#if max_row and (idx>=max_row):
		#	#	print( '> ...' ) # indicates the presence of more items in the bag
		#	#	break;
		#
		#	print( '%3i x %7i : %s - %s' % (item.qty, item.product.id,item.product.reference.ljust(30),item.product.name) )

	def do_bag_rebate( self, params ):
		""" Set the rebate value """
		value = ''
		while True:
			if value != None:
				self.do_bag( params )

			value = raw_input( "Rebate percent or +q: " )
			if value == '+q':
				break

			try:
				self.bag.rebate = float(value)
			except:
				print('Incorrect value!')
				value = None # Do not redisplay bag at next round

		return None

	def do_bag_comment( self, params ):
		""" Add a comment to the bag """
		label = raw_input( "Label or +q: " )
		if ( label == '+q' ) or ( len(label)==0 ):
			return None
		price = raw_input( "price or empty or +q: " )
		if len(price)==0:
			_price = None
		elif price=='+q':
			return None
		else:
			_price = float( price )

		qty = raw_input( "qty or empty or +q: " )
		if len(qty)==0:
			_qty = 1
		elif qty=='+q':
			return None
		else:
			_qty = int( qty )

		self.bag.add_comment( _qty, label, _price )
		# Show the bag
		self.do_bag( params )

	def do_bag_comment_del( self, params ):
		""" Remove a comment from bag """
		if len( self.bag.comments )==0:
			return None
		for idx in range( len(self.bag.comments) ):
			self.output.writeln( '%2i : %s' % (idx, self.bag.comments[idx].text ) )
		value = raw_input( "Which to delete or +q: " )
		if len(value)==0:
			return None
		elif value=='+q':
			return None
		else:
			_idx = int( value )
			del(self.bag.comments[_idx])

	def do_bag_ship( self, params ):
		""" Add a shipping cost to the bag (under the form of a comment)"""
		_pricing = [ ('Poste BE (home)', 6.53), ('Colissimo FR (home)', 10.00),
		             ('Relais BE', 4.00), ('Relais BE', 2.50),
					 ('Relais FR', 6.00), ('Relais FR', 3.50),
					 ('DHL BE', 16.00), ('DHL FR', 16.50) ]
		for i in range( len(_pricing) ):
			print( '%2i : %-20s ( %6.2f EUR)' % (i, _pricing[i][0], _pricing[i][1]) )

		pricing  = 0.0
		qty      = 1
		shipping = raw_input( "Label or +q: " )
		if ( shipping == '+q' ) or ( len(shipping)==0 ):
			return None
		elif shipping.isdigit():
			pricing  = _pricing[int(shipping)][1]
			shipping = _pricing[int(shipping)][0]

		price = raw_input( "price (%6.2f) or +q: " % pricing )
		if len(price)==0:
			pass # Keep pricing
		elif price=='+q':
			return None # exits
		else:
			pricing = float( price )

		value = raw_input( "qty (%i) or +q: " % qty )
		if len(value)==0:
			pass
		elif value=='+q':
			return None
		else:
			qty = int( value )

		self.bag.add_comment( qty, shipping, pricing )
		# Show the bag
		self.do_bag( params )


	def do_bag_clear( self, params ):
		self.bag.clear()

	def do_bag_export( self, params ):
		""" Export the bag to an XML file (to be imported into LibreOffice) """
		# export the bag
		root = self.bag.export_to_xmltree()
		tree = etree.ElementTree( root )

		root = Tk()
		root.filename = tkFileDialog.asksaveasfilename(initialdir = self.config.tote_bag_export_path,title = "Exporter vers fichier XML",filetypes = (("xml","*.xml"),("all files","*.*")))
		if (root.filename == u'') or (root.filename == self.config.tote_bag_export_path):
			self.output.writeln( 'User abort!')
			root.destroy()
			return
		tree.write( root.filename )
		root.destroy()
		self.output.writeln( 'exported to %s' % root.filename )

	def do_bag_import( self, params ):
		""" Import an XML file into the nag """
		root = Tk()
		root.filename = tkFileDialog.askopenfilename(initialdir = self.config.tote_bag_export_path,title = "Recharger un fichier XML",filetypes = (("xml","*.xml"),("all files","*.*")))
		if (root.filename == u'') or (root.filename == self.config.tote_bag_export_path):
			self.output.writeln( 'User abort!')
			root.destroy()
			return

		tree = etree.parse( root.filename )
		xml_root = tree.getroot()
		# Clear the bag
		self.bag.clear()
		# reload content from xml into the tote-bag
		self.bag.import_from_xmltree(self.cachedphelper, xml_root )
		root.destroy()
		# display information to user
		self.output.writeln( 'reloaded from %s' % root.filename )

	def do_bag_links( self, params ):
		""" Export BAG as text list + Link to the webshop """
		for item in self.bag:
			self.output.writeln( '%s x %s' % (item.qty, item.product.reference ) )
			self.output.writeln( '   %s' % item.product.name )
			self.output.writeln( '   %8.2f Eur TTC/p (indicatif)' % (item.product.price*1.21) )
			self.output.writeln( '   '+self.options['shop_url_product'].format( id=item.product.id )  )
			self.output.writeln( ' ' )

	def do_bag_quote( self, params ):
		""" Export BAG as QUOTE text list + Link to the webshop """
		dt = datetime.datetime.today()
		self.output.writeln( '---------------------------------' )
		self.output.writeln( '   DDD   EEEE  V   V  I   SSSS' )
		self.output.writeln( '   D  D  E     V   V  I  S    ' )
		self.output.writeln( '   D  D  EEE   V   V  I   SSS ' )
		self.output.writeln( '   D  D  E      V V   I      S' )
		self.output.writeln( '   DDD   EEEE    V    I  SSSS ' )
		self.output.writeln( '---------------------------------' )
		self.output.writeln( ' ' )
		self.output.writeln( '                       Devis n°   : '  )
		self.output.writeln( '                       Date       : %s' % dt.strftime("%d/%m/%Y") )
		self.output.writeln( '                       Expiration : %s' % (dt+datetime.timedelta(days=30)).strftime("%d/%m/%Y") )
		self.output.writeln( 'SHIPPING ADDRESS:' )
		self.output.writeln( '   Company  : ' )
		self.output.writeln( '   Recipient: ' )
		self.output.writeln( '   Address  : ' )
		self.output.writeln( '   CP/Town  : ' )
		self.output.writeln( ' ' )
		self.output.writeln( 'INVOICE ADDRESS:' )
		self.output.writeln( '   Company  : ' )
		self.output.writeln( '   Recipient: ' )
		self.output.writeln( '   Address  : ' )
		self.output.writeln( '   CP/Town  : ' )
		self.output.writeln( '   VAT      : ' )
		self.output.writeln( ' ' )
		self.output.writeln( '-'*70 )
		self.output.writeln( '%3s | %-30s | %8s |  %8s ' % ("Qty", "Description", "P.U.", "Total EUR (HTVA)" ) )
		self.output.writeln( '-'*70 )
		for item in self.bag:
			self.output.writeln( '%3i | %-30s | %8.2f |  %8.2f ' % (item.qty, item.product.reference, item.product.price, item.qty * item.product.price ) )
			self.output.writeln( '    | %s' % item.product.name )
			self.output.writeln( '    | '+self.options['shop_url_product'].format( id=item.product.id )  )
			self.output.writeln( '%3s | %30s | %8s |  %8s ' % ("", "", "", "" ) )
			# self.output.writeln( ' ' )
			# self.output.writeln( '   %8.2f Eur TTC/p (indicatif)' % (item.product.price*1.21) )
		for comment in self.bag.comments:
			_qty = ('%3i'%comment.qty) if comment.price!=None else ''
			_text = comment.text
			_price = ('%6.2f' % comment.price) if comment.price!=None else ''
			_total = ('%6.2f' % (comment.price*comment.qty)) if comment.price!=None else ''
			self.output.writeln( '%3s | %-30s | %8s |  %8s ' % (_qty,_text,_price,_total))

		totals = self.bag.total_price_ordered() # sum, sum_ttc, sum_wholesale_price, rebate_htva
		if self.bag.rebate > 0:
			self.output.writeln( '%3i | %-30s | %8.2f |  %8.2f ' % (1, 'Rebate %5.2f EUR'%totals[3],-1*totals[3],-1*totals[3] ) )
		self.output.writeln( '-'*70 )
		self.output.writeln( 'Total HTVA: %8.2f EUR' % (totals[0]-totals[3]) ) # sum_htva - rebate_htva
		_tva = (totals[0]-totals[3])*0.21
		self.output.writeln( 'TVA       : %8.2f EUR' % _tva ) # amount of TVA
		self.output.writeln( 'Total TTC : %8.2f EUR' % (totals[0]-totals[3]+_tva) )

		self.output.writeln( ' ' )

		self.output.writeln( 'Delivery delay   : [ On order confirmation depending on supplier stock ]' )
		self.output.writeln( 'Payment          : [ 7 to 10 days max after delivery ] [ Payment at order ]' )
		self.output.writeln( '                    BELGIUM' )
		self.output.writeln( '                    BNP : Iban : BE 41 0017 0629 8910' )
		self.output.writeln( '                          Swift: GEBABEBB' )
		self.output.writeln( ' ' )
		self.output.writeln( '-'*70 )
		self.output.writeln( ' MC Hobby SPRL - Clos de la Giberne, 3 - 1410 WATERLOO - BELGIQUE' )
		self.output.writeln( ' Email: frc@mchobby.be - www.MCHobby.be - tel: +32 (0) 496 92 83 20' )
		self.output.writeln( ' BNP Parisbas : IBAN : BE41 0017 0629 8910 - BIC/SWIFT : GEBABEBB' )
		self.output.writeln( ' TVA : BE 0538.615.264 RPM Nivelles' )




	def do_batch_new( self, params ):
		""" Create a new batch with expiration information """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID Product'
		global _last_tracability_info
		_id = int( params[0] )
		_p  = self.cachedphelper.products.product_from_id( _id )
		if not(_p):
			self.output.writeln( 'Invalid id product.' )
			return
		self.output.writeln( "--- PREPARING NEW BATCH for ID %s ---" % _id )
		self.output.writeln( "  ref   : %s" % _p.reference )
		self.output.writeln( "  label : %s" % _p.name )
		_exp = request_expiration( 'Expiration MM/YYYY ? ')
		if not _exp:
			print( "User abord!" )
			return
		print( 'Tracability info   : %s' % _last_tracability_info )
		_info = request_text( 'Tracability   (+q) ? ', default = _last_tracability_info)
		if not(_info):
			print( "User abord!" )
			return
		_last_tracability_info = _info # Remember for next time

		_label_qty = request_int ( '# Label            ? ')
		if not(_label_qty) or (_label_qty==0):
			print( "User abord!" )
			return

		_confirm = request_text( 'CREATE NEW BATCH (y=1/.)? ', default = '0' )
		if _confirm.upper() != '1':
			print( "User abord!" )
			return

		# Save the batch
		batch = self.batches.new_batch()
		batch.data.product_id = _id
		batch.data.product_reference = _p.reference
		batch.data.product_name      = _p.name
		batch.data.product_ean       = _p.ean13
		batch.data.creation_date     = datetime.datetime.now()
		batch.data.expiration        = _exp
		batch.data.label_count       = _label_qty # Number of printeed label
		batch.data.info 			 = _info
		self.batches.save_batch( batch )

		self.output.writeln( "Batch %i created!" % batch.data.batch_id )

		while True:
			_confirm = request_text( 'CREATE TRANSFORMATION (y=1/.)? ', default = '0' )
			if not( _confirm.upper() in ('1','Y') ):
				break
			self.encode_batch_transformation( batch )

		# Save tranformations if any
		if len(batch.transformations)>0:
			self.batches.save_batch( batch )
			self.output.writeln( "Batch %i updated!" % batch.data.batch_id )

		print_ticket_batch( batch, _label_qty )
		self.output.writeln( "" )

	def encode_batch_transformation( self, batch ):
		""" Key-in a transformation for an existing batch """
		# search for target_product_id
		_id_target = None
		while True:
			sTarget = request_text( 'Target product (+q) : ', default = '' )
			if not(sTarget) or (sTarget.strip().upper()=='+Q') :
				return None
			if sTarget.isdigit():
				_p  = self.cachedphelper.products.product_from_id( int(sTarget) )
				if _p:
					_id_target = int( sTarget )
					break
			else:
				self.do_list_product( [sTarget] )

		_p  = self.cachedphelper.products.product_from_id( _id_target )
		# Go printing!
		self.output.writeln( "Target product   : %s (%s)" % (_p.reference, _p.id) )
		_label_qty = request_int ( "# Label          ? " )
		if not(_label_qty) or (_label_qty==0):
			print( "User abord this transformation!" )
			return
		_trf = batch.add_transformation()
		_trf.target_product_id   = _p.id
		_trf.target_product_reference = _p.reference
		_trf.target_product_name = _p.name
		_trf.target_product_ean  = _p.ean13
		_trf.creation_date       = datetime.datetime.now()
		_trf.expiration          = batch.data.expiration
		_trf.label_count         = _label_qty
		return _trf

	def do_batch_transform( self, params ):
		""" Reload an existing batch and start a transformation """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an batch ID'
		_id = int( params[0] )
		_batch = self.batches.load_batch( _id )

		self.output.writeln( "-"*40 )
		self.output.writeln( "PREPARE TRANSFORMATION for %s (%s) " % (_batch.data.product_reference, _batch.data.product_id) )
		self.output.writeln( "-"*40 )
		# List the related product
		self.show_combinations( int(_batch.data.product_id) )
		# Encode a transformation
		_trf = self.encode_batch_transformation( _batch )
		if not( _trf ):
			self.output.writeln( "User abord" )

		self.batches.save_batch( _batch )
		self.output.writeln( "Batch %i updated!" % _batch.data.batch_id )

		print_ticket_transformation( _batch.data.batch_id , _trf, qty=_trf.label_count )
		self.output.writeln( "" )

	def do_batch_print( self, params ):
		""" reload an existing batch and print it. """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an batch ID'
		_id = int( params[0] )
		_batch = self.batches.load_batch( _id )
		print_ticket_batch( _batch, _batch.data.label_count )

	def do_batch_list( self, params ):
		""" List the last 25 batches (or params'Nth batches) from the disk """
		if len( params )>0:
			assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an integer'
			count = int(params[0])
		else:
			count = 25

		batch_id = self.batches.last_batch_id()
		self.output.writeln( "List %s batches from #batch %s" % (count, batch_id) )
		self.output.writeln( "%-10s : %-4s: %-36s : %-10s : %s" % ('Date', 'Batch', 'Product', 'Prod.ID', "Expire") )
		self.output.writeln( "-"*70 )
		while (count > 0) and (batch_id >= 0) :
			try:
				_batch = self.batches.load_batch( batch_id )
			except EBatch as err:
				# Loading error are just reported to the output
				self.output.writeln( u"%s" % err ) # must be unicode
				continue
			finally:
				count -= 1
				batch_id -= 1
			# Print batch information (date, batch, Product, Prod.ID, Expire )
			self.output.writeln( "%10s : %4s : %3s x %-30s : %10s : %s" % (_batch.data.creation_date.strftime("%d/%m/%Y"), _batch.data.batch_id, _batch.data.label_count ,_batch.data.product_reference, _batch.data.product_id, _batch.data.expiration  ) )
		self.output.writeln( "" )

	def do_batch_view( self, params ):
		""" View the content of the given batch """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the batch_id must be an integer'
		batch_id = int(params[0])
		self.output.writeln( 'stored @ %s' % self.batches.batch_filename(batch_id) )
		for line in self.batches.as_text( batch_id ):
			self.output.writeln( line )

	def do_batch_search( self, params ):
		""" Search in the batch for a string (given in parameter). The second parameter is the the search length"""
		assert len(params)>0 and isinstance( params[0], str )
		if len(params)>1:
			assert isinstance( params[1], str ) and params[1].isdigit(), 'the second parameter must be an integer'
			_count = int( params[1] )
		else:
			_count = 100

		_last_id = self.batches.last_batch_id()
		_text = params[0] # The search string

		self.output.writeln( 'Search for "%s" from batch %i' % (_text,_last_id) )
		_ids = self.batches.has_text( _last_id, _count, _text )

		# Display the result list
		self.output.writeln( "%-10s : %-4s: %-36s : %-10s : %s" % ('Date', 'Batch', 'Product', 'Prod.ID', "Expire") )
		self.output.writeln( "-"*70 )
		for _id in _ids :
			try:
				_batch = self.batches.load_batch( _id )
			except EBatch as err:
				# Loading error are just reported to the output
				self.output.writeln( u"%s" % err ) # must be unicode
				continue
			# Print batch information (date, batch, Product, Prod.ID, Expire )
			self.output.writeln( "%10s : %4s : %3s x %-30s : %10s : %s" % (_batch.data.creation_date.strftime("%d/%m/%Y"), _batch.data.batch_id, _batch.data.label_count ,_batch.data.product_reference, _batch.data.product_id, _batch.data.expiration  ) )
		self.output.writeln( "" )

	def do_check_stock_config( self, params ):
		""" Check all the product with improper stock configuration. """
		psr_lst = ProductSearchResultList()
		for item in self.cachedphelper.stock_availables:
			# Not synched  -OR-  accept order while out of stock
			if (item.depends_on_stock != 1) or (item.out_of_stock == 1) :
				_p = self.cachedphelper.products.product_from_id( item.id_product )
				if _p.active == 0:
					continue
				_psr = ProductSearchResult( _p )
				_psr.add_product_suppliers( self.cachedphelper.product_suppliers.suppliers_for_id_product( item.id_product ) )
				_psr.qty = item.quantity
				psr_lst.append( _psr )
		sorted_lst = sorted( psr_lst, key=lambda item:item.product_data.reference.upper() )
		self.output.writeln( 'Products with improper stock configuration' )
		self.output_product_search_result( psr_list = sorted_lst )

	def do_order( self, params ):
		""" Load and Show the detail of a given order """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID cmd'
		_id = int( params[0] )
		_option = "" # Additional keywork as TARIFF
		if len(params)>1:
			_option = params[1].upper().strip()

		orders = self.cachedphelper.get_last_orders( _id, 1 )
		if len( orders ) <= 0:
			raise ValueError( 'order %s not found' % _id )

		order = orders[0]
		customer = self.cachedphelper.get_customer( order.id_customer )

		def display_order():
			self.output.writeln( '--- Order ID : %i ---' % order.id )
			self.output.writeln( 'Shop ID      : %s' % order.id_shop )
			# print( 'Carrier   ID : %i' % order.id_carrier )
			# print( 'current state: %i' % order.current_state )
			# print( 'Customer  ID : %i' % order.id_customer )
			self.output.writeln( 'Customer     : %s' % customer.customer_name )
			self.output.writeln( 'Cust.EMail   : %s' % customer.email )
			self.output.writeln( 'Carrier      : %s' % self.cachedphelper.carriers.carrier_from_id( order.id_carrier ).name )
			self.output.writeln( 'Order Date   : %s' % order.date_add )
			self.output.writeln( 'Current State: %s @ %s' % ( self.cachedphelper.order_states.order_state_from_id( order.current_state ).name, order.date_upd) )
			self.output.writeln( 'valid        : %i' % order.valid )
			self.output.writeln( 'payment      : %s' % order.payment )
			self.output.writeln( 'total HTVA   : %.2f' % order.total_paid_tax_excl )
			self.output.writeln( 'total Paid   : %.2f' % order.total_paid )
			self.output.writeln( 'Shipping Nr  : %s'   % order.shipping_number )
			self.output.writeln( '' )
			# Content the order
			for row in order.rows:
				self.output.writeln( row )

		def display_tariff():
			# qty, ref, country, tariff, total weight,  Unit_price Ex.VAT, total_price Ex.VAT
			sTitle  = "%3s | %-30s | %5s | %20s | %s | %10s | %10s"
			sFormat = "%3i | %-30s | %5s | %20s | %6.3f | %10.2f | %10.2f"

			self.output.writeln( '              Tariff Declaration' )
			self.output.writeln( '              ==================' )
			self.output.writeln( '' )
			self.output.writeln( 'Date         : %-20s  | Order #: %s' % (order.date_add,order.id) )
			self.output.writeln( 'Shipper Name : MCHobby SRPL          |  Consignee : %s' % (customer.customer_name) )
			self.output.writeln( 'Address      :                       |  Address   :' )
			self.output.writeln( '  Clos de la Giberne, 3              |' )
			self.output.writeln( '  1410 Waterloo                      |' )
			self.output.writeln( '  Belgium                            |' )
			self.output.writeln( '  TAX ID: BE0538.615.264             |' )
			self.output.writeln( 'Contact : +32.496.92.83.20           | Contact : %s ' % (customer.email ) )
			self.output.writeln( '' )
			self.output.writeln( 'Exporting Carrier: %s' % self.cachedphelper.carriers.carrier_from_id( order.id_carrier ).name )
			self.output.writeln( 'Total Ex.VAT     : %.2f EUR' % order.total_paid_tax_excl )
			self.output.writeln( '' )
			self.output.writeln( '   *** all prices are EUR Ex.VAT ***' )
			self.output.writeln( '' )
			self.output.writeln( sTitle  % ('Qty', 'Reference / label', 'Orig.', 'Tariff Code', 'Weight', 'U.Price', 'Total Price'))
			self.output.writeln( '-'*100)

			for row in order.rows:
				# import pdb; pdb.set_trace()
				# qty, ref, country, tariff, total weight,  Unit_price Ex.VAT, total_price Ex.VAT
				id_product = int(row.id_product)
				t = self.get_product_tariff( id_product ) # ( Country_iso, Tariff )
				p = self.cachedphelper.products.product_from_id( id_product, include_inactives=True )
				self.output.writeln( sFormat % (row.ordered_qty, row.reference, t[0], t[1], 0, row.unit_price, row.ordered_qty * row.unit_price) )

		def update_order_send():
			self.output.writeln( '--- Order ID : %i ---' % order.id )
			self.output.writeln( 'Updating shipping info...' )
			_data = "" # Additional data is shipping Nr
			if len(params)>2:
				_data = params[2].upper().strip()
			if _data == "":
				raise Exception.create("Shipping number is missing!")
			# This command receive an unique order_id as int, _data=shiping_nr
			self.save_shipping_nr( [_id], _data )

		if _option == "":
			display_order()
		elif _option == "TARIFF":
			display_tariff()
		elif _option == "SEND":
			update_order_send()
		else:
			raise Exception("Invalid option %s for order command" % _option )

	def do_ean( self, params ):
		""" Generates the EAN13 for the ID_Product """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID product'

		_id = int( params[0] )
		product_ean = '32321%07i' % _id  # prefix 3232 + product 1 + id_product
		product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
		self.output.writeln( '%s' % product_ean )

	def do_eand( self, params ):
		""" Generates the EAN13 for the Declination ID_Product (ID+<00>+ID_Product)"""
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID product'
		_id = int( params[0] )
		declination_product_ean = '33%010i' % _id  # prefix 3232 + product 1 + id_product
		declination_product_ean = calculate_ean13( declination_product_ean ) # Add the checksum to 12 positions
		self.output.writeln( '%s' % declination_product_ean )

	def do_calc_ean( self, params ):
		""" Caclulate the check digit of EAN (on 12 positions) """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit() and len(params[0])==12, 'the parameter must be the first 12 ean digits'

		_ean = calculate_ean13( params[0] ) # Add the checksum to 12 positions
		self.output.writeln( '%s' % _ean )

	def do_editor_begin( self, params ):
		self.output.writeln( 'editor file %s created' % self.output.open_temp_file() )

	def do_editor_end( self, params ):
		filename = self.output.close_temp_file()
		self.output.writeln( 'Editing %s ...' % filename )
		cmd = '%s %s &' % (self.options['editor'], filename)
		self.editor_once = False;

		os.system( cmd )
		# raise Exception('failed to execute %s')

	def do_editor_once( self, params ):
		self.editor_once = True
		self.do_editor_begin( params )

	def do_editor_abort( self, params ):
		self.editor_once  = False
		self.output.close_temp_file()
		raise Exception( 'Editor file aborted!' )

	def do_file_begin( self, params ):
		self.output.writeln( 'file %s created' % self.output.open_temp_file() )

	def do_file_end( self, params ):
		filename = self.output.close_temp_file()
		self.output.writeln( 'Closing %s ...' % filename )
		return filename

	def do_file_abort( self, params ):
		self.output.close_temp_file()
		raise Exception( 'File aborted!' )

	def do_help( self, params ):
		""" Display Help """
		os.system( 'less console.help' )

	def do_label_small( self, params ):
		handle_print_custom_label_small()

	def do_label_king( self, params ):
		handle_print_custom_label_king()

	def do_label_large( self, params ):
		handle_print_custom_label_large()

	def do_label_product( self, params ):
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID product'

		_id = int( params[0] )
		_product = self.cachedphelper.products.product_from_id( _id )
		handle_print_for_product( _product, self.get_product_params( _id ), separator=self.options['label-separator']=='1' )

	def do_label_order( self, params ):
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID order'

		_id = int( params[0] )
		# Ean12 will be automagically transformed to ean13
		print_custom_label_small( label_title="ORDER %s" % _id, label_lines=[], qty=1, ean=("324%09d" % (_id,)) )

	def do_label_war( self, params ):
		_id = int( params[0] ) # use the id provided on the command line

		p = self.cachedphelper.products.product_from_id( _id )
		if not( p ):
			self.output.writeln( 'No product ID %s' % _id )
			return
		handle_print_warranty_label_large( p )

	def do_label_vat( self, params ):
		handle_print_vat_label_large()

	def do_label_conf( self, params ):
		handle_print_conformity_label_small()

	def do_label_esd( self, params ):
		handle_print_esd_label_large()

	def do_label_ean( self, params ):
		handle_print_ean_label_large()

	def do_links( self, params ):
		""" Export PRODUCT as text list + Link to the webshop """
		_id = int( params[0] ) # use the id provided on the command line

		p = self.cachedphelper.products.product_from_id( _id )
		if not( p ):
			self.output.writeln( 'No product ID %s' % _id )
			return

		self.output.writeln( '%s x %s' % (1, p.reference ) )
		self.output.writeln( '   %s' % p.name )
		self.output.writeln( '   %8.2f Eur TTC/p (indicatif)' % (p.price*1.21) )
		self.output.writeln( '   '+self.options['shop_url_product'].format( id=p.id )  )
		self.output.writeln( ' ' )

	def do_list_order( self, params ):
		""" Search for the last order on the shop """
		if len(params)>0:
			_count = int( params[0] ) # use the id provided on the command line
			if _count > 100:
				raise ValueError( 'Count %i is too high! (50 max)' % _count )
		else:
			_count = 10

		last_id = self.cachedphelper.get_lastorder_id()
		orders = self.cachedphelper.get_last_orders( last_id, _count )
		self.output.writeln( "%7s | %-5s | %-19s | %10s | %-20s | %-30s | %-20s " % ('id','valid','date','Tot.htva','Customer', 'Carrier', 'Statut') )
		self.output.writeln( "-"*129 )
		for order in orders:
			customer = self.cachedphelper.get_customer( order.id_customer )
			carrier_name = self.cachedphelper.carriers.carrier_from_id( order.id_carrier ).name
			status_name  = self.cachedphelper.order_states.order_state_from_id( order.current_state ).name
			self.output.writeln( '%7i | %-5s | %19s | %10.2f | %-20s | %-30s | %-20s ' % \
				( order.id, order.valid, order.date_add, order.total_paid_tax_excl, \
				  customer.customer_name[:20], carrier_name[:30], status_name[:20] ) \
				)

	def do_list_product( self, params ):
		""" Search for a product base on its partial reference code + list themself.

		:return: ProductSearchResultList computed and displayed by the function. """
		assert len(params)>0 and isinstance( params[0], str ), 'the parameter must be a string'
		key = params[0]
		if key=='*': # List all products
			key = ''
		elif len( key ) < 3:
			raise ValueError( 'searching product requires at least 3 characters' )

		if (len(key)>0) and (key[0] == '/'):  # search on Supplier Ref
			result = self.cachedphelper.search_products_from_supplier_ref( key[1:], include_inactives = True ) # Skip the /
		elif (len(key)>0) and (key[0] == '*'): # search on label
			result = self.cachedphelper.search_products_from_label( key[1:], include_inactives = True ) # Skip the *
		else:
			result = self.cachedphelper.search_products_from_partialref( key, include_inactives = True )

		show_IT_product = self.options['include-it'] == '1'
		show_inactive   = self.options['inactive-product'] == '1'
		# Remove item that are ITs
		if not( show_IT_product ):
			result.filter_out( lambda psr: psr.product_data.is_IT )
		# Remove item that are inactive (but preserve ITs which are always inactives)
		if not( show_inactive ):
			result.filter_out( lambda psr: psr.product_data.active==0  and not(psr.product_data.is_IT) )
		self.output_product_search_result( psr_list = result )

		return result


	def do_list_supplier( self, params ):
		""" Show the list of suppliers (or product inside the supplier if only one produc) """
		def show_product_list( id_supplier, extra_params ):
			""" Display the list of supplier products

			:param id_supplier: identifier of the supplier to list out.
			:param extra_params: le parameters behind "list product <PARAMS>". order will reduce the list 'QM Warning' products
			"""
			# build the product list
			self.output.writeln( '='*40 )
			self.output.writeln( '    %s supplier list (%i)' % (self.cachedphelper.suppliers.supplier_from_id(id_supplier).name, id_supplier)  )
			self.output.writeln( '='*40 )
			psr_lst = self.cachedphelper.search_products_from_supplier( id_supplier, include_inactives=(self.options['inactive-product']=='1') )
			# also include ITs product
			psr_lst2 = self.cachedphelper.search_products_from_supplier( id_supplier, include_inactives=True, filter = lambda product : product.is_IT )
			psr_lst.merge( psr_lst2 )
			if 'order' in extra_params:
				# Remove all items that are not initiating QM Warning
				psr_lst.filter_out( lambda psr : self.get_qm_info(psr)[1] == '' )

			sorted_lst = sorted( psr_lst, key=lambda item:item.product_data.reference.upper() )
			self.output_product_search_result( psr_list = sorted_lst )
			if 'order' in extra_params:
				# Calculate buy estimation (based on QM)
				total = 0
				for item in psr_lst:
					total += item.product_data.wholesale_price * self.get_qo_info( item , as_int=True )
				self.output.writeln( 'Total : %7.2f Eur HTVA' % total )
		# Collect all extra parameter after "list supplier <PARAM>" "
		if len( params )>1:
			extra_params = list( [ p.lower() for p in params[1:] ] )
		else:
			extra_params = []


		# List product <PARAM> with <PARAM> as digit or text
		if ( len(params)>0 ) and ( params[0].isdigit() ):
			# we have an ID Supplier in parameter --> Show the products
			id_supplier = int( params[0] )
			show_product_list( id_supplier, extra_params )
		else:
			# Sort the list
			sorted_lst = sorted( self.cachedphelper.suppliers, key=lambda item:item.name.lower() )
			# reduce the list
			if len(params)>0:
				_lst = [ item for item in sorted_lst if params[0].lower() in item.name.lower() ]
			else:
				_lst = sorted_lst

			# show product list (if only one supplier returned)
			if len( _lst )==1:
				id_supplier = int( _lst[0].id )
				show_product_list( id_supplier, extra_params )
				return

			# show the list of supplier
			for sup in _lst:
				self.output.writeln(  '%4i : %s ' % (sup.id, sup.name) )

	def do_print_begin( self, params ):
		print( 'print file %s created' % self.output.open_temp_file() )
		dt = datetime.date.today()
		self.output.writeln( 'date %s' % dt.strftime("%d/%m/%Y") )

	def do_print_end( self, params ):
		filename = self.output.close_temp_file()
		print( 'printing %s ...' % filename )
		cmd = 'lp -o media=A4 '
		if self.options['print-landscape']=='1':
			cmd += '-o landscape '
		cmd += '-o cpi='+self.options['print-cpi']+' '
		cmd += '-o lpi='+self.options['print-lpi']+' '
		cmd += '-o sides='+self.options['print-sides']+' '
		cmd += filename

		self.print_once = False;

		os.system( cmd )
		# raise Exception('failed to execute %s')

	def do_print_once( self, params ):
		self.print_once = True
		self.do_print_begin( params )

	def do_print_abort( self, params ):
		self.print_once  = False
		self.output.close_temp_file()
		raise Exception( 'Print file aborted!' )

	def do_quit( self, params ):
		self.output.writeln( "User exit!")
		sys.exit(0)

	def do_reload( self,  params, auto_save = True ):
		""" Reload ALL the data from the WebShow + save the data """
		self.output.writeln( 'Contacting WebShop and reloading...' )
		self.cachedphelper.load_from_webshop()
		self.__init_from_loaded_data() # reinit global variables
		# Also save the cache
		if auto_save:
			self.do_save( params )

	def do_reload_only( self,  params ):
		""" Reload ALL the data from the WebShow (deactivate the auto save) """
		self.reload( self, params, auto_save = False )

	def do_reload_stock( self, params ):
		""" Reload the stock quantities only. """
		self.output.writeln( 'Refreshing stock quantities...' )
		self.cachedphelper.refresh_stock()

	def do_save( self, params ):
		""" Save the memory data to the cache file """
		self.output.writeln( 'Saving cache...' )
		self.cachedphelper.save_cache_file()

	def do_show_keyword( self, params ):
		""" Display keyword equivalents for params """
		kw = params[0].lower()
		if not kw in self.KEYWORDS:
			raise ValueError( '%s is not a valid keyword!' % kw )
		self.output.writeln( '"%s" equivalence are %s' % (kw, ', '.join( self.KEYWORDS[kw])) )

	def do_show_command( self, params ):
		""" Display list of commands """
		for cmd, param_count in self.COMMANDS:
			self.output.writeln( "%s %s" % (cmd, "<%s>" % param_count if param_count!=0 else "" ) )

	def do_show_debug( self, params ):
		""" Show lot of information for inner debugging """
		self.output.writeln( 'debug              : %s' % ('True' if self.cachedphelper.debug else 'false') )
		self.output.writeln( 'last product id    : %s' % self.cachedphelper.products.last_id )

		self.output.writeln( 'PARAMS id_supplier : %i' % self.ID_SUPPLIER_PARAMS )
		self.output.writeln( 'list of option     :' )
		self.do_show_option( params=[], prefix='      ')

	def show_combinations( self, id ):
		""" TOOL:
		    Try to list down the various combination from a given ID_product (or ID_Combination)
			If the id is a combination_id, the code extract the ID_product and list down the combinations """

		assert type(id) is int, 'ID must be integer'

		# extract ID_product from combination
		if is_combination( id ):
			id = unmangle_id_product( id )[0]

		_ids = self.cachedphelper.products.product_combinations( id )
		if len(_ids)==0:
			self.output.writeln( 'No combinations for product ID %s' % id )
			return
		self.output.writeln( "%i combinations for product %s!" % (len(_ids),id) )
		for id_combination in _ids:
			_sa = self.cachedphelper.stock_availables.stockavailable_from_id_product( id_combination )
			_qty = _sa.quantity if _sa else None
			self.output.writeln( '  %10s : %-30s : %s' % (id_combination,self.cachedphelper.products.product_from_id(id_combination).reference,_qty) )

	def do_show_product( self, params ):
		""" Display the details about a given product ID (int).
		    Also accept /xxx or  *zzzz  instead of the ID.
			Relies on the do_list_product() when /xxx ir *zzz must be resolved.
			WHEN do_list_product() only returns one row THEN it also shows the product details :-) """

		# Did the user provides a /supplier_ref or *label_to_search ?
		if( params[0][0] in ( '*','/' ) ):
			# List & display articles matching the request
			psr_lst = self.do_list_product( params )
			# If only 1 items -> resolve id_product and list detail about it
			if len( psr_lst )== 1:
				self.output.writeln( ' ' )
				_id = psr_lst[0].product_data.id
			else:
				# too much product returned ! so abort
				return
		else:
			_id = int( params[0] ) # use the id provided on the command line

		# Try to catch a simple product
		p = self.cachedphelper.products.product_from_id( _id )
		if not( p ):
			# If the ID is not found... maybe it is a combination product (so several product for a base id_product)
			# Just create a list with the found combination products
			_ids = self.cachedphelper.products.product_combinations( _id )
			if len(_ids)==0:
				self.output.writeln( 'No product ID %s' % _id )
				return
			# Else display the list of combinations
			self.output.writeln( " " )
			# Just show it
			for id_combination in _ids:
				self.output.writeln( "%s" % ("-"*40) )
				self.do_show_product( [str(id_combination)] )
				self.output.writeln( " " )
			self.output.writeln( "%i combinations for product %s!" % (len(_ids),_id) )
			for id_combination in _ids:
				_sa = self.cachedphelper.stock_availables.stockavailable_from_id_product( id_combination )
				_qty = _sa.quantity if _sa else None
				self.output.writeln( '  %10s : %-30s : %s' % (id_combination,self.cachedphelper.products.product_from_id(id_combination).reference,_qty) )
			return

		# Display information about simple product
		_sa = self.cachedphelper.stock_availables.stockavailable_from_id_product( _id )
		# _id may contains a base ID_Product (200) ID or an ID_Product_Combination (178500401)
		# So we need to be sure to obtain a base product in any case
		print( 'id : %s ' % _id )
		print( 'product data:' )
		print( p.advanced_stock_management )
		if is_combination( _id):
			print( "base product: %s" % unmangle_id_product(_id)[0] )
			p_base = self.cachedphelper.products.product_from_id( unmangle_id_product(_id)[0] ) # find the base product from the combination product
			print( p_base )
		else:
			print( "not a combination for %s" %_id)
			p_base = p # The product is already a base product

		try:
			_margin = (p.price-p.wholesale_price) / p.wholesale_price * 100
		except:
			_margin = -1
		self.output.writeln( 'Reference  : %s' % p.reference )
		self.output.writeln( 'Name       : %s' % p.name )
		self.output.writeln( 'EAN        : %s' % p.ean13 )
		self.output.writeln( 'ID         : %s  (%s)' % (p.id, 'active' if p.active==1 else 'INACTIVE') )
		self.output.writeln( 'P.A. (%%)   : %6.2f (%4.1f %%)' %  (p.wholesale_price,_margin) )
		self.output.writeln( 'P.V. (TTC) : %6.2f (%6.2f)' % ( p.price, p.price_ttc ) )
		self.output.writeln( ' ' )
		# If stock_available (only reloabale for basic product)
		if _sa and not(is_combination(_id)):
			self.output.writeln( 'Qty        : %i ' % _sa.quantity )
			if _sa.depends_on_stock != _sa.DEPENDS_ON_STOCK_SYNCH:
				self.output.writeln( 'Stock Synch: NOT SYNCH !!! (manual stock)' )
			if _sa.out_of_stock == _sa.OUT_OF_STOCK_ACCEPT_ORDER:
				self.output.writeln( 'Out of Stock: ACCEPT ORDER !!!' )
		elif is_combination(_id):
			# For combination product, just check the advanced_stock_management flag on the products
			if p.advanced_stock_management != 1:
				self.output.writeln( 'Stock Synch: NO ADVANCED STOCK MANAGEMENT !!! (manual stock)' )

		# PARAMS
		_p = self.get_product_params( _id )
		self.output.writeln( 'QM   ( QO ): %2s     ( %2s ) ' % ( _p['QM'] if 'QM' in _p else '---',  _p['QO'] if 'QO' in _p else '---' ) )

		# Supplier Ref
		_supp_ref = -1
		if p.id_supplier:
			_supp_name = self.cachedphelper.suppliers.name_from_id( p.id_supplier )
			_supp_ref  = self.cachedphelper.product_suppliers.reference_for( p.id, p.id_supplier )
			self.output.writeln( 'Supplier   : %s  (%s)' %  (_supp_ref, _supp_name) )
		# other supplier refs
		_supp_refs = self.cachedphelper.product_suppliers.suppliers_for_id_product( _id )
		self.output.writeln( 'Suppliers  : %s' % ', '.join([ref.reference for ref in _supp_refs if ref.reference != _supp_ref  and ref.id_supplier != self.ID_SUPPLIER_PARAMS ]) )


		#self.output.writeln( 'Stock Mngt    : %s' % 'yes' if p.advanced_stock_management == 1 else 'NO' )
		#self.output.writeln( 'Avail.f.order : %s' % 'yes' if p.available_for_order == 1 else 'NO' )
		# xxx



	def do_set_debug( self, params ):
		""" Toggle the debug flag """
		self.cachedphelper.debug = (params[0] == '1')

	def do_set( self, params ):
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
				self.output.writeln( prefix+'%-20s = %s' % (params[0], self.options[params[0]]) )
			else:
				raise ValueError( '%s is not a valid option' % params[0] )
		else:
			# show all params
			for key_val in self.options.iteritems():
				self.output.writeln( prefix+'%-20s = %s' % key_val )

	def do_show_stat( self, params ):
		""" Display the cachec helper statistics """
		self.output.writeln( '%6i Carriers' % len(self.cachedphelper.carriers) )
		self.output.writeln( '%6i OrderStates' % len( self.cachedphelper.order_states ) )
		self.output.writeln( '%6i Products' % len( self.cachedphelper.products ) )
		self.output.writeln( '%6i suppliers' % len( self.cachedphelper.suppliers ) )
		self.output.writeln( '%6i categories' % len( self.cachedphelper.categories ) )
		self.output.writeln( '%6i stock availables' % len( self.cachedphelper.stock_availables ) )
		self.output.writeln( '%6i product suppliers available' % len( self.cachedphelper.product_suppliers ) )
		self.output.writeln( '%6i last product id' % self.cachedphelper.products.last_id )

	def do_upgrade( self, params ):
		""" Just upgrade the software from GitHub depot. """
		if os.system( 'git fetch' )!=0:
			raise Exception( 'git fetching failure!' )
		if os.system( 'git pull' )!=0:
			raise Exception( 'git pulling failure!')
		else:
			self.output.writeln( 'Update complete. Restart the console!' )


def main():
	app = App()
	if os.path.isfile( 'console.startup' ):
		with open( 'console.startup', 'r' ) as f:
			lines = f.readlines()
			app.evaluate_lines( lines )

	app.run()


if __name__ == '__main__':
	main()
