#!/usr/bin/python
# -*- coding: utf-8 -*-
# vim:set ts=4 sw=4 noet:

# AficioAccounts.py -- Adapter for the XMLRPC interfaces of Ricoh Aficio 1075
#   concerning account management.
#
# Copyright (C) 2007 Philipp Kern <philipp.kern@fsmi.uni-karlsruhe.de>
# Copyright (C) 2008 Fabian Knittel <fabian.knittel@fsmi.uni-karlsruhe.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.

# Based on bash scripts and XML snippets by
# Thomas Witzenrath <thomas.witzenrath@fsmi.uni-karlsruhe.de>.

# Depends on python-httplib2, python-xml

import httplib2
import codecs
import socket
from base64 import b64encode, b64decode
from xml.dom.ext.reader import Sax2
from xml import xpath

STRING_ENCODING = 'Windows-1252'

def _get_text_node(path, node):
	return xpath.Evaluate('string(%s)' % path, node)

class UserMaintException(RuntimeError):
	pass

class UserRestrict(object):
	def __init__(self, grant_copy = False, grant_printer = False,
			grant_scanner = False, grant_storage = False):
		self.grant_copy = grant_copy
		self.grant_printer = grant_printer
		self.grant_scanner = grant_scanner
		self.grant_storage = grant_storage

	def __str__(self):
		return '(c%dp%ds%dst%d)' % (self.grant_copy, self.grant_printer,
				self.grant_scanner, self.grant_storage)

	def __avail_str(self, is_available):
		if is_available:
			return '<available/>'
		else:
			return '<restricted/>'

	def get_as_xml(self):
		return """
			<restrictInfo>
				<copyInfo>
					<monochrome>%s</monochrome>
				</copyInfo>
				<printerInfo>
					<monochrome>%s</monochrome>
				</printerInfo>
				<scannerInfo>
					<scan>%s</scan>
				</scannerInfo>
				<localStorageInfo>
					<plot>%s</plot>
				</localStorageInfo>
			</restrictInfo>""" % (self.__avail_str(self.grant_copy),
				self.__avail_str(self.grant_printer),
				self.__avail_str(self.grant_scanner),
				self.__avail_str(self.grant_storage))

class User(object):
	def __init__(self, user_code, name, restrict = None):
		self.user_code = user_code
		self.name = name
		self.restrict = restrict

	def __str__(self):
		return 'User "%s" (#%u, %s)' % (self.user_code, self.name,
				str(self.restrict))

	def get_as_xml(self):
		encoded_name = b64encode(
				codecs.getencoder(STRING_ENCODING)(self.name)[0])
		return """<user version="1.1">
					<userCode>%u</userCode>
					<userType>general</userType>
					<userCodeName enc="%s">%s</userCodeName>
					%s
				</user>""" % (self.user_code, STRING_ENCODING, encoded_name,
					self.restrict.get_as_xml())

class UserMaintSession(object):
	"""
	Objects of this class represent a user maintainance session. They provide
	methods to retrieve and modify user accounts.

	There is no session on the network level: Each request initiates a
	self-contained XML-RPC request.
	"""
	def __init__(self, *args, **kwargs):
		self.__host = kwargs['host']
		self.__port = kwargs.get('port', 80)
		self.__auth_token = kwargs['auth_token']

	def _send_request(self, body):
		headers = {'Content-Type': 'text/xml;charset=us-ascii'}
		uri = "http://%s:%d/System/usermaint/" % \
			(self.__host, self.__port)

		h = httplib2.Http()
		(result, content) = h.request(uri, "POST", body = body,
				headers = headers)

		print content
		reader = Sax2.Reader()
		doc = reader.fromString(content)
		return doc

	def _perform_operation(self, oper):
		body = """<?xml version='1.0' encoding='us-ascii'?>
			<operation>
				<authorization>%s</authorization>
			%s
			</operation>
		""" % (self.__auth_token, oper)
		return self._send_request(body)

	def _get_operation_result(self, doc, oper_name):
		success = _get_text_node(
				'operationResult/%s/isSucceeded' % oper_name, doc) == 'true'
		if success:
			return None
		else:
			error_code = _get_text_node(
				'operationResult/%s/errorCode' % oper_name, doc)
			return error_code

	def add_user(self, user_code, name):
		u = User(user_code = user_code, name = name,
				restrict = UserRestrict(grant_copy = True,
						grant_printer = True, grant_scanner = True,
						grant_storage = True))
		body = """<addUserRequest>
					<target>
						<userCode>%u</userCode>
					</target>
					%s
				</addUserRequest>
		""" % (user_code, u.get_as_xml())
		doc = self._perform_operation(body)

		error_code = self._get_operation_result(doc, 'addUserResult')
		if error_code is not None:
			raise UserMaintException('failed to add user (code %s)' %\
					error_code)

	def delete_user(self, user_code):
		body = """<deleteUserRequest>
					<target>
						<userCode>%u</userCode>
					</target>
				</deleteUserRequest>
		""" % user_code
		doc = self._perform_operation(body)

		error_code = self._get_operation_result(doc, 'deleteUserResult')
		if error_code is not None:
			raise UserMaintException('failed to delete user (code %s)' %\
					error_code)

	def user_counter(self, user_code=''):
		body = """<getUserInfoRequest>
					<target>
						<userCode>%s</userCode>
					</target>
					<user version="1.1">
						<userCode/>
						<userCodeName/>
						<restrictInfo/>
						<statisticsInfo/>
					</user>
				</getUserInfoRequest>
		""" % user_code
		doc = self._perform_operation(body)

		error_code = self._get_operation_result(doc, 'getUserInfoResult')
		if error_code is not None:
			raise UserMaintException('failed to retrieve user info (code %s)' %\
					error_code)

		list = []
		# Iterate over the users.
		for user in xpath.Evaluate(
				'operationResult/getUserInfoResult/result/user', doc):
			user_code = _get_text_node('userCode', user)
			if user_code == 'other':
				user_code = 0
				name = 'other'
			else:
				user_code = int(user_code)
				name = codecs.getdecoder('windows-1252')(
					b64decode(_get_text_node('userCodeName', user))
					)[0]
			copy_a3_count = int(_get_text_node(
				'statisticsInfo/copyInfo/monochrome/doubleSize', user))
			copy_a4_count = int(_get_text_node(
				'statisticsInfo/copyInfo/monochrome/singleSize', user))
			print_a3_count = int(_get_text_node(
				'statisticsInfo/printerInfo/monochrome/doubleSize', user))
			print_a4_count = int(_get_text_node(
				'statisticsInfo/printerInfo/monochrome/singleSize', user))
			list.append((user_code, name, print_a3_count, print_a4_count,
					copy_a3_count, copy_a4_count))
		return list
