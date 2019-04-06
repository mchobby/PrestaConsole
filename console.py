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

from prestaapi import PrestaHelper, CachedPrestaHelper, calculate_ean13, ProductSearchResult, ProductSearchResultList
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
import cmd
import sys

try:
	from Tkinter import *
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


#def list_products( cachedphelper, key ):
#	""" Search for a product base on its partial reference code + list them """
#	assert isinstance( key, str ), 'Key must be a string'
#	if len( key ) < 3:
#		print( 'searching product requires at least 3 characters' )
#		return
#
#	result = cachedphelper.products.search_products_from_partialref( key, include_inactives = True )
#	for item in result:
#		print( '%7i : %s - %s' % (item.id,item.reference.ljust(30),item.name) )


#def build_supplier_product_list( cachedphelper ):
#	""" Build a list of product for that supplier (the default supplier) """
#	r = []
#	products = cachedphelper.get_products()
#	for item in products:
#		_cargo = Product_cargo( item )
#		# Identify stock information
#		stock = cachedphelper.stock_availables.stockavailable_from_id_product( _cargo.id )
#		if stock:
#			_cargo.qty_stock = stock.quantity
#		r.append( _cargo )
#	# Also locates all the IT-xxx articles.
#	# They are NOT ACTIVE so we would not duplicate them
#	for item in products.inactivelist:
#		if item.reference.find( 'IT-' ) == 0:
#			_cargo = Product_cargo( item )
#			# Identify stock information
#			stock = cachedphelper.stock_availables.stockavailable_from_id_product( _cargo.id )
#			if stock:
#				_cargo.qty_stock = stock.quantity
#			r.append( _cargo )
#	return r



def progressHandler( prestaProgressEvent ):
	if prestaProgressEvent.is_finished:
		print( '%s' %prestaProgressEvent.msg )
	else:
		print( '%i/%i - %s' % ( prestaProgressEvent.current_step, prestaProgressEvent.max_step, prestaProgressEvent.msg ) )

class PrestaOut( object ):
	""" Class to manage the ouput of data to various streams """

	def __init__( self ):
		self.fh = None # File handle
		self.filename = ''  #  filename for the file handle

	def writeln( self, obj ):
		#print( obj.decode( sys.stdout.encoding ) )
		print( obj )
		if self.fh != None:
			self.fh.write( obj )
			self.fh.write(  '\n' )

	def write_lines( self, lines ):
		""" just write all the lines contained in the list """
		for l in lines:
			self.writeln( l )

	def open_temp_file( self ):
		""" Open temportary file to write output content.
		    Later, this file will be used to content to the printer :-)

			:returns: the openned temporary filename
		"""
		if self.fh:
			return self.filename

		# Create a new temporary file
		self.filename = tempfile.mktemp( '-console-print.txt' )
		self.fh = open( self.filename, 'w' )
		return self.filename

	def close_temp_file( self ):
		""" just close the temporary file.

			:returns: the just closed temporary filename. """
		if not self.fh:
			raise Exception( 'No printer file open!' )
		_r = self.filename
		self.fh.close()
		self.fh = None
		self.filename = None
		return _r


class CmdParse(cmd.Cmd):
	prompt = '> '
	#def do_listall(self, line):
	#	print(commands)
	def __init__( self, cmd_callback ):
		cmd.Cmd.__init__( self )
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
		self.cmd_parse = CmdParse( self.cmd_parse_callback )
		self.config = Config()
		self.KEYWORDS = keywords
		self.COMMANDS = commands
		self.output = PrestaOut()

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
				self.output.writeln( '> %s' % value )
				self.evaluate_line( value )
			except Exception as err:
				self.output.writeln( '[ERROR] %s' % err )
				if self.cachedphelper.debug:
					traceback.print_exc()

	#def run_deprecated( self ):
	#	""" Run the main cmd line requests loop """
	#	value = ''
	#	while value != 'quit':
	#		try:
	#			value = raw_input( '> ' )
	#			self.evaluate_line( value )
	#			self.output.writeln('')
    #
	#		except Exception as err:
	#			self.output.writeln( '[ERROR] %s' % err )
	#			if self.cachedphelper.debug:
	#				traceback.print_exc()

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
	None      : ['from'] # remove any from and to

}

# Commands + Needed parameters + function to call
#    Needed Parameter '+': 1 or more, '*': 0 or mode, numeric (exactly X values)
COMMANDS = [
	('ean'            , 1   ),
	('help keyword'   , 1   ),
	('help command'   , 0   ),
	('help'           , 0   ),
	('bag clear'      , 0   ),
	('bag export'     , 0   ),
	('bag import'     , 0   ),
	('bag links'      , 0   ),
	('bag'            , 0   ),
	('check stock config',0 ),
	('editor begin'   , 0   ),
	('editor end'     , 0   ),
	('editor once'    , 0   ),
	('editor abort'   , 0   ),
	('label product'  , 1   ),
	('label small'    , 0   ),
	('label large'    , 0   ),
	('label king'     , 0   ),
	('label war'      , 0   ),
	('label vat'      , 0   ),
    ('list product'   , '+' ),
	('list supplier'  , '*' ),
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
	('show debug'     , 0   ),
	('show option'    , '*' ),
	('show product'   , 1   ),
	('show stat'      , 0   ),
	('upgrade'        , 0   )
	]


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
				raise Exception( 'Invalid product PARAMS "%s" in "%s" for id_product %s. it must have 2 parts (colon separated!)' % (vals, reference,id_product) )
			result[vals[0]] = vals[1]

		return result

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
		sTitle += '%7s | %-30s | %5s' % ('ID', 'Reference', 'stock' )
		sPrint += '%7i | %-30s | %5i'
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
	def do_bag( self, params ):
		""" View the content of the bag (shopping basket """
		#def view_bag( cachedphelper, bag, max_row=None, desc=False ):

		#_desc = False # Display in descending order

		if len( self.bag )==0:
			self.output.writeln(  '(empty bag)' )
		else:
			self.output_product_search_result( psr_list = self.bag )
			totals = self.bag.total_price_ordered() # sum, sum_ttc, sum_wholesale_price
			self.output.writeln( 'Total (TTC) : %6.2f Eur (%6.2f TTC)' % (totals[0], totals[1]) )
			if totals[2]>0:
				self.output.writeln( 'Marge       : %6.2f Eur (%4.2f %%)' % (totals[0]-totals[2], ((totals[0]-totals[2])/totals[2])*100) )
		#for idx, item in enumerate( reversed(self.bag) if _desc else self.bag ):
		#	#if max_row and (idx>=max_row):
		#	#	print( '> ...' ) # indicates the presence of more items in the bag
		#	#	break;
		#
		#	print( '%3i x %7i : %s - %s' % (item.qty, item.product.id,item.product.reference.ljust(30),item.product.name) )

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


	def do_ean( self, params ):
		""" Generates the EAN13 for the ID_Product """
		assert len(params)>0 and isinstance( params[0], str ) and params[0].isdigit(), 'the parameter must be an ID product'

		_id = int( params[0] )
		product_ean = '32321%07i' % _id  # prefix 3232 + product 1 + id_product
		product_ean = calculate_ean13( product_ean ) # Add the checksum to 12 positions
		self.output.writeln( '%s' % product_ean )

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

	def do_help( self, params ):
		""" Display Help """
		os.system( 'less console.help' )

	def do_help_keyword( self, params ):
		""" Display keyword equivalents for params """
		kw = params[0].lower()
		if not kw in self.KEYWORDS:
			raise ValueError( '%s is not a valid keyword!' % kw )
		self.output.writeln( '"%s" equivalence are %s' % (kw, ', '.join( self.KEYWORDS[kw])) )

	def do_help_command( self, params ):
		""" Display list of commands """
		for cmd, param_count in self.COMMANDS:
			self.output.writeln( "%s %s" % (cmd, "<%s>" % param_count if param_count!=0 else "" ) )

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


	def do_label_war( self, params ):
		handle_print_warranty_label_large()

	def do_label_vat( self, params ):
		handle_print_vat_label_large()

	def do_list_product( self, params ):
		""" Search for a product base on its partial reference code + list themself.

		:return: ProductSearchResultList computed and displayed by the function. """
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
				print( 'Total : %7.2f Eur HTVA' % total )
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

	def do_show_debug( self, params ):
		""" Show lot of information for inner debugging """
		self.output.writeln( 'debug              : %s' % ('True' if self.cachedphelper.debug else 'false') )
		self.output.writeln( 'last product id    : %s' % self.cachedphelper.products.last_id )

		self.output.writeln( 'PARAMS id_supplier : %i' % self.ID_SUPPLIER_PARAMS )
		self.output.writeln( 'list of option     :' )
		self.do_show_option( params=[], prefix='      ')

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

		p = self.cachedphelper.products.product_from_id( _id )
		if not( p ):
			self.output.writeln( 'No product ID %s' % _id )
			return

		_sa = self.cachedphelper.stock_availables.stockavailable_from_id_product( _id )
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
		if _sa:
			self.output.writeln( 'Qty        : %i ' % _sa.quantity )
			if _sa.depends_on_stock != _sa.DEPENDS_ON_STOCK_SYNCH:
				self.output.writeln( 'Stock Synch: NOT SYNCH !!! (manual stock)' )
			if _sa.out_of_stock == _sa.OUT_OF_STOCK_ACCEPT_ORDER:
				self.output.writeln( 'Out of Stock: ACCEPT ORDER !!!' )

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
