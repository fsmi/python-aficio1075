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

def _decode(str, encoding = STRING_ENCODING):
	if encoding == 'none' or encoding is None or encoding == '':
		return str
	else:
		return codecs.getdecoder(encoding)(b64decode(str))

def _encode(str, encoding = STRING_ENCODING):
	if encoding == 'none' or encoding is None or encoding == '':
		return str
	else:
		return b64encode(codecs.getencoder(encoding)(str)[0])


def _get_text_node(path, base_node):
	return xpath.Evaluate('string(%s)' % path, base_node)

class UserMaintException(RuntimeError):
	pass

class UserStatistics(object):
	pass
	def __init__(self, copy_a4 = 0, copy_a3 = 0, print_a4 = 0,
			print_a3 = 0, scan_a4 = 0, scan_a3 = 0):
		self.copy_a4 = copy_a4
		self.copy_a3 = copy_a3
		self.print_a4 = print_a4
		self.print_a3 = print_a3
		self.scan_a4 = scan_a4
		self.scan_a3 = scan_a3

	def __str__(self):
		return '<UserStatistics c%u,%u p%u,%u s%u,%u>' % (self.copy_a4,
				self.copy_a3, self.print_a4, self.print_a3,
				self.scan_a4, self.scan_a3)

	def get_copy_a4_total(self):
		return self.copy_a4 + (self.copy_a3 * 2)

	def get_print_a4_total(self):
		return self.print_a4 + (self.print_a3 * 2)

	def get_scan_a4_total(self):
		return self.scan_a4 + (self.scan_a3 * 2)

	def to_xml(self):
		return """
			<statisticsInfo>
				<copyInfo>
					<monochrome>
						<singleSize>%u</singleSize>
						<doubleSize>%u</doubleSize>
					</monochrome>
				</copyInfo>
				<printerInfo>
					<monochrome>
						<singleSize>%u</singleSize>
						<doubleSize>%u</doubleSize>
					</monochrome>
				</printerInfo>
				<scannerInfo>
					<monochrome>
						<singleSize>%u</singleSize>
						<doubleSize>%u</doubleSize>
					</monochrome>
				</scannerInfo>
			</statisticsInfo>""" % (self.copy_a4,
				self.copy_a3, self.print_a4, self.print_a3,
				self.scan_a4, self.scan_a3)

	@staticmethod
	def from_xml(stats_node):
		assert stats_node.tagName == 'statisticsInfo'
		return UserStatistics(
				copy_a4 = int(_get_text_node(
					'copyInfo/monochrome/singleSize', stats_node)),
				copy_a3 = int(_get_text_node(
					'copyInfo/monochrome/doubleSize', stats_node)),
				print_a4 = int(_get_text_node(
					'printerInfo/monochrome/singleSize', stats_node)),
				print_a3 = int(_get_text_node(
					'printerInfo/monochrome/doubleSize', stats_node)),
				scan_a4 = int(_get_text_node(
					'scannerInfo/monochrome/singleSize', stats_node)),
				scan_a3 = int(_get_text_node(
					'scannerInfo/monochrome/doubleSize', stats_node)))


class UserRestrict(object):
	def __init__(self, grant_copy = False, grant_printer = False,
			grant_scanner = False, grant_storage = False):
		self.grant_copy = grant_copy
		self.grant_printer = grant_printer
		self.grant_scanner = grant_scanner
		self.grant_storage = grant_storage

	def __str__(self):
		return '<UserRestrict c%dp%ds%dst%d>' % (self.grant_copy,
				self.grant_printer, self.grant_scanner, self.grant_storage)

	def __avail_str(self, is_available):
		if is_available:
			return '<available/>'
		else:
			return '<restricted/>'

	def to_xml(self):
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

	@staticmethod
	def from_xml(restrict_node):
		assert restrict_node.tagName == 'restrictInfo'
		return UserRestrict(
				grant_copy = len(xpath.Evaluate(
						'copyInfo/monochrome/available', restrict_node)) == 1,
				grant_printer = len(xpath.Evaluate(
						'printerInfo/monochrome/available',
						restrict_node)) == 1,
				grant_scanner = len(xpath.Evaluate(
						'scannerInfo/scan/available', restrict_node)) == 1,
				grant_storage = len(xpath.Evaluate(
						'localStorageInfo/plot/available', restrict_node)) == 1)

class User(object):
	def __init__(self, user_code, name, restrict = None, stats = None):
		self.user_code = user_code
		self.name = name
		self.restrict = restrict
		self.stats = stats

	def __str__(self):
		return '<User "%s" (#%u, %s, %s)>' % (self.user_code, self.name,
				str(self.restrict), str(self.stats))

	def to_xml(self):
		encoded_name = _encode(self.name, STRING_ENCODING)
		if self.restrict is None:
			restr_str = ''
		else:
			restr_str = self.restrict.to_xml()
		if self.stats is None:
			stat_str = ''
		else:
			stat_str = self.stats.to_xml()
		return """<user version="1.1">
					<userCode>%u</userCode>
					<userType>general</userType>
					<userCodeName enc="%s">%s</userCodeName>
					%s
					%s
				</user>""" % (self.user_code, STRING_ENCODING, encoded_name,
					restr_str, stat_str)

	@staticmethod
	def from_xml(user_node):
		assert user_node.tagName == 'user' \
				and user_node.getAttribute('version') == '1.1'

		# Load data
		user_code = _get_text_node('userCode', user_node)
		if user_code == 'other':
			user_code = 0
			name = 'other'
		else:
			user_code = int(user_code)
			code_name_node = user_node.getElementsByTagName('userCodeName')[0]
			name = _decode(_get_text_node('.', code_name_node),
					code_name_node.getAttribute('enc'))

		# Load sub-data
		restrict_nodes = user_node.getElementsByTagName('restrictInfo')
		if len(restrict_nodes) == 0:
			restrict = None
		else:
			restrict = UserRestrict.from_xml(restrict_nodes[0])
		stats_nodes = user_node.getElementsByTagName('statisticsInfo')
		if len(stats_nodes) == 0:
			stats = None
		else:
			stats = UserStatistics.from_xml(stats_nodes[0])

		return User(user_code = user_code, name = name, restrict = restrict,
				stats = stats)

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
		""" % (user_code, u.to_xml())
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
		for user_node in xpath.Evaluate(
				'operationResult/getUserInfoResult/result/user', doc):
			u = User.from_xml(user_node)
			list.append((u.user_code, u.name, u.stats.print_a3,
					u.stats.print_a4, u.stats.copy_a3, u.stats.copy_a4))
		return list
