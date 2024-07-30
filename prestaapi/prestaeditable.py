#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""prestaeditable.py - classes and helper for updating prestashop data via the PrestaShop API.

	PrestaShop data updates are made via load( id ) & save() method handling the XML data.
	Properties are used to change the data inside the XML data.

Created by Meurisse D. <info@mchobby.be>

Copyright 2014 MC Hobby SPRL, All right reserved
"""
from xml.etree import ElementTree

class EditableData(object):
	""" Base class to load & save content """
	def __init__( self, prestahelper, ressource ):
		self._helper = prestahelper
		self._ressource  = ressource # as stated inside WebService (eg: products)
		self._data = None

	def load( self, id ):
		self._id = id
		# _data = self.cachedphelper.webservice.get( 'products', 2328 )
		self._data = self._helper.webservice.get( self._ressource, self._id )

	def save( self ):
		_r = self._helper.webservice.edit( self._ressource, ElementTree.tostring(self._data, encoding="utf8" ) )

	@property
	def as_string( self ):
		return ElementTree.tostring( self._data)

class ProductEditable(EditableData):
	""" Allow to edit some properties of Product."""

	def __init__(self, prestahelper):
		super(ProductEditable, self).__init__(prestahelper, 'products')

	def load( self, id ):
		super(ProductEditable, self).load(id)
		self._p = self._data.find('product')
		# Remove nodes that cannot be edited
		self._p.remove( self._p.find('manufacturer_name') )
		self._p.remove( self._p.find('quantity') )

	@property
	def date_add( self ):
		return self._p.find('date_add').text

	@date_add.setter
	def date_add( self, dt ):
		self._p.find('date_add').text = dt.strftime("%Y-%m-%d 00:00:00")
