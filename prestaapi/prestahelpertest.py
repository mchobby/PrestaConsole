#!/usr/bin/python
#-*- encoding: utf8 -*-
""" Various tests and example of use of PrestaHelper """

from prestahelper import PrestaHelper, OrderStateList, CachedPrestaHelper

class PrestaHelperTest( object ):
	_pHelper = None

	def __init__( self, prestahelper ):
		""" Initialise the tester object
		
		pHelper - a PrestaHelper already initialised
		"""
		self._pHelper = prestahelper 
	
	def test( self ):
		print( '******************************************************************' )
		print( '*  PrestaHelperTest.test()                                       *' )
		print( '******************************************************************' )
		#self.test_accessrights()
		#self.test_lastcustomermessage_id()
		self.test_lastcustomermessages()
		#self.test_customerthread() 
		#self.test_carriers()
		#self.test_order_states()
		#self.test_orders()
		#self.test_products() # Prefer using the CachedPrestaHelper class
		#self.test_bad_stock_config_ids()
		#self.test_suppliers()
		self.test_product_suppliers()
		#self.test_categories()
		#self.test_stock_available()
	
	def test_accessrights(self):
		""" affiche la liste des droits """
		rights = self._pHelper.get_accessrights()
		for k,v in rights.items():
			print( '--- %s ---' % k )
			print( '  get:%s, put:%s, post:%s, head:%s' % ( v['@get'], v['@put'], v['@post'], v['@head'] ) ) 
			print( '  descr: %s ' % (v['description']['#text']) )

	def test_lastcustomermessage_id(self):
		""" afficher les derniers messages clients """
		id = self._pHelper.get_lastcustomermessage_id()
		print( 'last message id: %s' % id )
		#msgs = self._pHelper.get_lastcustomermessages(10)

	def test_lastcustomermessages(self):
		""" affiche les 5 derniers messages clients """
		id = self._pHelper.get_lastcustomermessage_id()
		print( 'last message id: %s' % id )
		custmsgs = self._pHelper.get_lastcustomermessages( id, 10 )
		for custmsg in custmsgs: # CustomerMessageData
			print( '--- id: %s---------------' % custmsg.id )
			print( '   date_add: %s' % custmsg.date_add )
			print( '   read    : %s' % custmsg.read )
			print( '   Employee: %s' % custmsg.id_employee )
			print( '   id_customer_thread: %s' % custmsg.id_customer_thread )
			print( custmsg.message )
			print( '' )

	def test_customerthread(self):
		""" Affiche le customer thread du dernier message """
		id = self._pHelper.get_lastcustomermessage_id()
		custmsgs = self._pHelper.get_lastcustomermessages( id, 1 )
		id_customer_thread = custmsgs[0].id_customer_thread
		print( 'last message id: %s' % id )
		print( '  +-> id_customer_thread: %s' % id_customer_thread )
		custthread = self._pHelper.get_customerthread( id_customer_thread-25 ) 
		print( '  +-> id_customer: %i' % custthread.id_customer )
		print( '  +-> id_order   : %i' % custthread.id_order )
		print( '  +-> id_contact : %i' % custthread.id_contact )
		print( '  +-> email      : %s' % custthread.email )
		print( '  +-> STATUS     : %s' % custthread.status )
		print( '  +-> date_add   : %s' % custthread.date_add )
		print( '  +-> date_upd   : %s' % custthread.date_upd )
		print( '  +-> Message IDs: %s' % (','.join([str(i) for i in custthread.customer_message_ids]) ))
		threadmessages = custthread.get_customermessages()
		for customermessage in threadmessages:
			print( '--- id: %s---------------' % customermessage.id )
			print( '   date_add: %s' % customermessage.date_add )
			print( '   read    : %s' % customermessage.read )
			print( customermessage.message )
			print( '' )

	def test_carriers(self):
		""" Affiche la liste des transporteurs """
		carriers = self._pHelper.get_carriers()
		for carrier in carriers:
			print ( '--- Carrier id: %s ---------------------' % carrier.id )
			print ( 'name   : %s' % carrier.name )
			print ( 'deleted: %s' % carrier.deleted )
			print ( 'active : %s' % carrier.active )
			
		aCarrierId = carriers[1].id
		# Locate Carrier from ID
		carrier = carriers.carrier_from_id( aCarrierId )
		print( 'Id %s -> %s' % (aCarrierId, carrier.name ) )
		print( 'Id %s -> %s' % (aCarrierId, carriers.name_from_id( aCarrierId )) )
		print( 'Id %s -> %s' % (9999, carriers.name_from_id( 9999 )) )
		
	def test_order_states( self ):
		""" Affiche la liste des status de commande """
		order_states = self._pHelper.get_order_states()
		
		for order_state in order_states:
			print( '--- Order State id: %s ---------------------' % order_state.id )
			print( 'name       : %s' % order_state.name )
			print( 'unremovable: %s' % order_state.unremovable )
			print( 'send_email : %s' % order_state.send_email )
			print( 'invoice    : %s' % order_state.invoice )
			print( 'shipped	   : %s' % order_state.shipped )
			print( 'paid       : %s' % order_state.paid )
			print( 'deleted    : %s' % order_state.deleted )
		
		order_state = order_states.order_state_from_id( 3 )
		print( 'order state id = 3 -> %s' % order_state.name )
		print( 'order state id = 2 -> %s' % order_states.name_from_id( 2 ) )
		
		print( 'Is Wait_BankWire order status is paid? %s' % order_states.is_paid( order_states.ORDER_STATE_WAIT_BANKWIRE ) )
		print( 'Is PAID order status is paid? %s' % order_states.is_paid( order_states.ORDER_STATE_PAID ) )
		print( 'Is Shipped order status is paid? %s' % order_states.is_paid( order_states.ORDER_STATE_SHIPPED ) )
		print( 'Is Shipped order status is waiting payment? %s ' % order_states.is_payment_waiting( order_states.ORDER_STATE_SHIPPED ) )
		print( 'Is Wait_Bankwire order status is waiting payment? %s ' % order_states.is_payment_waiting( order_states.ORDER_STATE_WAIT_BANKWIRE ) )  
		print( 'Is Wait_Paypal order status is waiting payment? %s ' % order_states.is_payment_waiting( order_states.ORDER_STATE_WAIT_PAYPAL ) )  
		print( 'Is PAID order status is waiting payment? %s ' % order_states.is_payment_waiting( order_states.ORDER_STATE_PAID ) )
		print( 'Is Wait_Paypal order status is sent? %s' % order_states.is_sent( order_states.ORDER_STATE_WAIT_PAYPAL ) )
		print( 'Is Shipping order status is sent? %s' % order_states.is_sent( order_states.ORDER_STATE_SHIPPING ) )
		print( '--- Testing is_new_order ---' )
		for order_state in order_states:
			print( 'Is \"%s\" order status is a new order? %s' % (order_state.name, order_states.is_new_order(order_state.id)) )
		print( '--- Testing is_open_order ---' )
		for order_state in order_states:
			print( 'Is \"%s\" order status is a open order? %s' % (order_state.name, order_states.is_open_order(order_state.id)) )
			
	def test_orders(self):
		print( '--- ORDERS ---' )
		last_order_id = self._pHelper.get_lastorder_id()
		print( 'last order id: %i' % last_order_id )
		
		orders = self._pHelper.get_last_orders( last_order_id, 1 )
		
		for order in orders:
			print( '--- Order ID : %i ---' % order.id )
			print( 'Customer  ID : %i' % order.id_customer )
			print( 'Carrier   ID : %i' % order.id_carrier )
			print( 'current state: %i' % order.current_state )
			print( 'valid        : %i' % order.valid )
			print( 'payment      : %s' % order.payment )
			print( 'total HTVA   : %.2f' % order.total_paid_tax_excl )
			print( 'total Paid   : %.2f' % order.total_paid )
			
		filtered_order_ids = self._pHelper.get_order_ids( OrderStateList.ORDER_STATE_WAIT_BANKWIRE ) 
		print( '--- BankWire state orders ---' )
		for iId in filtered_order_ids:
			print('order id: %s' % iId )
			
	def test_products( self ):
		print( '--- PRODUCTS ---' )
		products = self._pHelper.get_products()
		
		for product in products:
			print( '--- ProductID : %i ---' % product.id )
			print( 'Ref - Nom     : %s - %s' %  (product.reference,  product.name ) )
			print( 'price         : %.2f EUR' % product.price )
			print( 'Buy Price     : %.2f EUR' % product.wholesale_price ) 
			print( 'ID_supplier   : %i'       % product.id_supplier ) # May be -1 if undefined
			print( 'ID_categ_def  : %i'       % product.id_category_default )
			print( 'adv.stock.mng : %i'       % product.advanced_stock_management )
			print( 'avai.for.order: %i'       % product.available_for_order )


		# return a tuple (ref,name)
		productinfo = products.productinfo_from_id( 25 )
		print( 'who is product ID = %i' % 25 )
		print( '  +-> ref: %s ' % productinfo[0] )
		print( '  +-> name: %s ' % productinfo[1] )
		
		# Search a product 
		_list = products.search_products_from_partialref( 'push' )
		print( 'Product reference having (push)' )
		for item in _list:
			print (' Found %s: %s' % (item.reference, item.name) )
		print( 'end of search' )	
		
	def test_bad_stock_config_ids( self ):
		print( '--- Bad Stock Config ---' )
		orderable_product_ids = self._pHelper.get_outofstock_orderable_ids()
		unsynch_product_ids = self._pHelper.get_unsynch_stock_qty_ids()
		# merge the two lists 
		product_ids = list( set( orderable_product_ids + unsynch_product_ids ) )
		
		# Retrieve list of products 
		products = self._pHelper.get_products() # Prefer using the CachedPrestaHelper
		
		print( '%i products being orderable out of stock or not synch with Advanced Stock Management' % len( product_ids ) )
		for iId in product_ids:
			print( 'Product ID: %i ' % (iId) )
			print( '  +-> %s' % products.product_from_id( iId ).reference )
		
	def test_suppliers( self ):
		print( '--- SUPPLIERS ---' )
		suppliers = self._pHelper.get_suppliers()
		
		for supplier in suppliers:
			print( '%i - %s' % (supplier.id, supplier.name ) )
			
		print( 'Who is supplier ID = 10' )
		print( '  +--> %s' % (suppliers.name_from_id(10)) )

	def test_product_suppliers( self ):
		print( '--- PRODUCT SUPPLIERS ---' )
		product_suppliers = self._pHelper.get_product_suppliers()
		for item in product_suppliers:
			print( 'ID Product: %i --> ID supplier: %i --> ref: %s' % (item.id_product, item.id_supplier, item.reference ) )
		
		print( 'Suppliers for ID Product 17' )	
		suppliers = product_suppliers.suppliers_for_id_product( 17 )
		for info in suppliers:
			print( 'id supplier: %i  --> ref: %s' % (info.id_supplier, info.reference) )
			
		print( 'Reference for ID_product 17 and ID_supplier 2' )
		print ( product_suppliers.reference_for( id_product = 17, id_supplier = 2 ) )

		print( 'first Reference found for ID_product 17' )
		print ( product_suppliers.reference_for( id_product = 17, id_supplier = None ) )
		
			
	def test_categories( self ):
		print( '--- CATEGORIES ---' )
		categories = self._pHelper.get_categories()
		
		for category in categories:
			print( '%i - %s' % (category.id, category.name ) )
			
		print( 'Who is category ID = 23' )
		print( '  +--> %s' % (categories.name_from_id(23)) )
		
	def test_stock_available( self ):
		# To be used with products, and do prefer to use the caching
		print( '--- STOCK AVAILABLES ---' )
		stocks = self._pHelper.get_stockavailables()
		
		for stock in stocks:
			print( "id_product: %i --> Qty = %i" % (stock.id_product, stock.quantity) )
		
		# Force quantity update:
		newQty = stocks.stockavailable_from_id_product( 10 ).update_quantity()
		if( newQty != None ):
			print( "Update Qty for article %i => %i" % ( 10, newQty ) )
			
		# Force the update of all quantities
		stocks.update_quantities()
		print( "id_product: %i --> Qty = %i" % (stocks[3].id_product, stocks[3].quantity) )
		
			
class CachedPrestaHelperTest( object ):
	""" Test of the CachedPrestaHelper object """
	_pHelper = None
	
	def __init__( self, cachedprestahelper ):
		""" Initialize the tester object.
		
		Args:
			pHelper (CachedPrestaHelper): an instance of the CachedPrestaHelper already initialised
		"""
		self._pHelper = cachedprestahelper 

	def test_cache( self ):
		print( '******************************************************************' )
		print( '*  CachedPrestaHelperTest.test_cache()                           *' )
		print( '******************************************************************' )
		print( 'Type of Helper is %s' % type(self._pHelper) )
		print( '#Carriers = %s' % len(self._pHelper.carriers) )
		print( '#OrderStates = %s' % len( self._pHelper.order_states ) )
		print( '#Products = %i' % len( self._pHelper.products ) )
		print( '#suppliers = %i' % len( self._pHelper.suppliers ) )
		print( '#categories = %i' % len( self._pHelper.categories ) )
		print( '#stock availables = %i' % len( self._pHelper.stock_availables ) )
		print( '#product suppliers available = %i' % len( self._pHelper.stock_availables ) )
		
		print('mise à jour des qty' )
		self._pHelper.stock_availables.update_quantities()
		print( 'Voila, c est fait' )


def run_prestahelper_tests(presta_api_url, presta_api_key, debug):
	""" Execute the various tests on PrestaHelper & CachedPrestaHelper 
	
	Args:
		presta_api_url (string): URL where the presta shop API can be located
		presta_api_key (string): The secret key granting access to the API 
								 generated in PrestaShop 
	"""
	phelper = PrestaHelper( presta_api_url, presta_api_key, debug )
	tester = PrestaHelperTest( phelper )
	tester.test()

	def progressHandler( prestaProgressEvent ):
		if prestaProgressEvent.is_finished:
			print( '%s' %prestaProgressEvent.msg )
		else:
			print( '%i/%i - %s' % ( prestaProgressEvent.current_step, prestaProgressEvent.max_step, prestaProgressEvent.msg ) )
    
    # A CachedPrestaHelper is a PrestaHelper with cache capabilities	
	cachedphelper = CachedPrestaHelper( presta_api_url, presta_api_key, debug, progressCallback = progressHandler )
	# Force loading cache
	#   cachedphelper.load_from_webshop()
	tester = CachedPrestaHelperTest( cachedphelper )
	tester.test_cache()
	
	# Ensure cache file to be saved (and will be automatically reloaded)
	cachedphelper.save_cache_file()
	
	# Force reload from webShop
	#  cachedphelper.load_from_webshop()
	#  tester.test_cache() # again
	
	
	# print( rights )	 
