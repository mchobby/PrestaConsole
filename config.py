#!/usr/bin/python
#-*- encoding: utf8 -*-
""" Configuration management for PrestaConsole and others """

from ConfigParser import ConfigParser
from os.path import expanduser

CONFIG_FILENAME = 'config.ini'
# Sections names
CONFIG_SECTION_PRESTAAPI = 'PRESTA-API'
CONFIG_SECTION_APP = 'APP'
CONFIG_SECTION_DEBUG = 'DEBUG'
CONFIG_SECTION_LCD = 'LCD-DISPLAY'
CONFIG_SECTION_COMPANY = 'COMPANY'
CONFIG_SECTION_TOTE_BAG= 'TOTE-BAG'
CONFIG_SECTION_ORDER_SHIP = 'ORDER-SHIP'

# Keynames for section PRESTA-API
CONFIG_KEY_KEY = 'key'
CONFIG_KEY_URL = 'url'

# Keynames for section PRESTA-API
CONFIG_KEY_PROMPT     = 'prompt'
CONFIG_KEY_BATCH_PATH = 'batch_path'
CONFIG_KEY_PRINTER_SHORTLABEL_QUEUE_NAME = 'printer_shortlabel_queue_name'
CONFIG_KEY_PRINTER_LARGELABEL_QUEUE_NAME = 'printer_largelabel_queue_name'
CONFIG_KEY_PRINTER_TICKET_QUEUE_NAME     = 'printer_ticket_queue_name'

CONFIG_KEY_SHOP_INFO_SMALL = 'shop_info_small'
CONFIG_KEY_SHOP_INFO_LARGE = 'shop_info_large'

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
CONFIG_KEY_MAIL_API = 'mail_api'
CONFIG_KEY_MAIL_API_KEY = 'mail_api_key'
CONFIG_KEY_MAIL_API_SECRET = 'mail_api_secret'

class Config(object):
	"""read paramters from the "config.ini" configuration file"""
	_presta_api_key = 'None'
	_presta_api_url = 'None'
	_app_prompt     = ''
	_logfile = 'None'
	_lcd_device = 'None'

	_company_name = 'None'
	_company_address = []
	_company_vat = ''
	_company_phone = ''
	_company_web = ''

	_tote_bag_export_path = ''

	_order_ship_data_path = ''
	_order_ship_mail_api = None
	_order_ship_mail_api_key = None
	_order_ship_mail_api_secret = None

	def __init__( self ):
		config = ConfigParser()
		config.read( CONFIG_FILENAME )

		self._presta_api_key = config.get( CONFIG_SECTION_PRESTAAPI, CONFIG_KEY_KEY )
		self._presta_api_url = config.get( CONFIG_SECTION_PRESTAAPI, CONFIG_KEY_URL )

		self._app_prompt = config.get( CONFIG_SECTION_APP, CONFIG_KEY_PROMPT )
		try:
			self._batch_path = config.get( CONFIG_SECTION_APP, CONFIG_KEY_BATCH_PATH )
		except:
			self._batch_path = expanduser("~")

		self._printer_shortlabel_queue_name = config.get( CONFIG_SECTION_APP, CONFIG_KEY_PRINTER_SHORTLABEL_QUEUE_NAME )
		self._printer_largelabel_queue_name = config.get( CONFIG_SECTION_APP, CONFIG_KEY_PRINTER_LARGELABEL_QUEUE_NAME )
		self._printer_ticket_queue_name     = config.get( CONFIG_SECTION_APP, CONFIG_KEY_PRINTER_TICKET_QUEUE_NAME )
		self._shop_info_small = config.get( CONFIG_SECTION_APP, CONFIG_KEY_SHOP_INFO_SMALL )
		self._shop_info_large = config.get( CONFIG_SECTION_APP, CONFIG_KEY_SHOP_INFO_LARGE )

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

		self._order_ship_api = None
		self._order_ship_api_key = None
		self._order_ship_api_secret = None
		try:
			self._order_ship_data_path = config.get( CONFIG_SECTION_ORDER_SHIP, CONFIG_KEY_DATA_PATH )
			self._order_ship_api = config.get( CONFIG_SECTION_ORDER_SHIP, CONFIG_KEY_MAIL_API )
			self._order_ship_api_key = config.get( CONFIG_SECTION_ORDER_SHIP, CONFIG_KEY_MAIL_API_KEY )
			self._order_ship_api_secret = config.get( CONFIG_SECTION_ORDER_SHIP, CONFIG_KEY_MAIL_API_SECRET )
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
	def prompt( self ):
		""" The prompt to be displayed in the front of command prompt """
		return self._app_prompt

	@property
	def batch_path( self ):
		""" where are stored the batch files """
		return self._batch_path if len( self._batch_path)>0 else None

	@property
	def printer_shortlabel_queue_name( self ):
		return self._printer_shortlabel_queue_name

	@property
	def printer_largelabel_queue_name( self ):
		return self._printer_largelabel_queue_name

	@property
	def printer_ticket_queue_name( self ):
		return self._printer_ticket_queue_name

	@property
	def shop_info_small( self ):
		""" Shop information to display on small labels """
		return [ unicode(item) for item in self._shop_info_small.split( '/n') ]

	@property
	def shop_info_large( self ):
		""" Shop information to display on small labels """
		return [ unicode(item) for item in self._shop_info_large.split( '/n') ]

	@property
	def shop_info_small( self ):
		""" Shop information to display on small labels """
		return [ unicode(item) for item in self._shop_info_small.split( '/n') ]

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

	@property
	def order_ship_api( self ):
		assert self._order_ship_api
		return self._order_ship_api

	@property
	def order_ship_api_key( self ):
		assert self._order_ship_api_key
		return self._order_ship_api_key

	@property
	def order_ship_api_secret( self ):
		assert self._order_ship_api_secret
		return self._order_ship_api_secret
