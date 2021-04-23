#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""batch.py

Manage the Batch handling for Food (with Batch number, date, expiration date, etc).
Batches are managed with files under a storage patch and file locking based on FileLock

Copyright 2020 DMeurisse <info@mchobby.be>

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
from filelock import Timeout, SoftFileLock
import os, codecs
from datetime import datetime
# Backport of configparser with better Unicode support
#   https://pypi.org/project/configparser/
#
from backports import configparser

COUNTER_DAT = 'counter.dat'
LOCK_FILE   = 'batches.lock'

class EBatch( Exception ):
	pass

class BatchData( object ):
	def __init__( self ):
		self.batch_id   = None
		self.product_id = None
		self.product_reference = None
		self.product_name      = None
		self.product_ean       = None
		self.creation_date     = datetime.now()
		self.expiration        = None # 'mm/yyyy'
		self.label_count       = 0 # Number of printeed label
		self.info              = ''

	def save_in_section( self, section_name, config ):
		""" Save the data into a ConfigParser.section """
		config.set( section_name, 'batch_id'         , str( self.batch_id ) )
		config.set( section_name, 'product_id'       , str( self.product_id ) )
		config.set( section_name, 'product_reference', self.product_reference )
		config.set( section_name, 'product_name'     , self.product_name )
		config.set( section_name, 'product_ean'      , self.product_ean )
		config.set( section_name, 'creation_date'    , self.creation_date.strftime("%d/%m/%Y, %H:%M:%S") )
		config.set( section_name, 'expiration'		 , self.expiration  ) # 'mm/yyyy'
		config.set( section_name, 'label_count'		 , str( self.label_count ) ) # Number of printeed label
		config.set( section_name, 'info'			 , self.info )

	def load_from_section( self, section_name, config ):
		""" reload the data from a ConfigParser.section """
		self.batch_id = int( config.get( section_name, 'batch_id' ) )
		self.product_id        = config.get( section_name, 'product_id'        )
		self.product_reference = config.get( section_name, 'product_reference' )
		self.product_name  = config.get( section_name, 'product_name'     )
		self.product_ean   = config.get( section_name, 'product_ean'      )
		self.creation_date = datetime.strptime( config.get( section_name, 'creation_date' ), "%d/%m/%Y, %H:%M:%S" )
		self.expiration  = config.get( section_name, 'expiration'		  ) # 'mm/yyyy'
		self.label_count = int( config.get( section_name, 'label_count'	) ) # Number of printeed label
		self.info        = config.get( section_name, 'info'	 )

class TransformationData( object ):
	def __init__( self ):
		self.transformation_id = None # incremental ID
		self.target_product_id = None # Target product created from the BatchData
		self.target_product_reference = None
		self.target_product_name      = None
		self.target_product_ean       = None
		self.creation_date            = None
		self.expiration				  = None # mm/yyyy
		self.label_count              = 0 # Number of labels for the target

	def save_in_section( self, section_name, config ):
		""" Save the data into a ConfigParser.section """
		config.set( section_name, 'transformation_id'       , str( self.transformation_id ) )
		config.set( section_name, 'target_product_id'       , str( self.target_product_id ) )
		config.set( section_name, 'target_product_reference', self.target_product_reference )
		config.set( section_name, 'target_product_name'     , self.target_product_name )
		config.set( section_name, 'target_product_ean'      , self.target_product_ean )
		config.set( section_name, 'creation_date'           , self.creation_date.strftime("%d/%m/%Y, %H:%M:%S") )
		config.set( section_name, 'expiration'              , self.expiration  ) # 'mm/yyyy'
		config.set( section_name, 'label_count'             , str( self.label_count ) ) # Number of printeed label

	def load_from_section( self, section_name, config ):
		self.transformation_id = int( config.get( section_name, 'transformation_id' ))
		self.target_product_id = config.get( section_name, 'target_product_id' )
		self.target_product_reference = config.get( section_name, 'target_product_reference')
		self.target_product_name      = config.get( section_name, 'target_product_name'     )
		self.target_product_ean       = config.get( section_name, 'target_product_ean'      )
		self.creation_date 			  = datetime.strptime( config.get( section_name, 'creation_date' ), "%d/%m/%Y, %H:%M:%S" )
		self.expiration 			  = config.get( section_name, 'expiration'              ) # 'mm/yyyy'
		self.label_count 			  = int( config.get( section_name, 'label_count' )) # Number of printeed label

class Batch( object ):
	""" Batch object with load & save facilities """
	def __init__( self ):
		self.data = BatchData()
		self.transformations = []

	def add_transformation( self ):
		_r = TransformationData()
		_r.transformation_id = len( self.transformations )+1
		self.transformations.append( _r )
		return _r

	def has_transformation( self, id_product ):
		# Check if the batch contains transformation for the target product_ID
		for t in self.transformations:
			if int(t.target_product_id) == int(id_product):
				return True
		return False


	def sub_path_for_batch( self, batch_id ):
		""" Compute the storage sub-path for a given batch id. 100 files by sub-directory
			12  --> 00000/12
			125 --> 00001/125
			1255--> 00012/1255 """
		return "%05i" % (batch_id // 100)

	def save( self, storage_path, batch_id ):
		config = configparser.ConfigParser() # backports.configparser.ConfigParser
		config.add_section('BATCH')
		self.data.batch_id = batch_id
		self.data.save_in_section( 'BATCH', config )
		for item in self.transformations:
			section_name = "TRANSFORMATION.%s" % item.transformation_id
			_section = config.add_section( section_name )
			item.save_in_section( section_name, config )
		# create sub-directory every 100 batches
		storage_sub_path = self.sub_path_for_batch( batch_id )
		if not os.path.isdir( os.path.join(storage_path,storage_sub_path) ):
			os.mkdir( os.path.join(storage_path,storage_sub_path) )
		# store the file
		filename = os.path.join( storage_path, storage_sub_path, str(batch_id) )
		with codecs.open( filename, 'wb', encoding='utf-8' ) as _file:
			config.write( _file )

	def load( self, storage_path, batch_id ):
		# store the file
		config = configparser.ConfigParser()
		storage_sub_path = self.sub_path_for_batch( batch_id )
		filename = os.path.join( storage_path, storage_sub_path, str(batch_id) )
		if not os.path.exists( filename ):
			raise EBatch( "Batch %s does not exists" % batch_id )
		with codecs.open( filename, 'rb', encoding='utf-8' ) as _file:
			config.readfp( _file )
		self.data.load_from_section( 'BATCH', config)
		for section_name in config.sections():
			if 'TRANSFORM' in section_name:
				trf = self.add_transformation()
				trf.load_from_section( section_name, config )

	def as_text( self, storage_path, batch_id ):
		r = []
		storage_sub_path = self.sub_path_for_batch( batch_id )
		filename = os.path.join( storage_path, storage_sub_path, str(batch_id) )
		if not os.path.exists( filename ):
			raise EBatch( "Batch %s does not exists" % batch_id )
		with codecs.open( filename, 'rb', encoding='utf-8' ) as _file:
			_lines = _file.readlines()
			for _line in _lines:
				r.append( _line.encode('utf8','replace').replace('\r','').replace('\n',''))
		return r

class BatchFactory( object ):
	def __init__( self, storage_path ):
		self.storage_path = storage_path
		# check path existante
		assert os.path.exists( self.full_path(COUNTER_DAT) ), "Storage path access error. Missing %s !" % self.full_path(COUNTER_DAT)
		# Lock files
		self.lock = SoftFileLock( self.full_path(LOCK_FILE) )

	def full_path( self, subpath ):
		""" compose the full path to access an item in the storage path """
		return os.path.join( self.storage_path, subpath )

	def new_batch( self ):
		""" create a new Batch objet (but do not yet reserve the batch id) """
		return Batch()

	def save_batch( self, batch ):
		""" Store the Batch object & assign the batch_id when applicable """
		if not batch.data.batch_id:
			batch.data.batch_id = self.next_batch_id()
		batch.save( self.storage_path, batch.data.batch_id )

	def batch_filename(self, batch_id ):
		""" Returns the full path for a given batch """
		return os.path.join( self.storage_path, "%05i" % (batch_id // 100), str(batch_id) )

	def load_batch( self, batch_id ):
		""" Load the Batch object from disk """
		_batch = Batch()
		_batch.load( self.storage_path, batch_id  )
		return _batch

	def as_text( self, batch_id ):
		""" returns the content of a batch as readable text """
		_batch = Batch()
		return _batch.as_text( self.storage_path, batch_id  )

	def has_text( self, start_batch_id, max_count, _text ):
		""" Search for a given string _text (not case-sensitive ) from start_batch down to start_batch-max_count.

		Returns a list of batch_id """
		_r = []
		_text = _text.upper().replace('-','')
		for _batch_id in range( start_batch_id, start_batch_id - max_count, -1 ):

			if _batch_id < 0: # Going to far? then stop
				break
			# Load the batch
			try:
				_lines = self.as_text( _batch_id )
				if any( [ _text in _line.upper().replace('-','') for _line in _lines ] ):
					_r.append( _batch_id )
					continue # process nex file
			except EBatch as err:
				pass # silent error
				#print( '[ERROR] %s' % (_batch_id,err) )
		return _r


	def next_batch_id( self ):
		with self.lock:
			with open( self.full_path(COUNTER_DAT), 'r' ) as f:
				_id = int( f.read() )
			_id += 1
			with open( self.full_path(COUNTER_DAT), 'w' ) as f:
				f.write( str(_id) )
		return _id

	def last_batch_id( self ):
		""" Just retreive the last batch ID (just for info) without modifying it!
		    DOES NOT APPLY ANY LOCKING MECANISM! """
		with open( self.full_path(COUNTER_DAT), 'r' ) as f:
			_id = int( f.read() )
		return _id
