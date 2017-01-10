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
import logging, os
from logging.handlers import SysLogHandler # Send entries to syslog server
import sys
import signal
import curses
from time import sleep

# from pypcl import calculate_ean13, ZplDocument, PrinterCupsAdapter
PRINTER_ENCODING = 'cp850'

LOGGING_LEVEL = logging.DEBUG # DEBUG, INFO, WARNING, ERROR, CRITICAL

HELP_MESSAGE = """+Q : quit
+R : reload 
+S : save"""

#logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
#	format='%(asctime)s - [%(levelname)s] %(message)s',
#	datefmt='%d/%m/%y %H:%M:%S.%f' )

# LABEL Size is stored into the article reference of the "PARAMS" supplier.
ID_SUPPLIER_PARAMS = None

class MyApp:
	def __init__( self, screen ):
		self.screen = screen 
		(self.height, self.width) = screen.getmaxyx()
		self.subwin = [] # Subwin list
		self.create_subwin()

		# Create a SysLog handler
		self.logger = logging.getLogger()
		self.logger.setLevel( logging.DEBUG )
		# Follow the log with
		#    tail -f /var/log/syslog 
		# formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
		#    also mention the python filename in the log
		formatter = logging.Formatter( os.path.basename(__file__)+' :: %(levelname)s :: %(message)s')
		sys_handler = SysLogHandler( address = '/dev/log')
		sys_handler.setLevel( LOGGING_LEVEL )
		sys_handler.setFormatter( formatter )
		self.logger.addHandler( sys_handler )

		self.logger.info( 'Starting app' )
		self.config = Config()
		self.cachedphelper  = CachedPrestaHelper( self.config.presta_api_url, self.config.presta_api_key, debug = False ) #, progressCallback = progressHandler )
		# initialize global variables
		self.initialize_globals()

	def initialize_globals( self ):
		""" Initialize the global var @ startup or @ reload """
		global ID_SUPPLIER_PARAMS
		_item = self.cachedphelper.suppliers.supplier_from_name( "PARAMS" )
		#for _item in cachedphelper.suppliers:
		#	print( '%i - %s' % (_item.id,_item.name) )
		if _item != None:
			ID_SUPPLIER_PARAMS = _item.id
			self.logger.info( 'Catched PARAMS supplier :-). ID: %i' % ID_SUPPLIER_PARAMS )	

	def create_subwin(self):
		self.wresult = curses.newwin(self.height-1,self.width,0,0) # NLines, NCols, begin_y, begin_x
		self.wresult.border()
		self.wresult.addstr(0,2,"[ Result ]")
		self.wresult.addstr(1,1,"%i , %i" % self.wresult.getmaxyx() )
		self.subwin.append( (self.wresult,self.wresult_redraw) )

		self.status = curses.newwin(2,self.width,self.height-1,0) # min 2 lines height!!!

	def wresult_redraw(self):
		""" redraw the subwin background """
		self.wresult.clear()
		self.wresult.border()
		self.wresult.addstr( 0, 2, "[ Result ]" )

	#def draw_screen(self)

	def status_redraw( self, input_text=None, input_data=None, info=None ):
		""" redraw the status bar """
		self.status.addstr( 0, 0, " "*self.width, curses.A_REVERSE )

		# Only draw information in the second part of the screen
		info = '| +h for Help' if info==None else '| %s'%info
		info = info + ' '*(self.width//2-len(info))
		self.status.addstr( 0, self.width//2, '%s' % info, curses.A_REVERSE )
		
		# Draw input_text and input_data in the first part of the screen
		if input_text or input_data:
			_s = "%s%s" % (input_text,input_data if input_data else '')
			self.status.addstr( 0, 1, _s, curses.A_REVERSE )

		self.status.refresh()

	def screen_redraw( self ):
		""" Draw every subwindow THEN refresh the whole terminal """
		self.screen.clear()		
		# full screen redraw
		for win, redraw in self.subwin:
		    redraw()
		self.status_redraw()
		# Refresh the output
		self.refresh()

	def refresh( self ):
		""" makes curses refreshing the whole terminal content """ 
		for win, redraw  in self.subwin:
			win.refresh()
		self.status.refresh()

	def input( self, text = '?' ):
		""" capture a string from the keyboard, each characters in the status bar.
		returns a tuple (input_string,last_ch_ascii_code) """
		_r = ''
		self.status_redraw( input_text=text, input_data=_r )

		ch = 0
		while True:
			ch = self.status.getch()
			self.logger.debug( 'getch returned %i' % ch )
			if ch in (13,10): # CR/LF
				break
			elif ch == 127: # backspace
			    if len(_r)>0:
					_r = _r[:-1]
			elif ch == 27: # escape
				if len(_r)>0: # First time, we clear the input
					_r = ''
				else:
					break # Second time (so when empty): we exit the input 
			elif 31 <= ch < 256:
				_r = _r + chr(ch)

			# Display the current value
			self.status_redraw( input_text=text, input_data=_r )
			self.status.refresh()

		# Clear input field zone in the status bar
		self.status_redraw( input_text=None, input_data=None )

		self.logger.debug( 'input() returns with "%s" and last key %i' % (_r,ch) )
		return (_r,ch)

	def search_products( self, key=None, ean=None, id=None ):
		""" Search for a product based on its partial reference code (key) -OR- its ean -OR- product ID.

		:return: None or a list of product """
		
		result = None
		if key:
			assert isinstance( key, str ), 'Key must be a string'
			if len( key ) < 3:
				print( 'searching product requires at least 3 characters' )
				return
			result = self.cachedphelper.products.search_products_from_partialref( key )
		elif ean:
			assert isinstance( ean, str ), 'Key must be a string'
			result = self.cachedphelper.products.search_products_for_ean( ean )
		elif id:
			assert isinstance( id, int ), 'ID must be an integer'
			_r = self.cachedphelper.products.product_from_id( id )
			result = [_r] if _r else None

		return result

	def display_products( self, products, auto_select=False ):
		""" Display a list of products in the wresult Windows 

		:param products: list of product to display.
		:param auto_select: automaticaly select the first row WHEN it is the unique row! """
		self.logger.debug('display_products')
		iTopIndex = 0 # Index of the TOP record in the products list
		iSelected = 0 # Index of the ITEM currently selected 
		hClient = self.wresult.getmaxyx()[0] - 2 # Height of the client area
		wclient = self.wresult.getmaxyx()[1] - 2
		while products and len( products )>0: # At least one item
			self.wresult_redraw()
			iRow = 0
			for i in range(iTopIndex,iTopIndex+hClient):
				# self.logger.debug( '%i' % i)
				if i >= len(products):
					continue
				item = products[i]
				_s = '%4i: %s (%6.2f) %6.2f EUR' % (item.id,item.reference.ljust(20),item.price,item.price*1.21) 
				self.wresult.addstr( iRow+1,1, _s, curses.A_REVERSE if i == iSelected else 0 )
				iRow += 1
			self.wresult.refresh()

			# auto_select
			if len( products )==1 and auto_select:
				return products[0]

			# user input
			self.status_redraw( input_text='browsing result...')
			ch = self.status.getch()
			self.logger.debug( 'getch returned %i' % ch )
			if ch in (13,10): # CR/LF
				return products[iSelected]
			#elif ch == 27: #ESC -- also returned with escape sequence....
			#	return None
			elif ch == 66: # arrow down
				# Select next
				iSelected += 1
				if iSelected >= len( products ):
					iSelected = len( products )-1
				# Keep selected row visible
				if iSelected >= (iTopIndex + hClient):
					iTopIndex += 1
			elif ch == 65: # arrow up
				iSelected -= 1
				if iSelected <= 0:
					iSelected = 0
				# Keep selected row visible
				if iSelected < iTopIndex:
					iTopIndex = iSelected

		# Always return something
		return None 


	def run( self ):
		self.screen_redraw()

		while True:
			(_cmd,_ch) = self.input( text='Cmd?' )

			# special commands
			if _cmd.upper() == '+Q':
				break # Exit the software
			elif _cmd.upper() == '+R':
				self.status_redraw( info='Contacting WebShop and reloading...' )
				self.cachedphelper.load_from_webshop()
				self.initialize_globals() # reinit global variables
				self.screen_redraw()
				self.status_redraw( info='Data reloaded!')
				sleep( 1 )
				continue	
			elif _cmd.upper() == '+S':
				print( 'Saving cache...' )
				self.status_redraw( info = 'Saving cache...')
				self.cachedphelper.save_cache_file()
				self.screen_redraw()
				self.status_redraw( info='Data saved!' )
				sleep( 1 )
				continue
			elif _cmd.upper() == '+H':
				# Display the Help
				self.wresult_redraw()
				for idx, line in enumerate( HELP_MESSAGE.split('\n') ):
					self.wresult.addstr( 1+idx,1, line )
				self.wresult.refresh()
				self.status_redraw(input_text='Press return to continue')
				self.wresult.getch()
				self.wresult_redraw()

					
			_l = None # List of products
			if _cmd.isdigit():
				if len(_cmd)<=5: # we are looking for a product ID
					_l = self.search_products( id=int(_cmd) )
				else:
					_l = self.search_products( ean=_cmd )
			else:
				if len(_cmd)<3:
					self.status_redraw( input_text='Min. 3 chars!!!' )
					sleep( 1 )
				else:
					_l = self.search_products( key=_cmd )
			# Show the product on the screen
			self.display_products( _l, auto_select=True )
			
			self.refresh()
		

def main(screen):
	# Cursor invisible
	#curses.curs_set( 0 )
	curses.start_color()
	app = MyApp( screen )
	app.run()

def list_products( cachedphelper, key=None, ean=None, id=None ):
	""" Search for a product base on its partial reference code (key) -OR- its ean -OR- product ID + list them """
	
	result = None
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
			print( '%4i: %s (%6.2f) %6.2f EUR' % (item.id,item.reference.ljust(20),item.price,item.price*1.21) )
			print( '      %s' % item.name )
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
		

	
def main2():
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

def catch_ctrl_C(sig,frame):
    print "Il est hors de question d'autoriser la sortie sauvage!"

if __name__ == '__main__':
	# signal.signal(signal.SIGINT, catch_ctrl_C)
	curses.wrapper( main )
	# main2()

