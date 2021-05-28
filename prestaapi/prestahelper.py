#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""prestahelper.py - classes and helper for accessing the PrestaShop API

Created by Meurisse D. <info@mchobby.be>

Copyright 2014 MC Hobby SPRL, All right reserved
"""

from prestapyt import PrestaShopWebServiceError, PrestaShopWebService
from xml.etree import ElementTree # --> print( ElementTree.tostring( el ) )
from collections import defaultdict
from pprint import pprint
import logging
import pickle
import os.path
from datetime import datetime

PRESTA_UNDEFINE_INT = -1

def save_to_file( base_name, el ):
	""" Helper: Save the readable version of the element tree for easy debugging.
	    file will be created with .debug.xml suffix """
	filename = "%s.debug.xml" % base_name
	import codecs
	with codecs.open(filename, "w", "utf-8-sig") as temp:
		temp.write( ElementTree.tostring( el ) )
	print( "%s saved!" % filename )

def etree_to_dict(t):
    d = {t.tag: {} if t.attrib else None}
    children = list(t)
    if children:
        dd = defaultdict(list)
        for dc in map(etree_to_dict, children):
            for k, v in dc.iteritems():
                dd[k].append(v)
        d = {t.tag: {k:v[0] if len(v) == 1 else v for k, v in dd.iteritems()}}
    if t.attrib:
        d[t.tag].update(('@' + k, v) for k, v in t.attrib.iteritems())
    if t.text:
        text = t.text.strip()
        if children or t.attrib:
            if text:
              d[t.tag]['#text'] = text
        else:
            d[t.tag] = text
    return d

def extract_hashtext( item, default_lang_id='2' ):
	""" Extract the #text from the provided item (eg: item = items[i]['name'] ).
		Take care about monolingual & multilingual configuration

		ON MONOLINGUAL system : the label can be extracted with item['language']['#text']

		ON MULTILINGUAL system : the label is stored into a list a dictionnary.
		eg: item['language'] will be a list of dict
               [ {'#text': "En attente d'autorisation",
                   '@id': '1',
                   '@{http://www.w3.org/1999/xlink}href': 'https://shop.mchobby.be/api/languages/1'},
                 {'#text': "En attente d'autorisation",
                   '@id': '2',
                   '@{http://www.w3.org/1999/xlink}href': 'https://shop.mchobby.be/api/languages/2'}
               ]
	"""
	if isinstance( item['language'] , list ):
		# extract multilingual
		for label_dic in item['language']:
			if label_dic['@id'] == default_lang_id:
				if '#text' in label_dic: # cover strange case: {'language': {'@id': '2'}
					return label_dic['#text']
				else:
					return ''
	else:
		if '#text' in item['language']:
			return item['language']['#text']
		else:
			return ''

def ean13_checksum(ean_base):
	"""Calculates the checksum for EAN13-Code.
	   special thanks to python-barcode
	   http://code.google.com/p/python-barcode/source/browse/barcode/ean.py?r=3e6fe8dbabbf49726a4f156657511e941f7743df

	ean_base (str) - the 12 first positions of the ean13.

	returns (int) - the checkdigit (one number)

	example: ean13_checksum( '323210000576' ) --> 1
	"""
	sum_ = lambda x, y: int(x) + int(y)
	evensum = reduce(sum_, ean_base[::2])
	oddsum = reduce(sum_, ean_base[1::2])
	return (10 - ((evensum + oddsum * 3) % 10)) % 10

def calculate_ean13( ean_base ):
	"""compose the full ean13 from ean base (12 position) + calculated checksum

	example: calculate_ean13( '323210000576' ) --> '3232100005761' """
	return ean_base+str(ean13_checksum(ean_base))

def coalesce(*a):
    """Return the first non-`None` argument, or `None` if there is none."""
    return next((i for i in a if i is not None), None)

def canonical_search_string( sText ):
	"""Return the essential elements for text searching """
	if sText == None:
		return ''
	__s = sText.replace( ' ', '' )
	__s = __s.replace( '.', '' );
	__s = __s.replace( '-', '' );
	return __s.upper()


class PrestaHelper(object):
	"""Helper class to obtain structured information from
	   prestashop API"""
	__prestashop = None
	__prestashop_api_access = {'url' : None, 'key' : None }

	def __init__( self, presta_api_url, presta_api_key, debug = __debug__ ):
		""" constructor with connection parameter to PrestaShop API. """
		# Keep track of parameters
		self.__prestashop_api_access['url'] = presta_api_url
		self.__prestashop_api_access['key'] = presta_api_key

		logging.info( 'connecting Presta API @ %s...', (presta_api_url) )
		self.__prestashop = PrestaShopWebService( presta_api_url, presta_api_key )

		self.__debug = debug
		self.__prestashop.debug = debug

	@property
	def debug( self ):
		return self.__debug

	@debug.setter
	def debug( self, value ):
		self.__debug = value
		self.__prestashop.debug = value

	@property
	def webservice( self ):
		""" Direct access to the underlying WebService (if needed). """
		return self.__prestashop

	def search( self, pattern, options ):
		""" Giving access to search capability of underlaying PrestaShop WebService """

		# Search are organised as follow
		#    (Store URL)/api/customers/?display=[firstname,lastname]&filter[id]=[1|5]
		#    (store URL)/api/orders/?display=[id,current_state]&limit=25&sort=id_DESC
		# See source:
		#    http://doc.prestashop.com/display/PS14/Chapter+8+-+Advanced+Use
		#
		return self.__prestashop.search( pattern, options = options )

	def get_accessrights( self ):
		""" Return the access rights on API as dictionnary

		Really convenient to check the prestashop connexion."""
		el = self.__prestashop.get( '' )
		item = etree_to_dict( el )
		item = item['prestashop']['api'] #  skip nodes prestashop & api
		# remove attribute nodes
		_result = {}
		for k,v in item.items():
		  if not k.startswith('@'):
			  _result[k] = v
		return _result

	def get_lastcustomermessage_id( self ):
		""" Retreive the last customer message ID Stored into PrestaShop"""
		el = self.__prestashop.search( 'customer_messages', options={'limit':1, 'sort' : 'id_DESC'} )
		item = etree_to_dict( el )
		return int( item['prestashop']['customer_messages']['customer_message']['@id'] )

	def get_lastcustomermessages( self, fromId, count=1 ):
		""" Retreive the last customer messages stored in PrestaShop

		fromId - ID from the message message to start from (see get_lastcustomermessage_id)
		count  - (default=1) the number of messages to retreive fromId (counting down)

		Returns:
		A list of CustomerMessageData objects
		"""
		_result = []
		for i in range( count ): #  range(1)=0 range(2)=0,1
			el = self.__prestashop.get( 'customer_messages', fromId-i )
			customermessage = CustomerMessageData( self )
			customermessage.load_from_xml( el )
			_result.append( customermessage )
		return _result

	def get_customer( self, id ):
		""" Retreive the customer from the id

		:param id: customer id (int) to retreive the customer information

		Returns:
		A customer object
		"""
		if not( isinstance( id, int )):
			raise ValueError( 'id must be integer' )
		logging.debug( 'read id_customer: %s ' % id )
		el = self.__prestashop.get( 'customers', id )
		customer = CustomerData( self )
		customer.load_from_xml( el )
		return customer

	def get_customerthread( self, id ):
		""" Retreive the custom thread data from thread id

		id(int) - id_customer_thread which is mentionned into a customer message.

		Returns:
		A CustomerThreadData object
		"""
		if not(isinstance( id, int )):
			raise EValueError( 'id must be integer' )

		logging.debug( 'read id_customer_thread: %s ' % id )
		el = self.__prestashop.get( 'customer_threads', id )
		customerthread = CustomerThreadData( self )
		customerthread.load_from_xml( el )
		return customerthread

	def get_countries( self ):
		""" Retreive a list of Countries (CountryData) from prestashop """
		logging.debug( 'read countries' )
		el = self.__prestashop.search( 'countries', options = {'display':'[id,iso_code,active,name]'} )
		_result = CountryList( self )
		# save_to_file('countries', el )
		_result.load_from_xml( el )
		return _result

	def get_taxes( self ):
		logging.debug( 'read taxes' )
		el = self.__prestashop.search( 'taxes', options = {'display':'[id,active,rate]'} )
		_result = TaxList( self )
		# save_to_file('taxes', el )
		_result.load_from_xml( el )
		return _result

	def get_tax_rules( self ):
		logging.debug( 'read tax rules' )
		el = self.__prestashop.search( 'tax_rules', options = {'display':'[id,id_country,id_tax,id_tax_rules_group]'} )
		_result = TaxRuleList( self )
		# save_to_file('tax_rules', el )
		_result.load_from_xml( el )
		return _result

	def get_tax_rule_groups( self ):
		logging.debug( 'read tax rule groups' )
		el = self.__prestashop.search( 'tax_rule_groups', options = {'display':'[id,active,name]'} )

		_result = TaxRuleGroupList( self )
		# save_to_file('tax_rule_groups', el )
		_result.load_from_xml( el )
		return _result

	def get_tax_rate( self, id_tax_rule_group, country_iso ):
		""" Products does not have Tax_id but Tax_Rule_Group + Country for which we do need it. """
		# Optimize: if already search and found -> Return it qwickly

		country = self.countries.country_from_iso_code( country_iso )
		if country==None:
			raise Exception('get_tax_rate: no country for iso_code=%s' % (country_iso) )
		id_country = country.id

		tax_rule_group = self.tax_rules.taxrule_for_country( id_tax_rule_group, id_country )
		if tax_rule_group == None:
			raise Exception('get_tax_rate: no tax_rule_group for id_tax_rule_group=%i, id_country=%i' % (id_tax_rule_group, id_country))
		id_tax = tax_rule_group.id_tax

		tax = self.taxes.tax_from_id( id_tax )
		if tax == None:
			raise Exception('get_tax_rate: no tax record for id_tax=%i' % (id_tax))
		return tax.rate # 6.000 or 21.000 percent

	def get_carriers( self ):
		""" Retreive a list of Carriers (CarrierData) from prestashop """
		logging.debug( 'read carriers' )
		el = self.__prestashop.search( 'carriers', options = {'display':'[id,deleted,active,name]'} )

		_result = CarrierList( self )
		_result.load_from_xml( el )

		return _result

	def get_products( self ):
		""" retreive a list of products from PrestaShop """
		# combinations are used to create the various "declinaisons" of a single product
		logging.debug( 'read combinations' )
		el = self.__prestashop.search( 'combinations', options = {'display' : '[id,id_product,reference, ean13,wholesale_price,price,weight]' } )
		_combinations = CombinationList( self )
		#save_to_file( 'get_products_combinations', el )
		_combinations.load_from_xml( el )

		logging.debug( 'read products' )
		#el = self.__prestashop.search( 'products' )
		#print( ElementTree.tostring( el ) )

		el = self.__prestashop.search( 'products', options = {'display': '[id,reference,active,name,price,wholesale_price,id_supplier,id_category_default,advanced_stock_management,available_for_order,ean13,weight,id_tax_rules_group]'} )
		#print( ElementTree.tostring( el ) )

		_result = BaseProductList( self, _combinations if len(_combinations)>0 else None )
		_result.load_from_xml( el )

		return _result

	def get_suppliers( self ):
		""" retreive the list of suppliers """
		logging.debug('read suppliers')
		el = self.__prestashop.search( 'suppliers', options = {'display': '[id,active,name]'} )

		_result = SupplierList( self )
		_result.load_from_xml( el )

		return _result

	def get_product_suppliers( self ):
		""" retreive the list of all the supplier for all the products """
		logging.debug('read product suppliers')
		el = self.__prestashop.search( 'product_suppliers', options = {'display': '[id,id_product,id_supplier,id_product_attribute,product_supplier_reference]'} )

		_result = ProductSupplierList( self )
		_result.load_from_xml( el )
		#save_to_file( "get_product_suppliers", el )

		return _result

	def get_languages( self ):
		""" retreive the list of languages """
		logging.debug('read languages')
		el = self.__prestashop.search( 'languages', options = {'display': '[id,name,iso_code,language_code,active]'}  )
		# also: is_rtl, date_format_lite, date_format_full
		_result = LanguageList( self )
		_result.load_from_xml( el )

	def get_order_states( self ):
		""" Retreive the list of Order States (OrderStateDate) from prestashop """
		logging.debug( 'read order states' )
		el = self.__prestashop.search( 'order_states', options = {'display':'[id,unremovable,send_email,invoice,shipped,paid,deleted,name]'} )

		#print( ElementTree.tostring( el ) )
		_result = OrderStateList( self )
		_result.load_from_xml( el )

		return _result

	def get_lastorder_id( self ):
		""" retreive the last order ID stored in PrestaShop """
		el = self.__prestashop.search( 'orders', options={'limit':1, 'sort' : 'id_DESC'} )
		item = etree_to_dict( el )
		return int( item['prestashop']['orders']['order']['@id'] )

	def get_order_ids( self, order_state_filter, limit = 25 ):
		""" Retreive a list of Order ID stored in prestashop for a given
			status. Start from the highest ID in the database with
			a max of limit rows loaded via the API"""
		# Since PrestaShop 1.6, current_state is no more filterable (returns an Error 400 bad request)
		#   So filter must be applied by code!
		#
		# el = self.__prestashop.search( 'orders', options={'limit':limit, 'sort' : 'id_DESC', 'display':'[id,current_state]', 'filter[current_state]': '[%i]' % order_state_filter } )
		el = self.__prestashop.search( 'orders', options={'limit':limit, 'sort' : 'id_DESC', 'display':'[id,current_state]' } )

		items = etree_to_dict( el )

		# print( items )
		# Si aucune entrée due au filtrage (oui cela arrive)
		if isinstance( items['prestashop']['orders'], str ):
		  return []

		# Si une seule entrée --> transformer l'unique dictionnaire en liste
		order_list = items['prestashop']['orders']['order']
		if isinstance( order_list, dict ):
			order_list = [ order_list ]

		# print( order_list )
		_result = []
		for order in order_list:
			if (order_state_filter == None) or (int(order['current_state']['#text']) == order_state_filter):
				_result.append( int(order['id']) )

		return _result


	def get_last_orders( self, fromId, count=1 ):
		""" Retreive the last orders stored in PrestaShop

		Args:
		fromId - ID from the last order  (see get_lastorder_id)
		count  - (default=1) the number of orders to retreive fromId (counting down)

		Returns:
		A list of OrderData objects or PrestaShopWebServiceError exception in case of empty content
		"""
		_result = []
		try:
			for i in range( count ): #  range(1)=0 range(2)=0,1
				el = self.__prestashop.get( 'orders', fromId-i )
				# print( ElementTree.tostring( el ) )
				order = OrderData( self )
				order.load_from_xml( el )
				_result.append( order )
		except PrestaShopWebServiceError as e:
			if 'response is empty' in str(e): # Order ID is certainly out of range
				pass # ignore error and return empty list
			else:
				raise
		return _result

	def get_order_data( self, id ):
		""" retreive the xml data for an order.

		:returns: ElementTree with order content """
		try:
			return self.__prestashop.get( 'orders', id )
		except PrestaShopWebServiceError as e:
			if 'HTTP response is empty' in str(e):
				return None # The given ID does not match an order!
			else:
				raise e

	def post_order_data( self, el ):
		""" Post a modified xml data of an order.
		:returns:  ElementTree with order content """
		return self.__prestashop.edit( 'orders', ElementTree.tostring( el ) )

	def get_outofstock_orderable_ids( self ):
		""" Locate the product IDs where advanced stock management is
			improperly defined. Accepting OutOfStock ordering """

		# out_of_stock = 1 -> Accept "out of stock" order
		el = self.__prestashop.search( 'stock_availables' , options={ 'display':'[id, id_product]', 'filter[out_of_stock]': '[1]' } )
		items = etree_to_dict( el )
		# print( items )
		# Si aucune entrée due au filtrage (oui cela arrive)
		if isinstance( items['prestashop']['stock_availables'], str ):
		  return []

		# Si une seule entrée --> transformer l'unique dictionnaire en liste
		stock_list = items['prestashop']['stock_availables']['stock_available']
		if isinstance( stock_list, dict ):
			stock_list = [ stock_list ]

		# print( stock_list )
		_result = []
		for stock in stock_list:
			_result.append( int(stock['id_product']['#text']) )
		return _result

	def get_unsynch_stock_qty_ids( self ):
		""" Locate the product IDs where advanced stock management is
			improperly defined. Having theyr qty not in synch with
			the Advanced Stock Management """

		# depends_on_stock = 0 -> gestion manuelle des quantités
		el = self.__prestashop.search( 'stock_availables' , options={ 'display':'[id, id_product]', 'filter[depends_on_stock]': '[0]' } )
		items = etree_to_dict( el )
		# print( items )
		# Si aucune entrée due au filtrage (oui cela arrive)
		if isinstance( items['prestashop']['stock_availables'], str ):
		  return []

		# Si une seule entrée --> transformer l'unique dictionnaire en liste
		stock_list = items['prestashop']['stock_availables']['stock_available']
		if isinstance( stock_list, dict ):
			stock_list = [ stock_list ]

		# print( stock_list )
		_result = []
		for stock in stock_list:
			_result.append( int(stock['id_product']['#text']) )
		return _result

	def get_stockavailables( self ):
		""" retreive the list of stock availables from PrestaShop """
		el = self.__prestashop.search( 'stock_availables' , options={ 'display':'[id, id_product,quantity,depends_on_stock,out_of_stock,id_product_attribute]' } )
		_result = StockAvailableList( self )
		_result.load_from_xml( el )

		return _result

	def get_categories( self ):
		""" Load the product categories """
		el = self.__prestashop.search( 'categories', options={ 'display':'[id,name,active,level_depth,is_root_category]' } )
		_result = CategoryList( self )
		_result.load_from_xml( el )

		return _result

class PrestaProgressEvent( object ):
	""" Content the data for Progress Callback.
	Used by CachedPrestaHelper """
	def __init__( self, current_step, max_step, msg ):
		self.current_step = current_step
		self.max_step = max_step
		self.msg = msg

	@property
	def is_finished( self ):
		""" Use this to know if you have to close the Progress bar """
		return (self.current_step < 0) or (self.current_step > self.max_step)

	def set_finished( self ):
		""" A progress Bar is finished when current step < 0 :-) """
		self.current_step = -1

class ProductSearchResultList( list ):

	def merge( self, psr_list ):
		"""  Merge the current list with the psr_list in paramter. Do not add twice the same id_product !

		:param psr_list: the PoructSearchResultList to merge in the current instance. """
		ids = [psr.product_data.id for psr in self]
		for item in psr_list:
			if not( item.product_data.id in ids ):
				self.append( item )

	def filter_out( self, filter_fn ):
		""" Remove from the this the items where the filter function returns False

		:param filter_fn: the filtering fonction receiving the ProductSearchResult in parameter and returning True/False """
		_todel = []
		for psr in self:
			if filter_fn( psr ):
				_todel.append( psr )
		for psr in _todel:
			self.remove( psr )

	def total_price_ordered( self ):
		""" Total price (without VAT) of the ordered stuff in the basket.

		return a tuple (sum_without_tax, sum_tax_included, sum_wholesale_price ) """
		sum_netto = 0
		sum_ttc   = 0
		sum_wholesale = 0

		for psr in self:
			if psr.ordered_qty:
				sum_netto += psr.ordered_qty * psr.product_data.price
				sum_ttc   += psr.ordered_qty * psr.product_data.price_ttc
				sum_wholesale += psr.ordered_qty * psr.product_data.wholesale_price

		return (sum_netto, sum_ttc, sum_wholesale)

class ProductSearchResult( object ):

	def __init__( self, product_data ):
		self._product_data = product_data
		self._product_suppliers = []
		self._qty = 0            # Qty in Stock
		self._ordered_qty = None # Optinal : an ordered quantity

	@property
	def product_data( self ):
		""" Product information

		:remarks: see id_supplier for default product supplier."""
		return self._product_data

	@property
	def qty(self):
		""" Stock Qty available for this quantity """
		return self._qty

	@qty.setter
	def qty(self, value):
	    self._qty = value

	@property
	def ordered_qty( self ):
		""" optional ordered quantity. None by default """
		return self._ordered_qty

	@ordered_qty.setter
	def ordered_qty( self, value ):
		self._ordered_qty = value

	@property
	def product_suppliers( self ):
		""" known suppliers for the product """
		return self._product_suppliers

	@property
	def supplier_refs( self ):
		""" Return a concatenated string of supplier refs """
		return ", ".join( [ps.reference for ps in self._product_suppliers] )

	def add_product_suppliers( self, product_suppliers ):
		self._product_suppliers += product_suppliers

class CachedPrestaHelper( PrestaHelper ):
	""" PrestaHelper class that permamently cache some useful information """
	CACHE_FILE_VERSION = 7
	CACHE_FILE_NAME    = 'cachefile.pkl'
	CACHE_FILE_DATETIME= None

	__carrier_list = None
	__country_list = None
	__tax_list     = None
	__tax_rule_list = None
	__tax_rule_group_list = None
	__order_state_list = None
	__product_list = None
	__supplier_list = None
	__category_list = None
	__stock_available_list = None
	__product_supplier_list = None

	def __init__( self, presta_api_url, presta_api_key, debug = __debug__, progressCallback = None  ):
		""" constructor with connection parameter to PrestaShop API.
		And loads cache data"""
		self.progressCallback = progressCallback

		# Initializing
		self.fireProgress( 1, 1, 'Connecting WebShop...' )
		PrestaHelper.__init__( self, presta_api_url, presta_api_key, debug )

		# Loading cache
		if os.path.isfile( self.CACHE_FILE_NAME ):
			if not(self.load_from_cache_file()):
				self.load_from_webshop()
		else:
			self.load_from_webshop()


	def load_from_webshop( self ):
		""" Load the cache with data cominf from the WebShop """
		logging.info( 'Init cache from WebShop' )
		__MAX_STEP = 11

		self.fireProgress( 1, __MAX_STEP, 'Caching Carriers...' )
		self.__carrier_list = self.get_carriers()
		self.fireProgress( 2, __MAX_STEP, 'Caching Order states...' )
		self.__order_state_list = self.get_order_states()
		self.fireProgress( 3, __MAX_STEP, 'Caching Products...' )
		self.__product_list = self.get_products()
		self.fireProgress( 4, __MAX_STEP, 'Caching Suppliers...' )
		self.__supplier_list = self.get_suppliers()
		self.fireProgress( 5, __MAX_STEP, 'Caching Categories...' )
		self.__category_list = self.get_categories()
		self.fireProgress( 6, __MAX_STEP, 'Caching Stock Availables...' )
		self.__stock_available_list = self.get_stockavailables()
		self.fireProgress( 7, __MAX_STEP, 'Caching Product Suppliers...' )
		self.__product_supplier_list = self.get_product_suppliers()
		self.fireProgress( 8, __MAX_STEP, 'Caching Countries...' )
		self.__country_list = self.get_countries()
		self.fireProgress( 9, __MAX_STEP, 'Caching Taxes...' )
		self.__tax_list = self.get_taxes()
		self.fireProgress( 10, __MAX_STEP, 'Caching Tax Rules...' )
		self.__tax_rule_list = self.get_tax_rules()
		self.fireProgress( 11, __MAX_STEP, 'Caching Tax Rule Groups...' )
		self.__tax_rule_group_list = self.get_tax_rule_groups()

		# Languages are not pickled yet
		# self.fireProgress( 8, __MAX_STEP, 'Caching languages...' )
		# self.__language_list = self.get_languages()

		# Closing progress
		self.fireProgress( -1, __MAX_STEP, 'Done' ) # -1 for hidding

	def load_from_cache_file( self ):
		""" Reload the data from the persistant local file

			Returns:
				true if proprety loaded otherwise false
		"""
		saved_version = -1
		fh = open( self.CACHE_FILE_NAME, 'rb' )
		try:
			self.fireProgress( 1, 1, 'Reload cache from %s' % self.CACHE_FILE_NAME )
			logging.info( 'Reload cache from %s' % self.CACHE_FILE_NAME )

			saved_version = pickle.load( fh )
			if saved_version != self.CACHE_FILE_VERSION:
				logging.warning( 'Reload cache from %s failed. File version %i, expected version %i.' % (self.CACHE_FILE_NAME, saved_version, self.CACHE_FILE_VERSION ) )
				return False
			self.CACHE_FILE_DATETIME = pickle.load( fh )
			logging.info( 'Cache date %s' % self.CACHE_FILE_DATETIME.strftime("%Y-%m-%d %H:%M:%S") )
			self.__carrier_list = CarrierList( self )
			self.__carrier_list.unpickle_data( fh )
			self.__order_state_list = OrderStateList( self )
			self.__order_state_list.unpickle_data( fh )
			self.__product_list = BaseProductList( self )
			self.__product_list.unpickle_data( fh )
			self.__supplier_list = SupplierList( self )
			self.__supplier_list.unpickle_data( fh )
			self.__category_list = CategoryList( self )
			self.__category_list.unpickle_data( fh )
			self.__stock_available_list = StockAvailableList( self )
			self.__stock_available_list.unpickle_data( fh )
			self.__product_supplier_list = ProductSupplierList( self )
			self.__product_supplier_list.unpickle_data( fh )
			self.__country_list = CountryList( self )
			self.__country_list.unpickle_data( fh )
			self.__tax_list = TaxList( self )
			self.__tax_list.unpickle_data( fh )
			self.__tax_rule_list = TaxRuleList( self )
			self.__tax_rule_list.unpickle_data( fh )
			self.__tax_rule_group_list = TaxRuleList( self )
			self.__tax_rule_group_list.unpickle_data( fh )

			return True
		except StandardError, error:
			 logging.error( 'Reload cache from %s failed due to exception' % self.CACHE_FILE_NAME )
			 logging.exception( error )
			 return False
		finally:
			fh.close()

	def save_cache_file(self):
		""" Save the cached data to a persistant local file """
		fh = open( self.CACHE_FILE_NAME, 'wb' )
		now = datetime.now()
		try:
			logging.info( 'Save cache to file %s' % self.CACHE_FILE_NAME )
			pickle.dump( self.CACHE_FILE_VERSION, fh )
			pickle.dump( now, fh )
			self.__carrier_list.pickle_data( fh )
			self.__order_state_list.pickle_data( fh )
			self.__product_list.pickle_data( fh )
			self.__supplier_list.pickle_data( fh )
			self.__category_list.pickle_data( fh )
			self.__stock_available_list.pickle_data( fh )
			self.__product_supplier_list.pickle_data( fh )
			self.__country_list.pickle_data( fh )
			self.__tax_list.pickle_data( fh )
			self.__tax_rule_list.pickle_data( fh )
			self.__tax_rule_group_list.pickle_data( fh )
		finally:
			fh.close()

	def refresh_stock( self ):
		""" Reload the stock availables """
		self.__stock_available_list.update_quantities()

	def fireProgress( self, currentStep, maxStep, message ):
		if self.progressCallback == None:
			return
		# Prepare data
		e = PrestaProgressEvent( currentStep, maxStep, message )
		# fire event
		self.progressCallback( e )

	def __update_search_product_qty( self, _list ):
		""" Browse the _list  and update the quantity for the article

		   :param _list: list of ProductSearchResult to be updated """
		for psr in _list:
			_sa = self.stock_availables.stockavailable_from_id_product( psr.product_data.id )
			if _sa:
				psr.qty = _sa.quantity
			else:
				psr.qty = -999

	def psr_instance( self, product ):
		""" HELPER: create a ProductSearchResult instance for a given product and initialize
		    all dependencies as supplier references and current stock quantity """
		_psr = ProductSearchResult( product )
		_psr.add_product_suppliers( self.__product_supplier_list.suppliers_for_id_product( product.id ) )
		self.__update_search_product_qty( [_psr] )
		return _psr

	def search_products_from_partialref(  self, sPartialRef, include_inactives = False ):
		""" Find an active product from a partial reference """
		_products = self.__product_list.search_products_from_partialref( sPartialRef, include_inactives )
		_result = ProductSearchResultList()
		for product in _products:
			psr = ProductSearchResult( product )
			psr.add_product_suppliers( self.__product_supplier_list.suppliers_for_id_product( product.id ) )
			_result.append( psr )
		self.__update_search_product_qty( _result )
		return _result

	def search_products_from_label(  self, sPartial, include_inactives = False ):
		""" Find an active product from a partial label """
		_products = self.__product_list.search_products_from_label( sPartial, include_inactives )
		_result = ProductSearchResultList()
		for product in _products:
			psr = ProductSearchResult( product )
			psr.add_product_suppliers( self.__product_supplier_list.suppliers_for_id_product( product.id ) )
			_result.append( psr )
		self.__update_search_product_qty( _result )
		return _result

	def search_products_from_supplier_ref( self, sPartialRef, include_inactives = False ):
		""" Find an active product having the mentionned supplier reference """
		product_suppliers = self.__product_supplier_list.search_for_partialref( sPartialRef )
		_result = ProductSearchResultList()
		for product_supplier in product_suppliers:
			_p = self.__product_list.product_from_id( product_supplier.id_product )
			if _p:
				psr=ProductSearchResult( _p )
				# Append only the supplier REF
				psr.product_suppliers.append( product_supplier )
				# Add also ALL supplier refs for the product (to get TariffCode & QM,QO)
				psr.add_product_suppliers( self.__product_supplier_list.suppliers_for_id_product( product_supplier.id_product ) )
				_result.append( psr )
		self.__update_search_product_qty( _result )
		return _result

	def search_products_from_supplier( self, id_supplier, include_inactives = False, filter = None ):
		""" Find products for a supplier.

		:param include_inactives: include inactive products in the selection.
		:param filter: apply a filter on product (as parameter) to select it (otherwise is select the product). """
		_products = self.__product_list.search_products_from_supplier( id_supplier, include_inactives )
		_result = ProductSearchResultList()
		for product in _products:
			# Filter
			if filter and not filter( product ):
				continue

			psr = ProductSearchResult( product )
			# find all supplier red anyway
			psr.add_product_suppliers( self.__product_supplier_list.suppliers_for_id_product( product.id ) )
			_result.append( psr )
		self.__update_search_product_qty( _result )
		return _result


	@property
	def carriers( self ):
		""" Return the carrier list """
		return self.__carrier_list

	@property
	def countries( self ):
		return self.__country_list

	@property
	def taxes( self ):
		return self.__tax_list

	@property
	def tax_rules( self ):
		return self.__tax_rule_list

	@property
	def tax_rule_groups( self ):
		return self.__tax_rule_group_list

	@property
	def order_states( self ):
		""" Return the Order_State list """
		return self.__order_state_list

	@property
	def products( self ):
		""" Return the product list """
		return self.__product_list

	@property
	def product_suppliers( self ):
		""" Return the product suppliers """
		return self.__product_supplier_list

	@property
	def suppliers( self ):
		""" Return the supplier list """
		return self.__supplier_list

	@property
	def categories( self ):
		""" Return the categories. Don't forget to reload quantities when needed """
		return self.__category_list

	@property
	def stock_availables( self ):
		""" Return the stock availables """
		return self.__stock_available_list

class BaseData( object ):
	""" Base class for data object... having a reference to the helper """
	__slots__ = [ "helper" ]

	def __init__( self, owner ):
		""" the owner is the PrestaHelper instance which create the
		data object
		"""
		self.helper = owner

	def load_from_xml( self, node ):
		""" Initialize the object from an XML node returned by the
		prestaShop WebService
		"""
		pass


class BaseDataList( list ):
	""" Base class to register list of BaseData object """
	__slots__ = [ "helper" ]

	def __init__( self, owner ):
		""" the owner is the PrestaHelper instance which create the
			data objects )
		"""
		self.helper = owner

	def add_data_object( self, aBaseData ):
		""" Register a BaseData chilphotoen into the list """
		self.append( aBaseData )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		pickle.dump( list(self), fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		# Load the list of data
		aList = pickle.load( fh )
		for item in aList:
			# reassign the helper
			item.helper = self.helper
			# register to the list
			self.add_data_object( item )

class LanguageData( BaseData ):
	""" Contains a langage definition """
	__slots__ = [ "id", "name", "iso_code", "language_code", "active" ]

	def load_from_xml( self, node ):
		items = etree_to_dict( node )
		lng = items['prestashop']['language']
		self.id       = int( lng['id'] )          # 1, 2, 8
		self.name     = lng['name']
		self.iso_code = lng['iso_code']           # en, fr, nl
		self.language_code = lng['language_code'] # en-us, fr-fr, nl-nl
		self.active   = int( lng['active'] )

class LanguageList( BaseDataList ):
	""" List of Languages """

	def load_from_xml( self, node ):
		""" Load the language list with data comming from prestashop search.
			Must contains nodes: id, name """

		items = etree_to_dict( node )
		items = items['prestashop']['languages']['language']
		for item in items:
			_data = LanguageData( self.helper )
			_data.id       = int( item['id'] )
			_data.name     = item['name']
			_data.iso_code = item['iso_code']
			_data.language_code = item['language_code'] # en-us
			_data.active   = int( item['active'] )

			self.append( _data )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )


	def language_from_id( self, Id ):
		""" Return the LanguageData object from Language ID """
		for item in self:
			if item.id == Id:
				return item
		return None

	def language_from_iso_code( self, iso_code ):
		""" Return the LanguageData object from Language iso_code (en, fr, nl) """
		iso_code = iso_code.lower()
		for item in self:
			if item.iso_code == iso_code:
				return item
		return None

	def name_from_id( self, Id ):
		""" Return the LanguageData.name from the Language ID """
		_language_data = self.language_from_id( Id )
		if language_data == None:
			return ''
		return _language_data.name

class OrderRowData( BaseData ):
	""" Details of rows in the order.

		Remarks: this class is instanciated by OrderData.load_from_xml() """
	__slots__ = ["id", "id_product", "ordered_qty", "reference", "unit_price_ttc", "unit_price", "ean13" ]

	def load_from_items( self, dic ):
		# dic is a dictionnary with key=value pairs
		def _extract( dic, key ):
			if key in dic:
				value = dic[key]
				return value
			return None

		self.id = _extract(dic,"id")
		self.id_product = _extract(dic,"product_id")
		# Is this a Combination product ?
		if ("product_attribute_id" in dic) and (dic['product_attribute_id'] != '0'):
			self.id_product = recompute_id_product( int(self.id_product), int(dic['product_attribute_id']))
		self.ordered_qty = int( _extract(dic,"product_quantity") )
		self.reference   = _extract(dic,"product_reference")
		self.unit_price_ttc = float( _extract(dic,"unit_price_tax_incl") ) # TTC
		self.unit_price     = float( _extract(dic,"unit_price_tax_excl") ) # HTVA
		self.ean13			= _extract(dic,"product_ean13")

	def __repr__( self ):
		return "%4s x %-30s (%5s) @ %7.2f htva/p" % ( self.ordered_qty, self.reference, self.id_product, self.unit_price )

class OrderData( BaseData ):
	""" Contains the data of an order.

	This class is supposed to extend with time """

	__slots__ = ["id", "id_customer", "id_carrier", "current_state", "valid", "payment", "total_paid_tax_excl", "total_paid", "shipping_number", "id_shop", "id_lang", "date_add", "date_upd", "rows"]

	def load_from_xml( self, node ):
		""" Initialise the data of an Order """
		#print( ElementTree.tostring( node ) )
		items = etree_to_dict( node )
		order = items['prestashop']['order']

		# print( order )
		self.id            = int( order['id'] )
		self.date_add      = order['date_add'] # Date when the order was placed
		self.date_upd      = order['date_upd'] # Date when the order was last updated
		self.id_customer   = int( order['id_customer']['#text'] )
		self.id_carrier    = int( order['id_carrier']['#text'] )
		self.current_state = int( order['current_state']['#text'] )
		self.valid         = int( order['valid'] )
		self.payment       = order['payment']
		self.total_paid_tax_excl = float( order['total_paid_tax_excl' ] )
		self.total_paid          = float( order['total_paid' ] )
		if isinstance( order['shipping_number'], dict ) and ('#text' in order['shipping_number']) :
			self.shipping_number = order['shipping_number']['#text']
		else:
			self.shipping_number = ''
		self.id_shop			 = int( order['id_shop'] )
		self.id_lang			 = int( order['id_lang']['#text'] )
		self.rows				 = []
		_rows = order['associations']['order_rows']['order_row']
		if isinstance( _rows, dict ): # @ PrestaShop they drop the list of rows if there is only one row in the order!!!
			_rows = [ _rows ]
		for items in _rows : # For each row (entry in the list) --> Load row details
			# Items is a list of node values
			_row = OrderRowData( self.helper )
			_row.load_from_items( items )
			self.rows.append( _row )

class CustomerMessageData( BaseData ):
	""" Contains the data of a customer messsgae """

	__slots__ = ["id", "id_employee", "id_customer_thread", "message", "date_add", "read" ]

	def load_from_xml( self, node ):
		""" Initialize object from customer_message node """
		item = etree_to_dict( node )
		self.id = int( item['prestashop']['customer_message']['id'] )
		if isinstance( item['prestashop']['customer_message']['id_employee'] , dict ):
			self.id_employee = int( item['prestashop']['customer_message']['id_employee']['#text'] )
		else:
			self.id_employee = PRESTA_UNDEFINE_INT
		if isinstance( item['prestashop']['customer_message']['id_customer_thread'], dict ):
			self.id_customer_thread = int( item['prestashop']['customer_message']['id_customer_thread']['#text'] )
		else:
			self.id_customer_thread = PRESTA_UNDEFINE_INT
		self.message = item['prestashop']['customer_message']['message']
		self.date_add = item['prestashop']['customer_message']['date_add']
		self.read = item['prestashop']['customer_message']['read']

	def get_customerthread( self ):
		""" request the CustomerThreadData via the helper.
		Will provide access to customer information """
		if not isinstance( self.id_customer_thread, int ):
			return PRESTA_UNDEFINE_INT
		return self.helper.get_customerthread( int( self.id_customer_thread ) )

class CustomerThreadData( BaseData ):
	""" Contains the customer Thread data + list of linked message IDs """
	__slots__ = ["id", "id_customer", "id_order", "id_contact", "email", "status", "date_add", "date_upd", "customer_message_ids" ]

	def load_from_xml( self, node ):
		""" Initialize object from customer_thread node """
		self.customer_message_ids = []
		item = etree_to_dict( node )
		self.id = int( item['prestashop']['customer_thread']['id'] )
		if isinstance( item['prestashop']['customer_thread']['id_customer'], dict ):
			self.id_customer = int( item['prestashop']['customer_thread']['id_customer']['#text'] )
		else:
			self.id_customer = PRESTA_UNDEFINE_INT
		if isinstance( item['prestashop']['customer_thread']['id_order'], dict ):
			self.id_order = int( item['prestashop']['customer_thread']['id_order']['#text'] )
		else:
			self.id_order = PRESTA_UNDEFINE_INT
		if isinstance( item['prestashop']['customer_thread']['id_contact'], dict ):
			self.id_contact = int( item['prestashop']['customer_thread']['id_contact']['#text'] )
		else:
			self.id_contact = PRESTA_UNDEFINE_INT
		self.email = item['prestashop']['customer_thread']['email']
		self.status = item['prestashop']['customer_thread']['status']
		self.date_add = item['prestashop']['customer_thread']['date_add']
		self.date_upd = item['prestashop']['customer_thread']['date_upd']

		# --- List the messages ID ---
		customer_messages_list = item['prestashop']['customer_thread']['associations']['customer_messages']
		# Si une seule entrée --> transformer l'unique dictionnaire en liste
		customer_messages_list = customer_messages_list [ 'customer_message' ]
		if isinstance( customer_messages_list, dict ):
			customer_messages_list = [ customer_messages_list ]
		for i in range( len( customer_messages_list ) ):
			self.customer_message_ids.append( int( customer_messages_list[i]['id'] ) )

	def get_customermessages( self ):
		""" Retreive a list of CustomerMessageData corresponding to the
			list of message IDs in the list """
		_result = []
		for messageid in self.customer_message_ids:
			# only keeps the first item of the list returned by get_lastcustomermessages
			_result.append( self.helper.get_lastcustomermessages( messageid )[0] )
		return _result

class CustomerData( BaseData ):
	""" Contains the Customer dada """
	__slots__ = ["id", "lastname", "firstname", "email", "id_gender", "id_lang", "note" ]

	def load_from_xml( self, node ):
		# print( ElementTree.tostring( node ) )
		items = etree_to_dict( node )
		items = items['prestashop']['customer']

		self.id        = items['id']
		self.lastname  = items['lastname']
		self.firstname = items['firstname']
		self.email     = items['email']
		self.id_gender = items['id_gender']
		self.id_lang   = items['id_lang']['#text']
		self.note    = items['note' ]

	@property
	def customer_name( self ):
		return "%s %s" % (self.lastname, self.firstname)


class CarrierData( BaseData ):
	""" Contains the Carriers data """
	__slots__ = ["id", "deleted", "active", "name" ]

	def load_from_xml( self, node ):
		""" properties initialized directly from the CarrierList """
		pass

	def __getstate__(self):
		""" return the current state of the object for pickeling """
		return {'id':self.id, 'deleted':self.deleted, 'active':self.active, 'name':self.name }

	def __setstate__(self, dic ):
		""" set the current state of object from dic parameter """
		self.id = dic['id']
		self.deleted = dic['deleted']
		self.active  = dic['active' ]
		self.name    = dic['name' ]


class CarrierList( BaseDataList ):
	""" List of Carriers """

	# used to store inactive and deleted carrier objects
	deletedlist = []
	inactivelist = []

	def load_from_xml( self, node ):
		""" Load the Carrier list with data comming from prestashop search.
			Must contains nodes: id, deleted, active, name """
		# clear the inner lists
		self.deletedlist = []
		self.inactivelist = []

		# reload the data
		items = etree_to_dict( node )
		items = items['prestashop']['carriers']['carrier']
		for item in items:
			_data = CarrierData( self.helper )
			_data.deleted = int( item['deleted'] )
			_data.active  = int( item['active'] )
			_data.id      = int( item['id'] )
			_data.name    = item['name']
			if _data.deleted == 1:
				self.deletedlist.append( _data )
			else:
				if _data.active == 0:
					self.inactivelist.append( _data )
				else:
					self.append( _data )

	def carrier_from_id( self, Id ):
		""" Return the CarrierData object from carrier ID """
		for item in self:
			if item.id == Id:
				return item
		for item in self.inactivelist:
			if item.id == Id:
				return item
		for item in self.deletedlist:
			if item.id == Id:
				return item
		return None

	def name_from_id( self, Id ):
		""" Return the CarrierData.name from the carrier ID """
		_carrier_data = self.carrier_from_id( Id )
		if _carrier_data == None:
			return ''
		return _carrier_data.name

class CountryData( BaseData ):
	""" Contains the Country Data """
	__slots__ = ["id", "iso_code", "active", "name" ] # id_zone not used

	def load_from_xml( self, node ):
		""" properties initialized directly from the CountryList """
		pass

	def __getstate__(self):
		""" return the current state of the object for pickeling """
		return {'id':self.id, 'iso_code':self.iso_code, 'active':self.active, 'name':self.name }

	def __setstate__(self, dic ):
		""" set the current state of object from dic parameter """
		self.id = dic['id']
		self.iso_code = dic['iso_code']
		self.active  = dic['active' ]
		self.name    = dic['name' ]


class CountryList( BaseDataList ):
	""" List of Countries """

	# used to store inactive and deleted carrier objects
	inactivelist = []

	def load_from_xml( self, node ):
		""" Load the Country list with data comming from prestashop search.
			Must contains nodes: id, iso_code, active, name """
		# clear the inner lists
		self.inactivelist = []

		# reload the data
		items = etree_to_dict( node )
		items = items['prestashop']['countries']['country']
		for item in items:
			_data = CountryData( self.helper )
			_data.active  = int( item['active'] )
			_data.id      = int( item['id'] )
			_data.name    = extract_hashtext( item['name'] ) # ['language']['#text']
			_data.iso_code= item['iso_code'].upper()
			if _data.active == 0:
				self.inactivelist.append( _data )
			else:
				self.append( _data )

	def country_from_id( self, Id ):
		""" Return the CountryData object from record ID """
		for item in self:
			if item.id == Id:
				return item
		for item in self.inactivelist:
			if item.id == Id:
				return item
		return None

	def country_from_iso_code( self, iso_code ):
		""" Return the CountryData object from record iso_code """
		iso_code = iso_code.upper()
		for item in self:
			if item.iso_code == iso_code:
				return item
		for item in self.inactivelist:
			if item.iso_code == iso_code:
				return item
		return None

class TaxData( BaseData ):
	""" Contains the Tax Data """
	__slots__ = ["id", "active", "rate" ] # id_zone not used

	def load_from_xml( self, node ):
		""" properties initialized directly from the TaxList """
		pass

	def __getstate__(self):
		""" return the current state of the object for pickeling """
		return {'id':self.id, 'active':self.active, 'rate':self.rate }

	def __setstate__(self, dic ):
		""" set the current state of object from dic parameter """
		self.id = dic['id']
		self.active  = dic['active' ]
		self.rate    = dic['rate' ]

class TaxList( BaseDataList ):
	""" List of Taxes """

	# used to store inactive and deleted carrier objects
	inactivelist = []

	def load_from_xml( self, node ):
		""" Load the Tax list with data comming from prestashop search.
			Must contains nodes: id, active, rate """
		# clear the inner lists
		self.inactivelist = []

		# reload the data
		items = etree_to_dict( node )
		items = items['prestashop']['taxes']['tax']
		for item in items:
			_data = TaxData( self.helper )
			_data.active  = int( item['active'] )
			_data.id      = int( item['id'] )
			_data.rate    = float( item['rate'] ) # ['language']['#text']
			if _data.active == 0:
				self.inactivelist.append( _data )
			else:
				self.append( _data )

	def tax_from_id( self, Id ):
		""" Return the TaxData object from record ID """
		for item in self:
			if item.id == Id:
				return item
		for item in self.inactivelist:
			if item.id == Id:
				return item
		return None

class TaxRuleData( BaseData ):
	""" Contains the Tax Data """
	__slots__ = ["id", "id_tax", "id_country", "id_tax_rules_group" ]

	def load_from_xml( self, node ):
		""" properties initialized directly from the TaxList """
		pass

	def __getstate__(self):
		""" return the current state of the object for pickeling """
		return {'id':self.id, 'id_tax':self.id_tax, 'id_country':self.id_country, 'id_tax_rules_group':self.id_tax_rules_group }

	def __setstate__(self, dic ):
		""" set the current state of object from dic parameter """
		self.id = dic['id']
		self.id_tax  = dic['id_tax' ]
		self.id_country = dic['id_country' ]
		self.id_tax_rules_group = dic['id_tax_rules_group' ]

class TaxRuleList( BaseDataList ):
	""" List of Taxes """

	def load_from_xml( self, node ):
		""" Load the Tax list with data comming from prestashop search.
			Must contains nodes: id, id_tax, id_country, id_tax_rules_group """
		# reload the data
		items = etree_to_dict( node )
		items = items['prestashop']['tax_rules']['tax_rule']
		for item in items:
			_data = TaxRuleData( self.helper )
			_data.id      = int( item['id'] )
			_data.id_tax  = int( item['id_tax'] )
			_data.id_country = int( item['id_country']['#text'] )
			_data.id_tax_rules_group = int( item['id_tax_rules_group']['#text'] )
			self.append( _data )

	def taxrule_from_id( self, Id ):
		""" Return the TaxRuleData object from record ID """
		for item in self:
			if item.id == Id:
				return item
		return None

	def taxrule_for_country( self, id_tax_rules_group, id_country ):
		for item in self:
			if (item.id_tax_rules_group == id_tax_rules_group) and (item.id_country == id_country):
				return item
		return None

class TaxRuleGroupData( BaseData ):
	""" Contains the Tax Data """
	__slots__ = ["id", "name", "active" ]

	def load_from_xml( self, node ):
		""" properties initialized directly from the TaxList """
		pass

	def __getstate__(self):
		""" return the current state of the object for pickeling """
		return {'id':self.id, 'name':self.name, 'active':self.active }

	def __setstate__(self, dic ):
		""" set the current state of object from dic parameter """
		self.id = dic['id']
		self.name  = dic['name' ]
		self.active = dic['active' ]

class TaxRuleGroupList( BaseDataList ):
	""" List of Taxes """
	inactivelist = []

	def load_from_xml( self, node ):
		""" Load the Tax list with data comming from prestashop search.
			Must contains nodes: id, active, name """
		# clear the inner lists
		self.inactivelist = []

		items = etree_to_dict( node )
		items = items['prestashop']['tax_rule_groups']['tax_rule_group']
		for item in items:
			_data = TaxRuleGroupData( self.helper )
			_data.id      = int( item['id'] )
			_data.active  = int( item['active'] )
			_data.name    = item['name']
			if _data.active == 0:
				self.inactivelist.append( _data )
			else:
				self.append( _data )


	def taxrulegroup_from_id( self, Id ):
		""" Return the TaxRuleGroupData object from record ID """
		for item in self:
			if item.id == Id:
				return item
		return None


class SupplierData( BaseData ):
	""" Contains the Supplier description data """
	__slots__ = ["id", "active", "name" ]

	def load_from_xml( self, node ):
		""" properties initialized directly from the SupplierList """
		pass

	def __getstate__(self):
		""" return state of the object for pickeling """
		return { "id" : self.id, "active" : self.active, "name": self.name }

	def __setstate__(self, dic):
		""" set the state of the object based on dictionary """
		self.id     = dic['id']
		self.active = dic['active']
		self.name   = dic['name']

class SupplierList( BaseDataList ):
	""" List of Suppliers """

	# used to store inactive supplier objects
	inactivelist = []

	def load_from_xml( self, node ):
		""" Load the supplier list with data comming from prestashop search.
			Must contains nodes: id, active, name """
		self.inactivelist = []

		items = etree_to_dict( node )
		items = items['prestashop']['suppliers']['supplier']
		for item in items:
			_data = SupplierData( self.helper )
			_data.active  = int( item['active'] )
			_data.id      = int( item['id'] )
			_data.name    = item['name']
			if _data.active == 0:
				self.inactivelist.append( _data )
			else:
				self.append( _data )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )
		pickle.dump( list(self.inactivelist), fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )

		# Load the deletedlist of data
		aList = pickle.load( fh )
		for item in aList:
			# reassign the helper
			item.helper = self.helper
			# register to the list
			self.inactivelist.append( item )

	def supplier_from_id( self, Id ):
		""" Return the SupplierData object from Supplier ID """
		for item in self:
			if item.id == Id:
				return item
		for item in self.inactivelist:
			if item.id == Id:
				return item
		return None

	def name_from_id( self, Id ):
		""" Return the SupplierData.name from the Supplier ID """
		_supplier_data = self.supplier_from_id( Id )
		if _supplier_data == None:
			return ''
		return _supplier_data.name

	def supplier_from_name( self, name ):
		""" Locate the supplier object for a given supplier name """
		for item in self:
			if item.name.upper() == name.upper():
				return item

		return None # Not find!

class ProductSupplierData( BaseData ):
	""" Contains the ProductSupplier description data """
	__slots__ = ["id", "id_product", "id_supplier", "reference" ]

	def load_from_xml( self, node ):
		""" properties initialized directly from the SupplierList """
		pass

	def __getstate__(self):
		""" return state of the object for pickeling """
		return { "id" : self.id, "id_product" : self.id_product, "id_supplier": self.id_supplier, "reference" : self.reference }

	def __setstate__(self, dic):
		""" set the state of the object based on dictionary """
		self.id          = dic['id']
		self.id_product  = dic['id_product']
		self.id_supplier = dic['id_supplier']
		self.reference   = dic['reference']

class ProductSupplierList( BaseDataList ):

	def load_from_xml( self, node ):
		""" Load the product_supplier list with data comming from prestashop search.
			Must contains nodes: id, id_product, id_supplier, product_supplier_reference """
		items = etree_to_dict( node )
		items = items['prestashop']['product_suppliers']['product_supplier']
		for item in items:
			_data = ProductSupplierData( self.helper )
			_data.id      = int( item['id'] )
			_data.id_product = int( item['id_product']['#text'] )
			# Is this a Combination product ?
			if item['id_product_attribute'] != '0' :
				_data.id_product = recompute_id_product( _data.id_product, int(item['id_product_attribute']['#text']))
				#print( 'store productsupplier for id= %s' % _data.id_product )
			_data.id_supplier = int( item['id_supplier']['#text'] )
			_data.reference   = item['product_supplier_reference']
			if _data.reference == None:
				_data.reference = ''
			if _data.id == 267800447:
				print( _data.reference )
			self.append( _data )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )

	def suppliers_for_id_product( self, id_product ):
		""" find all the records for a given product """
		result = []

		for item in self:
			if item.id_product == id_product:
				result.append( item )

		return result

	def reference_for( self, id_product, id_supplier ):
		""" Look for the reference on a specific supplier. if id_supplier
		is None then return the first reference found """
		result = self.suppliers_for_id_product( id_product )
		if len( result )==0:
			return ''

		# No supplier mentionned --> return the first reference
		if id_supplier == None:
			return result[0].reference

		for item in result:
			if item.id_supplier == id_supplier:
				return item.reference

		return '' # No reference found for the specified ID_Supplier

	def search_for_partialref( self, partialref ):
		""" Search (not case sensitive) for entries having the partielref in their reference.

		:param partialref: The partial reference to search for.
		:returns: list of ProductSupplier. """
		_result = []
		partialref = canonical_search_string( partialref )
		for item in self:
			if item.reference and  (partialref in canonical_search_string( item.reference )):
				_result.append( item )
		return _result


class CategoryData( BaseData ):
	""" Contains the Carriers data """
	__slots__ = ["id", "active", "level_depth", "is_root_category" ,"name" ]

	def load_from_xml( self, node ):
		""" properties initialized directly from the CarrierList """
		pass

	def __getstate__(self):
		""" Get tke object state for pickeling """
		return {"id": self.id, "active":self.active, "level_depth":self.level_depth, "is_root_category":self.is_root_category ,"name":self.name }

	def __setstate__(self, dic):
		""" Set the state of the object from pickeling """
		self.id          = dic['id']
		self.active      = dic['active']
		self.level_depth = dic['level_depth']
		self.is_root_category = dic['is_root_category']
		self.name        = dic['name']

class CategoryList( BaseDataList ):
	""" List of Carriers """

	# used to store inactive and deleted carrier objects
	inactivelist = []

	def load_from_xml( self, node ):
		""" Load the category list with data comming from prestashop search."""
		items = etree_to_dict( node )
		items = items['prestashop']['categories']['category']
		for item in items:
			_data = CategoryData( self.helper )
			_data.active  = int( item['active'] )
			_data.id      = int( item['id'] )
			_data.name    = extract_hashtext( item['name'] ) # ['language']['#text']
			_data.level_depth = int( item['level_depth'] )
			_data.is_root_category = int( item['is_root_category'] )
			if _data.active == 0:
				self.inactivelist.append( _data )
			else:
				self.append( _data )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )
		pickle.dump( list(self.inactivelist), fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )

		# Load the deletedlist of data
		aList = pickle.load( fh )
		for item in aList:
			# reassign the helper
			item.helper = self.helper
			# register to the list
			self.inactivelist.append( item )

	def category_from_id( self, Id ):
		""" Return the CategoryData object from category ID """
		for item in self:
			if item.id == Id:
				return item
		for item in self.inactivelist:
			if item.id == Id:
				return item
		return None

	def name_from_id( self, Id ):
		""" Return the CategoryData.name from the category ID """
		_category_data = self.category_from_id( Id )
		if _category_data == None:
			return ''
		return _category_data.name


class OrderStateData( BaseData ):
	""" Contains the the Order State Data """
	__slots__ = ["id","unremovable","send_email","invoice","shipped","paid","deleted","name"]

	def load_from_xml( self, node ):
		""" properties initialized directly from the OrderStateList """
		pass

	def __getstate__(self):
		""" return the current state for pickeling """
		return { "id": self.id ,"unremovable": self.unremovable ,"send_email" : self.send_email,"invoice": self.invoice ,"shipped" : self.shipped ,"paid":self.paid ,"deleted" : self.deleted,"name": self.name }

	def __setstate__(self, dic):
		""" reinitialise the state of the object """
		self.id         = dic['id']
		self.unremovable= dic['unremovable']
		self.send_email = dic['send_email']
		self.invoice    = dic['invoice']
		self.shipped    = dic['shipped']
		self.paid       = dic['paid']
		self.deleted    = dic['deleted']
		self.name       = dic['name']

class OrderStateList( BaseDataList ):
	""" List of Order State """

	# used to store deleted carrier objects
	deletedlist = []

	# PREDEFINED status in PrestaShop
	ORDER_STATE_WAIT_CHEQUE = 1
	ORDER_STATE_PAID		= 2 # Order is paid
	ORDER_STATE_PREPARING   = 3 # Preparing the order
	ORDER_STATE_SHIPPING    = 4 # Order is currently shipping toward the customer
	ORDER_STATE_SHIPPED     = 5 # Customer did received the order
	ORDER_STATE_CANCELLED   = 6 # Order has been cancelled
	ORDER_STATE_REPLENISH   = 9 # Order is paid BUT some items are out of stock. Stock must be replenished!
	ORDER_STATE_WAIT_BANKWIRE = 10 # Wait completion of Bankwire money transfert
	ORDER_STATE_WAIT_PAYPAL   = 11 # Wait completion of Paypal money transfert
	ORDER_STATE_PAYPAL_AUTH   = 12 # Autorisation acceptée par PayPal

	PAID_ORDER_STATES = [ ORDER_STATE_PAID, ORDER_STATE_PREPARING, ORDER_STATE_SHIPPING, ORDER_STATE_SHIPPED, ORDER_STATE_REPLENISH ]
	WAIT_PAYMENT_ORDER_STATES = [ ORDER_STATE_WAIT_CHEQUE, ORDER_STATE_WAIT_PAYPAL, ORDER_STATE_WAIT_BANKWIRE ]
	CARRIER_ORDER_STATES = [ ORDER_STATE_SHIPPING, ORDER_STATE_SHIPPED ] # States where the order is currently shipping or shipped

	def load_from_xml( self, node ):
		""" Load the Order State list with data comming from prestashop search.
			Must contains nodes: id, unremovable , send_email ,invoice , shipped , paid, deleted, name """
		items = etree_to_dict( node )
		items = items['prestashop']['order_states']['order_state']
		#print( items )
		for item in items:
			_data = OrderStateData( self.helper )
			_data.unremovable = int( item['unremovable'] )
			_data.send_email  = int( item['send_email'] )
			_data.invoice  	  = int( item['invoice'] )
			_data.shipped  	  = int( item['shipped'] )
			_data.paid        = int( item['paid'] )
			_data.deleted     = int( item['deleted'] )
			_data.id          = int( item['id'] )
			#print( item )
			_data.name        = extract_hashtext( item['name'] )
			if _data.deleted == 1:
				self.deletedlist.append( _data )
			else:
				self.append( _data )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )
		pickle.dump( list(self.deletedlist), fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )

		# Load the deletedlist of data
		aList = pickle.load( fh )
		for item in aList:
			# reassign the helper
			item.helper = self.helper
			# register to the list
			self.deletedlist.append( item )


	def order_state_from_id( self, Id ):
		""" Return the OrderStateData object from Order State ID """
		for item in self:
			if item.id == Id:
				return item
		for item in self.deletedlist:
			if item.id == Id:
				return item
		return None

	def name_from_id( self, Id ):
		""" Return the OrderStateData.name from the OrderState ID """
		_order_state_data = self.order_state_from_id( Id )
		if _order_state_data == None:
			return ''
		return _order_state_data.name

	def is_payment_waiting(self, order_state ):
		""" Check if the order_state is a payment pending status. Payment not yet done """
		return order_state in self.WAIT_PAYMENT_ORDER_STATES

	def is_paid( self, order_state ):
		""" Check if the order_state imply that the order has been paid """
		_state = self.order_state_from_id( order_state )
		return (_state != None) and (_state.paid == 1)

	def is_sent( self, order_state ):
		""" Check if the order_state is sent (or already received by) to
			the customer """
		return order_state in self.CARRIER_ORDER_STATES

	def is_new_order( self, order_state ):
		""" Check if the order is a new order that should be managed """
		return self.is_paid( order_state ) and (order_state != self.ORDER_STATE_PREPARING ) and not( self.is_sent( order_state ) )

	def is_open_order( self, order_state ):
		""" An open order is an order where the state requires some
			kind of user management (like preparing, boxing, shipping, etc) """
		return self.is_paid( order_state ) and not(self.is_sent( order_state ))

class CombinationData( BaseData ):
	""" Contains the Combination of a product... the various "colors" of a single product.
		Each having a reference or an ean13

	Fields:
		id(int) - ID of the combination
		id_product(int) - related product ID
		reference(str)  - reference of the product (ex:FEATHER-CASE-TFT-WHITE)
		ean13(str)      - ean13 if available

	Remarks: directly loaded from the CombinationList class"""

	__slots__ = ["id", "id_product", "reference", "ean13", "wholesale_price", "price"]

	def load_from_xml( self, node ):
		""" Initialise the data from a combination """
		pass

	def __getstate__(self):
		""" return the object state for pickeling """
		return {"id":self.id, "id_product" : self.id_product, "reference" : self.reference, "ean13" : self.ean13, "wholesale_price": self.wholesale_price, "price": self.price }

	def __setstate__(self,dic):
		""" Set the object state from unpickeling """
		self.id             = dic['id']
		self.id_product     = dic['id_product']
		self.reference      = dic['reference']
		self.ean13 			= dic['ean13']
		self.wholesale_price= dic['wholesale_price']
		self.price			= dic['price']

	def canonical_reference( self ):
		""" Return the canonical search string of the reference.
			Allow a better search algorithm """

		return canonical_search_string( self.reference )

class ProductData( BaseData ):
	""" Constains the data of an product.

	Fields:
		id(int) - ID of the product
		active(int) - 1/0 indicates if the product is currently active
					  inactive products are stored in a séparated list.
		reference(str) - reference of the product. Ex: ARDUINO-UNO
		name(str)      - Human redeable name for the product. Ex: Arduino Uno Rev 3.
		wholesale_price(float) - buying price (without tax)
		price(float)           - sale price (without tax)
		id_supplier(int)	   - ID of the supplier
		supplier_reference(str)- Reference of the product @ supplier.
		id_category_default(int)- default category of the product
		advanced_stock_management(int) - 1/0 for advanced stock management
		available_for_order(int)       - 1/0
		ean13(str)	            - ean13 value when available
		weight(float)           - Product weight in Kg
		id_tax_rules_group(int) - identification of the Rule taxe applying to the product

	Remarks: directly loaded from by the product list class """

	__slots__ = ["id", "active", "reference", "name", "wholesale_price", "price", "id_supplier", "id_category_default", "advanced_stock_management", "available_for_order", "ean13", "weight", "id_tax_rules_group","__vat_rate" ]

	def __init__( self, owner ):
		""" the owner is the PrestaHelper instance which create the
		data object
		"""
		super(ProductData,self).__init__(owner)
		self.__vat_rate = None # Can be set with update_vat_rate (6,21,20.5)

	def load_from_xml( self, node ):
		""" Initialise the data of an product """
		pass

	def __getstate__(self):
		""" Return the object state for pickeling """
		return { "id":self.id, "active":self.active, "reference":self.reference , "name":self.name, "wholesale_price": self.wholesale_price, "price": self.price, "id_supplier" : self.id_supplier, "id_category_default" : self.id_category_default , "advanced_stock_management" : self.advanced_stock_management, "available_for_order" : self.available_for_order, "ean13" : self.ean13, "weight" : self.weight, "id_tax_rules_group" : self.id_tax_rules_group }

	def __setstate__(self, dic):
		""" Set the object state from unpickeling """
		self.id                       = dic['id']
		self.active                   = dic['active']
		self.reference                = dic['reference']
		self.name                     = dic['name']
		self.wholesale_price          = dic['wholesale_price']
		self.price                    = dic['price']
		self.id_supplier              = dic['id_supplier']
		self.id_category_default      = dic['id_category_default']
		self.advanced_stock_management= dic['advanced_stock_management']
		self.available_for_order      = dic['available_for_order']
		if 'ean13' in dic:
			self.ean13				  = dic['ean13']
		else:
			self.ean13				  = ''
		self.weight					  = dic['weight']
		self.id_tax_rules_group		  = dic['id_tax_rules_group']

	def canonical_reference( self ):
		""" Return the canonical search string of the reference.
			Allow a better search algorithm """
		return canonical_search_string( self.reference )

	def update_vat_rate( self, vat_rate ):
		""" Set the VAT rate from external source (6,21,20.5) """
		self.__vat_rate = vat_rate

	@property
	def is_combination( self ):
		""" Conbination product does have an ID > =100000. Eg: 4501077 for FEATHER-CASE-PROTO-WHITE """
		return (self.id >= 100000)

	@property
	def is_IT( self ):
		""" Check if the product is an [IT] product """
		return '[IT]' in self.name

	@property
	def is_INTERNAL( self ):
		""" Check if the product is an [IT] product """
		return '[INTERNAL]' in self.name

	@property
	def price_ttc(self):
		""" Calculate the price TTC """
		rate = self.__vat_rate if self.__vat_rate else 21.0 # assume a default VAT rate
		return self.price * (1+(rate/100)) # (1.06 if 'BK-' in self.reference else 1.21)


class StockAvailableData( BaseData ):
	""" Contains the Stock_Available description data """
	__slots__ = ["id", "id_product", "depends_on_stock", "out_of_stock", "quantity" ,"id_product_attribute"]

	# How the WebShop should manage the product ordering when out of stock
	OUT_OF_STOCK_NO_ORDER = 0     # Refuse order when out of stock
	OUT_OF_STOCK_ACCEPT_ORDER = 1 # Accept the orders when out of stock
	OUT_OF_STOCK_DEFAULT = 2      # Default webshop config behaviour when out of stock

	DEPENDS_ON_STOCK_SYNCH  = 1 # Quantity is synch with advanced stock management
	DEPENDS_ON_STOCK_MANUAL = 0 # Manual management of quantities from product sheet.

	def load_from_xml( self, node ):
		""" properties initialized directly from the StockAvailableList """
		pass

	def __getstate__(self):
		""" return state of the object for pickeling """
		return { "id" : self.id, "id_product" : self.id_product, "depends_on_stock": self.depends_on_stock, "out_of_stock" : self.out_of_stock, "quantity" : self.quantity,
		 		 "id_product_attribute" : self.id_product_attribute }

	def __setstate__(self, dic):
		""" set the state of the object based on dictionary """
		self.id     		  = dic['id']
		self.id_product 	  = dic['id_product']
		self.depends_on_stock = dic['depends_on_stock']
		self.out_of_stock 	  = dic['out_of_stock']
		self.quantity 	  	  = dic['quantity']
		self.id_product_attribute = dic['id_product_attribute']

	def update_quantity( self ):
		""" Force the refresh of the quantity to have an UptToDate qty """
		if self.id == None:
			return None
		__helper = self.helper
		__el = __helper.search( 'stock_availables' , options={ 'display':'[id,quantity]', 'filter[id]': '[%i]' % self.id } )
		__items = etree_to_dict( __el )
		self.quantity = int( __items['prestashop']['stock_availables']['stock_available']['quantity'] )
		return self.quantity

class StockAvailableList( BaseDataList ):
	""" List of stock available

	Remarks:
	consider to use update_quantity() on childs to have a up-to-date
	view of the quantities """

	def load_from_xml( self, node ):
		""" Load the stock available list with data comming from prestashop search.
			Must contains nodes: id, id_product, ... """
		#save_to_file( 'StockAvailableList.load_from_xml', node)
		items = etree_to_dict( node )
		items = items['prestashop']['stock_availables']['stock_available']
		for item in items:
			# Sometime, the stock_available does not contains a valid ID_product
			if not( '#text' in item['id_product'] ):
				print( "stock_available: record id %s as invalid id_product %s" % (item['id'], item['id_product']) )
				continue

			_data = StockAvailableData( self.helper )
			_data.id               = int( item['id'] )
			_data.id_product       = int( item['id_product']['#text'] )
			_data.depends_on_stock = int( item['depends_on_stock'] )
			_data.out_of_stock     = int( item['out_of_stock' ] )
			_data.quantity         = int( item['quantity'] )
			if "#text" in item['id_product_attribute']:
				_data.id_product_attribute = int( item['id_product_attribute']['#text'] )
			else:
				_data.id_product_attribute = None
			# Use the Internal ID_Product_combination when it applies
			# 2 combinations for product 205!
			# 		62000205 : HARIB-GUIM-COCO-200GR
			#		62100205 : HARIB-GUIM-COCO-1KG
			if _data.id_product_attribute:
				_data.id_product = recompute_id_product( _data.id_product, _data.id_product_attribute )
			self.append( _data )

	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )

	def stockavailable_from_id( self, Id ):
		""" Return the StockAvailableData object from StockAvailable ID """
		for item in self:
			if item.id == Id:
				return item
		return None

	def stockavailable_from_id_product( self, Id ):
		""" Return the StockAvailableData from the product ID """
		for item in self:
			if item.id_product == Id:
				return item
		return None

	def update_quantities( self ):
		""" query the quantities and update the inner list """
		__el = self.helper.search( 'stock_availables', options={ 'display':'[id,quantity]' } )
		__items = etree_to_dict( __el )
		__items  = __items['prestashop']['stock_availables']['stock_available']
		for __item in __items:
			stock_id = int(__item['id'])
			stock_obj = self.stockavailable_from_id( stock_id )
			if stock_obj == None:
				# Quantity present for a product not available in the
				# cache! -> Database Newer than cache !!!
				logging.warning( 'update_quantities() for cache: stock_id %i not present in cache file. Database more recent than cache file.' % ( stock_id ) )
				logging.warning( '  +--> Refresh cache data with CachedPrestaHelper.load_from_webshop() ')
			else:
				stock_obj.quantity = int( __item['quantity'] )
		return

class CombinationList( BaseDataList ):
	""" List of product combination """

	def load_from_xml( self, node ):
		#save_to_file('CombinationList.load_from_xml', node) # Debug
		items = etree_to_dict( node )
		#print( items )
		items = items['prestashop']['combinations']['combination']
		for item in items:
			# Sometime, the combination does not contains a valid ID_product
			if not( '#text' in item['id_product'] ):
				print( "Combination: record id %s as invalid id_product %s" % (item['id'], item['id_product']) )
				continue
			# print( item )
			_data = CombinationData( self.helper )
			_data.id         = int( item['id'] )
			_data.id_product = int( item['id_product']['#text'] )
			_data.reference  = item['reference'] if item['reference']!= None else ''
			_data.ean13      = item['ean13'] if item['ean13']!=None else ''
			_data.wholesale_price = float( item['wholesale_price'] )
			if( item['price'] == None ):
				_data.price = 0
			else:
				_data.price           = float( item['price'] )
			# Auto-switch from EAN12 to EAN13
			# Damned PrestaShop accept EAN12 instead of ean13!?!?
			if len(_data.ean13) == 12:
				_data.ean13 = calculate_ean13( _data.ean13 )
			self.append( _data )

	def has_combination( self, id_product ):
		""" Check if it exists a combination for an id_product """
		for item in self:
			if item.id_product == id_product:
				return True
		return False

	def get_combinations( self, id_product ):
		""" Return the combinations for an id_product or None """
		_r = [item for item in self if item.id_product == id_product ]
		return None if len(_r)==0 else _r

	def recompute_id_product( self, id_product, id_combination ):
		return recompute_id_product( id_product, id_combination )

	def unmangle_id_product( self, computed_id_product ):
		return unmangle_id_product( computed_id_product )

def recompute_id_product( id_product, id_combination ):
	""" Compute an unique product ID named recompute_id_product based on (id_product, id_combination) """
	return id_combination*100000+id_product

def unmangle_id_product( computed_id_product ):
	""" Make the opposite of recompute_id_product. returns (id_product, id_combination) """
	id_combination = int(computed_id_product/100000)
	id_product     = computed_id_product - (id_combination*100000)
	return id_product, id_combination

def is_combination( id_product ):
	""" Check if the ID_product is a recompute_id_product """
	return (id_product >= 100000)

class BaseProductList( BaseDataList ):
	""" List of product. Base class that can be derivated """

	# used to store inactive objects
	inactivelist = []
	combinationlist = None

	def __init__( self, owner, combinationlist=None ):
		""" the owner is the PrestaHelper instance which create the
			data objects, the combinationlist may provided from previous load )
		"""
		super(BaseProductList,self).__init__(owner)
		self.combinationlist = combinationlist

	def load_from_xml( self, node ):
		""" Load the Product list with data comming from prestashop search.
			Must contains nodes: id, name, active, ... """

		def create_from_item( item ):
			""" Init a ProductData from item dictionnary """
			_data = ProductData( self.helper )
			_data.active   = int( item['active'] )
			_data.id       = int( item['id'] )
			_data.id_category_default = int( item['id_category_default']['#text'] )
			_data.available_for_order = int( item['available_for_order'] )
			_data.advanced_stock_management = int( item['advanced_stock_management'] )
			_data.name     = extract_hashtext( item['name'] ) # ['language']['#text']
			_data.reference= item['reference']
			_data.wholesale_price = float( item['wholesale_price'] )
			if isinstance( item['id_supplier'], str ): # Not a valid reference
				_data.id_supplier = PRESTA_UNDEFINE_INT
			else:
				_data.id_supplier     = float( item['id_supplier']['#text'] )
			if( item['price'] == None ):
				_data.price = 0
			else:
				_data.price           = float( item['price'] )
			if _data.active == 0:
				self.inactivelist.append( _data )
			else:
				self.append( _data )
			_data.ean13 = item['ean13'] if item['ean13']!=None else ''
			_data.weight = float(item['weight'])
			# id_tax_rules_group may be defined as follow:
			#   When assigned: <id_tax_rules_group xlink:href="https://www.bonbonz.be/api/tax_rule_groups/55">55</id_tax_rules_group>
			#   When UNASSIGNED: <id_tax_rules_group>0</id_tax_rules_group>
			if( type(item['id_tax_rules_group']) is dict ): # Some record may not have tax rules
				_data.id_tax_rules_group = int(item['id_tax_rules_group']['#text'])
			else:
				_data.id_tax_rules_group = 0 # id_tax_rules_group not assigned. Set it to 0 like PrestaShop does
				if _data.active == 1: # If product is active, this may be a problem
					print( 'Load product %i: %s. Invalid/Unassigned id_tax_rules_group!' % (_data.id,_data.reference) )
			return _data

		# empty the list previously loaded
		self.inactivelist = []
		#save_to_file( "BaseProductList.load_from_xml", node )
		items = etree_to_dict( node )
		#print( items )
		items = items['prestashop']['products']['product']
		for item in items:
			# print( item )
			id_product = int(item['id'])
			if not self.has_combination( id_product ):
				_data = create_from_item( item ) # create the object from dict of data.

				# Auto-switch from EAN12 to EAN13
				# Damned PrestaShop accept EAN12 instead of ean13!?!?
				if len(_data.ean13) == 12:
					_data.ean13 = calculate_ean13( _data.ean13 )
			else:
				# Product HAS COMBINATION --> so create a product entry for each item
				_combinations = self.get_combinations( id_product )
				for _combination in _combinations:
					_data = create_from_item( item )
					_data.reference = _combination.reference
					_data.ean13     = _combination.ean13
					_data.wholesale_price = _combination.wholesale_price
					_data.price 		  = _combination.price
					# recompute an unique id_product (1 for 99.999 products)
					_data.id        = self.combinationlist.recompute_id_product( _combination.id_product, _combination.id )


	def pickle_data( self, fh ):
		""" organize the pickeling of data

		Parameters:
			fh - file handler to dump the data
		"""
		BaseDataList.pickle_data( self, fh )
		# Save the inactive list
		pickle.dump( list(self.inactivelist), fh )
		# Save the combination list
		pickle.dump( True if self.combinationlist else False, fh )
		pickle.dump( list(self.combinationlist), fh )

	def unpickle_data( self, fh ):
		""" unpickeling the data

		Parameter:
			fh - file handler to read the data
		"""
		BaseDataList.unpickle_data( self, fh )

		# Load the deletedlist of data
		aList = pickle.load( fh )
		for item in aList:
			# reassign the helper
			item.helper = self.helper
			# register to the list
			self.inactivelist.append( item )

		# Load the combination list
		aBoolean = pickle.load( fh )
		if aBoolean:
			self.combinationlist = pickle.load( fh )
			for item in self.combinationlist:
				# reassign the helper
				item.helper = self.helper
		else:
			aBoolean.combinationlist = None

	def has_combination( self, id_product ):
		return self.combinationlist and self.combinationlist.has_combination( id_product )

	def get_combinations( self, id_product ):
		if not self.combinationlist:
			return None
		return self.combinationlist.get_combinations( id_product )


	def product_from_id( self, id_product, include_inactives = True ):
		""" Return the ProductData object from product ID """
		for item in self:
			if item.id == id_product:
				return item
		if include_inactives:
			for item in self.inactivelist:
				if item.id == id_product:
					return item
		return None

	def product_combinations( self, id_product ):
		""" Retreive the combination IDs for a given id_product """
		lst = []
		for item in self:
			if is_combination( item.id ):
				_id_product,_id_combination = unmangle_id_product( item.id )
				if _id_product == id_product:
					lst.append( item.id ) # this is a combination id
		return lst

	def productinfo_from_id( self, id_product ):
		""" Return a tuple with the  ProductData.reference and
		ProductData.name from the product ID """
		_product_data = self.product_from_id( id_product )
		if _product_data == None:
			return ('?%i?'%(Id), 'undefined', '')

		return ( _product_data.reference, _product_data.name, _product_data.ean13 )

	def search_products_from_supplier( self, id_supplier, include_inactives = False ):
		""" Find all the product corresponding to a given supplier """
		_result = []
		if include_inactives:
			for item in self.inactivelist:
				if item.id_supplier == id_supplier:
					_result.append( item )
					#print( "match")
		for item in self:
			if item.id_supplier == id_supplier:
				_result.append( item )
		return _result


	def search_products_from_partialref( self, sPartialRef, include_inactives = False ):
		""" Find an active product from a partial reference """
		_result = []
		_sToFind = canonical_search_string( sPartialRef )
		if include_inactives:
			for item in self.inactivelist:
				sProductRef = item.canonical_reference()
				if sProductRef.find( _sToFind )>=0 :
					_result.append( item )
					#print( "match")
		for item in self:
			sProductRef = item.canonical_reference()
			if sProductRef.find( _sToFind )>=0 :
				_result.append( item )
		return _result

	def search_products_from_label( self, sPartial, include_inactives = False ):
		""" Find products based on the label """
		sPartial = sPartial.upper()
		_result = []
		if include_inactives:
			for item in self.inactivelist:
				if sPartial in item.name.upper():
					_result.append( item )
					#print( "match")
		for item in self:
			if sPartial in item.name.upper():
				_result.append( item )
		return _result


	def search_products_for_ean( self, sEan ):
		""" Find an active product from a partial reference """
		_result = []
		for item in self:
			if item.ean13 == sEan:
				_result.append( item )
		return _result

	@property
	def last_id( self ):
		""" return the last (greatest) product_id registered. Ignore combination product ID (> 100000)"""
		_result = None
		for item in self:
			if item.is_combination:
				continue
			_result = max( _result, item.id )
		return _result
