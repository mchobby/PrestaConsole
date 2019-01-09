#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

from prestaapi import PrestaHelper, CachedPrestaHelper, OrderStateList
from config import Config
from pprint import pprint
import logging 
import sys
import signal
# debugging
from xml.etree import ElementTree

config = Config()
h = CachedPrestaHelper( config.presta_api_url, config.presta_api_key, debug= False )
#print ("#products = %i" % ( len( h.products ) ) )

# Cmd de test 8042
cmd_nr = raw_input( '#Commande: ' )
if not cmd_nr.isdigit():
   raise ValueError( '%s is not a number' % cmd_nr )

orders = h.get_last_orders( int(cmd_nr), 1 )
order = orders[0]
if len( orders ) < 0:
    raise ValueError( 'order %s not found' % cmd_nr )

customer = h.get_customer( order.id_customer )

print( '--- Order ID : %i ---' % order.id )
# print( 'Carrier   ID : %i' % order.id_carrier )
# print( 'current state: %i' % order.current_state )
# print( 'Customer  ID : %i' % order.id_customer )
print( 'Customer     : %s' % customer.customer_name )
print( 'Cust.EMail   : %s' % customer.email )
print( 'Carrier      : %s' % h.carriers.carrier_from_id( order.id_carrier ).name )
print( 'Current State: %s' % h.order_states.order_state_from_id( order.current_state ).name )
print( 'valid        : %i' % order.valid )
print( 'payment      : %s' % order.payment )
print( 'total HTVA   : %.2f' % order.total_paid_tax_excl )
print( 'total Paid   : %.2f' % order.total_paid )

# Extract the xml data
el_prestashop = h.get_order_data( int(cmd_nr) )
if el_prestashop == None:
    print( 'This order does not exists' )
    exit()

# Update the order current_status
"""order = list( el_prestashop )[0]
order_properties = list( order )
order_current_state = [ order_property for order_property in order_properties if order_property.tag == 'current_state' ]
order_current_state[0].text = str( OrderStateList.ORDER_STATE_SHIPPING )
#print( ElementTree.tostring( el_prestashop ) )
"""

""" Activate error detection
      http://stackoverflow.com/questions/14457470/prestapyt-error-on-edit 
    A sample of XML to send
      http://nullege.com/codes/show/src%40p%40r%40prestapyt-HEAD%40examples%40prestapyt_xml.py/22/prestapyt.PrestaShopWebService.edit/python 
"""
# Save the order
h.post_order_data( int(cmd_nr), el_prestashop )

#print( order_properties[0].tag )
#print( order_properties[0].text )
#print( order_properties[0].attrib )
