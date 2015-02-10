#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""prestaconsole.py
  
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

config = Config()
logging.basicConfig( filename=config.logfile, level=logging.DEBUG, 
	format='%(asctime)s - [%(levelname)s] %(message)s',
	datefmt='%d/%m/%y %H:%M:%S.%f' )

def main():
	# Execute the PrestaShopHelper classes tests
	run_prestahelper_tests(  config.presta_api_url, config.presta_api_key, debug = False )
	
	return 0

if __name__ == '__main__':
	main()

