#!/usr/bin/python
#-*- encoding: utf8 -*-
""" Configuration management for PrestaConsole and others """

from ConfigParser import ConfigParser

CONFIG_FILENAME = 'config.ini'
# Sections names
CONFIG_SECTION_PRESTAAPI = 'PRESTA-API'
CONFIG_SECTION_DEBUG = 'DEBUG'
CONFIG_SECTION_LCD = 'LCD-DISPLAY'
CONFIG_SECTION_COMPANY = 'COMPANY'
CONFIG_SECTION_TOTE_BAG= 'TOTE-BAG'
CONFIG_SECTION_ORDER_SHIP = 'ORDER-SHIP'

# Keynames for section PRESTA-API
CONFIG_KEY_KEY = 'key'
CONFIG_KEY_URL = 'url'

# Keynames for section DEBUG
CONFIG_KEY_LOGFILE = 'logfile'

# Keynames for section LCD-DISPLAY
CONFIG_KEY_DEVICE_PATH = 'device-path'

# Keynames for section COMPANY
CONFIG_KEY_NAME  = 'name'
CONFIG_KEY_ADDR  = 'addr'
CONFIG_KEY_VAT   = 'vat'
CONFIG_KEY_PHONE = 'phone'
CONFIG_KEY_WEB   = 'web'

# Tote Bag
CONFIG_KEY_EXPORT_PATH = 'export_path'

# Order-Ship
CONFIG_KEY_DATA_PATH = 'data_path'

class Config(object):
	"""read paramters from the "config.ini" configuration file"""
	_presta_api_key = 'None'
	_presta_api_url = 'None'
	_logfile = 'None'
	_lcd_device = 'None'

	_company_name = 'None'
	_company_address = []
	_company_vat = ''
	_company_phone = ''
	_company_web = ''

	_tote_bag_export_path = ''

	_order_ship_data_path = ''

	def __init__( self ):
		config = ConfigParser()
		config.read( CONFIG_FILENAME )

		self._presta_api_key = config.get( CONFIG_SECTION_PRESTAAPI, CONFIG_KEY_KEY )
		self._presta_api_url = config.get( CONFIG_SECTION_PRESTAAPI, CONFIG_KEY_URL )
		self._logfile = config.get( CONFIG_SECTION_DEBUG, CONFIG_KEY_LOGFILE )
		self._lcd_device = config.get( CONFIG_SECTION_LCD, CONFIG_KEY_DEVICE_PATH )

		# Read the company information (optional)
		try:
			self._company_name = config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_NAME )
		except:
			pass
		try:
			self._company_address.append( config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_ADDR+'1' ) )
		except:
			self._company_address.append('')
		try:
			self._company_address.append( config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_ADDR+'2' ) )
		except:
			self._company_address.append('')
		try:
			self._company_address.append( config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_ADDR+'3' ) )
		except:
			self._company_address.append('')
		try:
			self._company_vat = config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_VAT )
		except:
			pass
		try:
			self._company_phone = config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_PHONE )
		except:
			pass
		try:
			self._company_url = config.get( CONFIG_SECTION_COMPANY, CONFIG_KEY_WEB )
		except:
			pass
		try:
			self._tote_bag_export_path = config.get( CONFIG_SECTION_TOTE_BAG, CONFIG_KEY_EXPORT_PATH )
		except:
			pass

		try:
			self._order_ship_data_path = config.get( CONFIG_SECTION_ORDER_SHIP, CONFIG_KEY_DATA_PATH )
		except:
			pass

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

	@property
	def company_name( self ):
		return self._company_name

	@property
	def company_address( self ):
		return self._company_address

	@property
	def company_vat( self ):
		return self._company_vat

	@property
	def company_phone( self ):
		return self._company_phone

	@property
	def company_url( self ):
		return self._company_url

	@property
	def tote_bag_export_path(self):
		return self._tote_bag_export_path

	@property
	def order_ship_data_path( self ):
		return self._order_ship_data_path
