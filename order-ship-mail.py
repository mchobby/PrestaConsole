#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" Usage: order-ship-mail

Just collect the shipping files for a given date then send the notification
mails if not done yet.
"""
# Rely on https://github.com/mailjet/mailjet-apiv3-python

# from prestaapi import PrestaHelper, CachedPrestaHelper, OrderStateList
# from output import PrestaOut
from config import Config
from collections import namedtuple
import os
import glob
from mailjet_rest import Client
import codecs
import json
import time
import datetime

PAUSE_MIN = 5 # Time in minutes between two sent iteration

config = Config()
# Get your environment Mailjet keys
if config.order_ship_api == 'MAILJET':
	mailjet = Client(auth=(config.order_ship_api_key, config.order_ship_api_secret), version='v3.1')
else:
	raise Exception( '%s mail API not supported!' % config.order_ship_api )

spath = config.order_ship_data_path
print( 'Order Ship Data Path: %s' % spath )
#dirnames = [ dirname for dirname in os.listdir(spath) if not os.path.isfile( os.path.join(spath,dirname)) ]

ShipInfo = namedtuple( 'ShipInfo', ['order_id','carrier','ship_nr','order_date','ship_date','customer','email', 'is_joined', 'joined_to'] )
# is_joined to
shipping_mails = {} # dictionnary with the content of the various shipping.xxx files where xxx is the key in dictionnary (eg: POSTE, subject, MR, ... )


def extract_info_from_file( filename ):
	_order_id = None
	_carrier  = None
	_ship_nr  = None
	_order_date = None
	_ship_date = None
	_customer = None
	_email    = None
	_is_joined = False
	_joined_to = None
	f = open( filename, "r" )
	s = f.readline()
	while s:
		s = s.replace( '\r\n', '' )
		if '--- Order ID :' in s:
			_order_id = s.split(' ')[4]
		if 'Order Date   :' in s:
			_order_date = s.split(' ')[5]
		if 'Ship Nr :' in s:
			_ship_nr = s.split(' ')[3]
		if 'Carrier :' in s:
			_carrier = s.split(' ')[2]
		if 'OPERATION DATE :' in s:
			_ship_date = s.split(' ')[3]
		if 'Customer     :' in s:
			_customer = s.split(':')[1].strip()
		if 'Cust.EMail   :' in s:
			_email = s.split(':')[1].strip()
		if 'JOINED TO ORDER :' in s:
			_is_joined = True
			_joined_to = s.split(':')[1].strip()
		s = f.readline()
	f.close()
	return ShipInfo( order_id=_order_id, carrier=_carrier, ship_nr=_ship_nr, order_date=_order_date, ship_date=_ship_date, customer=_customer, email=_email, is_joined=_is_joined, joined_to=_joined_to )

# import csv
# with open('order-ship-list.csv', 'wb') as csvfile:
#	spamwriter = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
#
#	spamwriter.writerow( ['order_id', 'carrier', 'order_date', 'ship_date', 'ship_nr'] )
#
#	# For each directory
#	for dirname in dirnames:
#		files = glob.glob( '%s/*.scan' % (os.path.join(spath,dirname)) )
#		for filename in files:
#			info = extract_info_from_file( filename )
#			spamwriter.writerow( [info.order_id , info.carrier, info.order_date, info.ship_date, info.ship_nr] )
#			print( info.order_id )

def subs( s, info ):
	""" Substitute the content of string with values coming from ShipInfo named typle """
	'','','','','','',''
	s = s.replace( '@@order_id@@'  , '%s' % info.order_id )
	s = s.replace( '@@ship_nr@@'   , '%s' % info.ship_nr )
	s = s.replace( '@@order_date@@', '%s' % info.order_date )
	s = s.replace( '@@ship_date@@' , '%s' % info.ship_date )
	s = s.replace( '@@customer@@'  , '%s' % info.customer )
	s = s.replace( '@@email@@'     , '%s' % info.email )
	return s.replace( '@@carrier@@'   , '%s' % info.carrier )

def load_mails():
	global spath, shipping_mails
	shipping_mail = {} # Empty it
	files = glob.glob( '%s/shipping.*' % spath )
	for filename in files:
		with codecs.open( filename, 'r', encoding='utf-8' ) as f:
			ext = filename.split( 'shipping.' )[1] # eg: POSTE
			shipping_mails[ ext ] = f.read()

def send_ship_mail( info ):
	global spath, subpath, shipping_mails, mailjet
	#debug:
	mail_file = '%s/%s.mail' % (os.path.join(spath,subpath), info.order_id )
	subject = subs( shipping_mails['subject'], info )
	if info.carrier in shipping_mails:
		htmlpart = subs( shipping_mails[info.carrier], info )
	else:
		htmlpart = subs( shipping_mails['DEFAULT'], info )

	# create JSON structure
	data = { 'Messages': [ {'From' : { "Email" : None, "Name" : None }, 'To' : [{ "Email" : None, "Name" : None }], "Subject": None, "TextPart": "This mail contains HTML parts", "HTMLPart": None } ]}
	data['Messages'][0]['From']['Email'] = 'frc@mchobby.be'
	data['Messages'][0]['From']['Name'] = 'Scanny'
	data['Messages'][0]['To'][0]['Email'] = info.email # Customer e-mail
	data['Messages'][0]['To'][0]['Name'] = info.customer
	data['Messages'][0]['Subject'] = subject
	data['Messages'][0]['HTMLPart'] = htmlpart

	result = mailjet.send.create(data=data)
	if result.status_code == 200: # OK --> Write the mail file
		with open( mail_file, 'w') as f:
			f.write( json.dumps( result.json() )) # Write string
	return result

def main( yyyymm ):
	global spath, subpath
	load_mails()

	spath = config.order_ship_data_path
	subpath = yyyymm # arguments[ '<yyyymm>' ]
	scans = glob.glob( '%s/*.scan' % (os.path.join(spath,subpath)) ) # File containing the scan information
	mails = glob.glob( '%s/*.mail' % (os.path.join(spath,subpath)) ) # File written when the mail is sent

	for scan in scans:
		if scan.replace('.scan','.mail') in mails: # mail already sent
			continue
		# Extracting data from scan file
		info = extract_info_from_file( scan )
		print( "-"*30 )
		if info.is_joined == True: # Is this joined order ? (to another order ?)
			print( "Mail for order %s" % info.order_id )
			print( "   Joined order are skip!")
		else:
			print( "Mail for order %s" % info.order_id )
			print( "   carrier : %s  ( %s )" % (info.carrier,info.ship_nr) )
			print( "   Customer: %s" % (info.customer) )
			print( "   E-mail  : %s" % (info.email) )

			result = send_ship_mail( info ) # Return a mailjet result code

			if result.status_code != 200: # Pas OK?
				print( "[ERROR] status_code: %s" % result.status_code )
				print( result.json() )
			else:
				print( "Sent!")


from docopt import docopt
if __name__ == '__main__':
	arguments = docopt(__doc__)
	iteration = 1
	# print(arguments)
	while True:
		now = datetime.datetime.now()
		print( '==[ %s : iteration %i ]%s' %(now.strftime("%b %d %Y %H:%M:%S"), iteration, '='*60))
		curr_month = now.strftime('%Y%m')
		main( curr_month ) # Process current month

		# Process last month every 5 iteration
		if (iteration%5) == 0:
			one_month = datetime.timedelta(days=31)
			prev_month = now - one_month
			prev_month = prev_month.strftime('%Y%m')
			print( 'process previous month')
			main( prev_month ) # process previous month (if any shipping remain there)

		print( 'pause %i min' % PAUSE_MIN )
		time.sleep( PAUSE_MIN*60 )
		iteration += 1
