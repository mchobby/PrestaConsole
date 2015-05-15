#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""update-cachefile.py
  
Copyright 2015 DMeurisse <info@mchobby.be>
  
Presta Shop Cache File refresher AND interactive testing - Version alpha

Just load the information from the the WebShop and save it to the
cache file (on request).

To use it in interactive mode do the following:
  1) start python in interactive mode
  2) run the following command (refesh the data as necessary):
  3)   execfile( 'cachefile-update.py' ) 
  4) You can now inspect the cachedHelper and its data
  
  dir( cachedHelper )
  for state in cachedHelper.orderstates:
      print ( 'id, name = %i, %s' % (state.id, state.name )
 
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
from config import Config
import logging
import time
import math

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

cachedHelper = None
	
def main():
	global cachedHelper
	""" Simply create the global reference cachedHelper. Useful for 
	interfactive debugging """
	# just create the needed object
	logging.info( 'create cachedHelper object' )
	cachedHelper = CachedPrestaHelper( config.presta_api_url, config.presta_api_key, debug = False )
	
	value = raw_input( 'Rafraichir le cache (y/n)' )
	if value == 'y':
		logging.info( 'Force cache refreshing from WebShop' )
		cachedHelper.load_from_webshop()
		logging.info( 'Saving cache file' )
		cachedHelper.save_cache_file()
		logging.info( 'file saved' )
	else:
		logging.info( 'Data not refreshed from the WebShop' )
		 

if __name__ == '__main__':
	logging.info( 'cachefile-update Started' )	
	main()
	logging.info( 'cachefile-update End' )	
