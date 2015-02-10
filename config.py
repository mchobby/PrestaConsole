#!/usr/bin/python
#-*- encoding: utf8 -*-
""" Configuration management for PrestaConsole and others """

from ConfigParser import ConfigParser

CONFIG_FILENAME = 'config.ini'
# Sections names
CONFIG_SECTION_PRESTAAPI = 'PRESTA-API'
CONFIG_SECTION_DEBUG = 'DEBUG'
CONFIG_SECTION_LCD = 'LCD-DISPLAY'

# Keynames for section PRESTA-API
CONFIG_KEY_KEY = 'key'
CONFIG_KEY_URL = 'url'

# Keynames for section DEBUG
CONFIG_KEY_LOGFILE = 'logfile'

# Keynames for section LCD-DISPLAY
CONFIG_KEY_DEVICE_PATH = 'device-path'

class Config(object):
	"""read paramters from the "config.ini" configuration file"""
	_presta_api_key = 'None'
	_presta_api_url = 'None'
	_logfile = 'None'
	_lcd_device = 'None' 
	
	def __init__( self ):
		config = ConfigParser()
		config.read( CONFIG_FILENAME )
		
		self._presta_api_key = config.get( CONFIG_SECTION_PRESTAAPI, CONFIG_KEY_KEY )
		self._presta_api_url = config.get( CONFIG_SECTION_PRESTAAPI, CONFIG_KEY_URL )
		self._logfile = config.get( CONFIG_SECTION_DEBUG, CONFIG_KEY_LOGFILE )
		self._lcd_device = config.get( CONFIG_SECTION_LCD, CONFIG_KEY_DEVICE_PATH )
		
	@property
	def presta_api_key( self ):
		""" Access key to the PrestaShop API - must be generated in the 
		PrestaShop backend"""
		return self._presta_api_key
	
	@property
	def presta_api_url( self ):
		""" target url to join the PrestaShop API with the Key.
		Should be http://shop.my_domain_name.be/api"""
		return self._presta_api_url
		
	@property
	def logfile( self ):
		""" short name of the log file """
		return self._logfile

	@property
	def lcd_device( self ):
		""" device path where is attached the LCD Device """
		return self._lcd_device
