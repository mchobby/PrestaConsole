#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""savtrack.py

derivated from prestaconsole.py project
  
Copyright 2014 DMeurisse <info@mchobby.be>
  
Console Presta Shop - Version alpha

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

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

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
			
	#print('mise à jour des qty' )
	#cachedphelper.stock_availables.update_quantities()
	#print( 'Voila, c est fait' )
		
	print( '******************************************************************' )
	print( '*  Derniers Messages client                                      *' )
	print( '******************************************************************' )
		
	""" affiche les x derniers messages clients """
	id = cachedphelper.get_lastcustomermessage_id()
	print( 'last message id: %s' % id )
	custmsgs = cachedphelper.get_lastcustomermessages( id, 10 )
	for custmsg in reversed(custmsgs): # CustomerMessageData
		print( '--- id: %s---------------' % custmsg.id )
		print( '   date_add: %s' % custmsg.date_add )
		print( '   read    : %s' % custmsg.read )
		print( '   Employee: %s' % custmsg.id_employee )
		print( '   id_customer_thread: %s' % custmsg.id_customer_thread )
		print( custmsg.message )
		print( '' )		
	# Ensure cache file to be saved (and will be automatically reloaded)
	#cachedphelper.save_cache_file()
	
	# read char on keyboard
        print( 'Press a key to continue:' ) 
	char = sys.stdin.read(1) 
	return 0

if __name__ == '__main__':
	main()

