#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""prestahelper.py - classes and helper for accessing the PrestaShop API
 
Created by Meurisse D. <info@mchobby.be>
  
Copyright 2014 MC Hobby SPRL, All right reserved
"""  

from prestapyt import PrestaShopWebServiceError, PrestaShopWebService
from xml.etree import ElementTree
from collections import defaultdict
from pprint import pprint
import logging
import pickle
import os.path
from datetime import datetime

PRESTA_UNDEFINE_INT = -1

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

		self.__prestashop.debug = debug
		
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
		
	def get_carriers( self ):
		""" Retreive a list of Carriers (CarrierData) from prestashop """
		logging.debug( 'read carriers' )
		el = self.__prestashop.search( 'carriers', options = {'display':'[id,deleted,active,name]'} )

		_result = CarrierList( self )
		_result.load_from_xml( el )

		return _result
		
	def get_products( self ):
		""" retreive a list of products from PrestaShop """
		logging.debug( 'read products' )
		#el = self.__prestashop.search( 'products' )
		#print( ElementTree.tostring( el ) )
		el = self.__prestashop.search( 'products', options = {'display': '[id,reference,active,name,price,wholesale_price,id_supplier,id_category_default,advanced_stock_management,available_for_order,ean13]'} )
		
		_result = BaseProductList( self )
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
		el = self.__prestashop.search( 'product_suppliers', options = {'display': '[id,id_product,id_supplier,product_supplier_reference]'} )
		
		_result = ProductSupplierList( self )
		_result.load_from_xml( el )
		
		return _result
		
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
		A list of OrderData objects
		"""
		_result = [] 
		for i in range( count ): #  range(1)=0 range(2)=0,1
			el = self.__prestashop.get( 'orders', fromId-i )
			order = OrderData( self )
			order.load_from_xml( el )
			_result.append( order )
		return _result
		
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
		el = self.__prestashop.search( 'stock_availables' , options={ 'display':'[id, id_product,quantity,depends_on_stock,out_of_stock]' } ) 
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
		 
class CachedPrestaHelper( PrestaHelper ):
	""" PrestaHelper class that permamently cache some useful information """
	CACHE_FILE_VERSION = 3
	CACHE_FILE_NAME    = 'cachefile.pkl'
	CACHE_FILE_DATETIME= None
	
	__carrier_list = None
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
		__MAX_STEP = 7
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
		finally:
			fh.close()
		
	def fireProgress( self, currentStep, maxStep, message ):
		if self.progressCallback == None:
			return
		# Prepare data
		e = PrestaProgressEvent( currentStep, maxStep, message )
		# fire event
		self.progressCallback( e )
		
	@property
	def carriers( self ):
		""" Return the carrier list """
		return self.__carrier_list
		
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
		""" Register a BaseData children into the list """
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

class OrderData( BaseData ):
	""" Constains the data of an order. 
	
	This class is supposed to extend with time """
	
	__slots__ = ["id", "id_customer", "id_carrier", "current_state", "valid", "payment", "total_paid_tax_excl", "total_paid" ]
	
	def load_from_xml( self, node ):
		""" Initialise the data of an Order """
		# print( ElementTree.tostring( node ) )
		items = etree_to_dict( node ) 
		order = items['prestashop']['order']
		# print( order )
		self.id            = int( order['id'] )
		self.id_customer   = int( order['id_customer']['#text'] )
		self.id_carrier    = int( order['id_carrier']['#text'] )
		self.current_state = int( order['current_state']['#text'] )
		self.valid         = int( order['valid'] )
		self.payment       = order['payment']
		self.total_paid_tax_excl = float( order['total_paid_tax_excl' ] )
		self.total_paid          = float( order['total_paid' ] )
				
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
			_data.id_supplier = int( item['id_supplier']['#text'] )
			_data.reference   = item['product_supplier_reference']
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
			_data.name    = item['name']['language']['#text']
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
			_data.name        = item['name']['language']['#text']
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
		ean13(str)	           - ean13 value when available
	
	Remarks: directly loaded from by the product list class """
	
	__slots__ = ["id", "active", "reference", "name", "wholesale_price", "price", "id_supplier", "id_category_default", "advanced_stock_management", "available_for_order", "ean13" ]
	
	def load_from_xml( self, node ):
		""" Initialise the data of an product """
		pass
		
	def __getstate__(self):
		""" Return the object state for pickeling """
		return { "id":self.id, "active":self.active, "reference":self.reference , "name":self.name, "wholesale_price": self.wholesale_price, "price": self.price, "id_supplier" : self.id_supplier, "id_category_default" : self.id_category_default , "advanced_stock_management" : self.advanced_stock_management, "available_for_order" : self.available_for_order, "ean13" : self.ean13 }
		
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
		
	def canonical_reference( self ):
		""" Return the canonical search string of the reference. 
			Allow a better search algorithm """
			
		return canonical_search_string( self.reference )

class StockAvailableData( BaseData ):
	""" Contains the Stock_Available description data """
	__slots__ = ["id", "id_product", "depends_on_stock", "out_of_stock", "quantity" ]

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
		return { "id" : self.id, "id_product" : self.id_product, "depends_on_stock": self.depends_on_stock, "out_of_stock" : self.out_of_stock, "quantity" : self.quantity }

	def __setstate__(self, dic):
		""" set the state of the object based on dictionary """
		self.id     		  = dic['id']
		self.id_product 	  = dic['id_product']
		self.depends_on_stock = dic['depends_on_stock'] 
		self.out_of_stock 	  = dic['out_of_stock']
		self.quantity 	  	  = dic['quantity']
		
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
		items = etree_to_dict( node )
		items = items['prestashop']['stock_availables']['stock_available']
		for item in items:
			_data = StockAvailableData( self.helper )
			_data.id               = int( item['id'] )
			_data.id_product       = int( item['id_product']['#text'] )
			_data.depends_on_stock = int( item['depends_on_stock'] )
			_data.out_of_stock     = int( item['out_of_stock' ] )
			_data.quantity         = int( item['quantity'] )
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
		
class BaseProductList( BaseDataList ):
	""" List of product. Base class that can be derivated """

	# used to store inactive objects
	inactivelist = [] 
	
	def load_from_xml( self, node ):
		""" Load the Product list with data comming from prestashop search.
			Must contains nodes: id, name, active, ... """
		items = etree_to_dict( node )
		#print( items )
		items = items['prestashop']['products']['product']
		for item in items:
			# print( item )
			_data = ProductData( self.helper )
			_data.active   = int( item['active'] )
			_data.id       = int( item['id'] )
			_data.id_category_default = int( item['id_category_default']['#text'] )
			_data.available_for_order = int( item['available_for_order'] )
			_data.advanced_stock_management = int( item['advanced_stock_management'] )
			_data.name     = item['name']['language']['#text']
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
			# Auto-switch from EAN12 to EAN13
			# Damned PrestaShop accept EAN12 instead of ean13!?!?
			if len(_data.ean13) == 12:
				_data.ean13 = calculate_ean13( _data.ean13 ) 

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

	def product_from_id( self, Id ):
		""" Return the ProductData object from product ID """
		pass
		for item in self:
			if item.id == Id:
				return item
		for item in self.inactivelist:
			if item.id == Id:
				return item
		return None
		
	def productinfo_from_id( self, Id ):
		""" Return a tuple with the  ProductData.reference and
		ProductData.name from the product ID """
		pass
		_product_data = self.product_from_id( Id )
		if _product_data == None:
			return ('?%i?'%(Id),'undefined')
		return (_product_data.reference, _product_data.name )

	def search_products_from_partialref( self, sPartialRef ):
		""" Find an active product from a partial reference """
		_result = []
		_sToFind = canonical_search_string( sPartialRef )
		for item in self:
			sProductRef = item.canonical_reference()
			if sProductRef.find( _sToFind )>=0 :
				_result.append( item )
		return _result
