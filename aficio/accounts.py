# -*- coding: utf-8 -*-
# vim:set ft=python ts=4 sw=4 noet:

# aficio/accounts.py -- Adapter for the XMLRPC interfaces of Ricoh Aficio 1075
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
		return codecs.getdecoder(encoding)(b64decode(str))[0]

def _encode(str, encoding = STRING_ENCODING):
	if encoding == 'none' or encoding is None or encoding == '':
		return str
	else:
		return b64encode(codecs.getencoder(encoding)(str)[0])

def _get_operation_result(doc, oper_name):
	success = _get_text_node(
			'operationResult/%s/isSucceeded' % oper_name, doc) == 'true'
	if success:
		return None
	else:
		error_code = _get_text_node(
			'operationResult/%s/errorCode' % oper_name, doc)
		return error_code

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

	def __repr__(self):
		return '<UserStatistics c%u,%u p%u,%u s%u,%u>' % (self.copy_a4,
				self.copy_a3, self.print_a4, self.print_a3,
				self.scan_a4, self.scan_a3)

	def get_copy_a4_total(self):
		return self.copy_a4 + (self.copy_a3 * 2)

	def get_print_a4_total(self):
		return self.print_a4 + (self.print_a3 * 2)

	def get_scan_a4_total(self):
		return self.scan_a4 + (self.scan_a3 * 2)

	def is_zero(self):
		return self.copy_a4 == 0 and self.copy_a3 == 0 and \
				self.print_a4 == 0 and self.print_a3 == 0 and \
				self.scan_a4 == 0 and self.scan_a3 == 0

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

	def __repr__(self):
		return '<UserRestrict c%dp%ds%dst%d>' % (self.grant_copy,
				self.grant_printer, self.grant_scanner, self.grant_storage)

	def __avail_str(self, is_available):
		if is_available:
			return '<available/>'
		else:
			return '<restricted/>'

	def revoke_all(self):
		"""Revoke all privileges."""
		self.grant_copy = False
		self.grant_printer = False
		self.grant_scanner = False
		self.grant_storage = False

	def has_any_permissions(self):
		"""Are there any granted permissions at all?"""
		return self.grant_copy or self.grant_printer or self.grant_scanner or \
				self.grant_storage

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

	def _set_user_code(self, user_code):
		if not hasattr(self, '_orig_user_code'):
			if hasattr(self, '_user_code'):
				self._orig_user_code = self._user_code
		self._user_code = user_code
	def _get_user_code(self):
		return self._user_code
	user_code = property(_get_user_code, _set_user_code)

	def _get_orig_user_code(self):
		"""Get the user code assigned to the user on the server-side."""
		if hasattr(self, '_orig_user_code'):
			return self._orig_user_code
		else:
			return self._user_code
	orig_user_code = property(_get_orig_user_code)

	def notify_flushed(self):
		"""Inform the object, that the data was flushed to the server."""
		if hasattr(self, '_orig_user_code'):
			del self._orig_user_code

	def _set_name(self, name):
		if len(name) > 20:
			self.__name = name[0:19]
		else:
			self.__name = name
	def _get_name(self):
		return self.__name
	name = property(_get_name, _set_name)

	def __repr__(self):
		return '<User "%s" (#%s, %s, %s)>' % (unicode(self.name),
				str(self.user_code), str(self.restrict), str(self.stats))

	def to_xml(self):
		xml_str = """<user version="1.1">
					<userType>general</userType>"""
		if self.user_code is not None:
			xml_str += '<userCode>%u</userCode>' % self.user_code
		if self.name is not None:
			encoded_name = _encode(self.name, STRING_ENCODING)
			xml_str += '<userCodeName enc="%s">%s</userCodeName>' % (
					STRING_ENCODING, encoded_name)
		if self.restrict is not None:
			xml_str += self.restrict.to_xml()
		xml_str += '</user>'
		return xml_str

	@staticmethod
	def from_xml(user_node):
		assert user_node.tagName == 'user' \
				and user_node.getAttribute('version') == '1.1'

		# Load user code (if available)
		user_code_nodes = user_node.getElementsByTagName('userCode')
		if len(user_code_nodes) == 0:
			user_code = None
		else:
			user_code = _get_text_node('.', user_code_nodes[0])
			# 'other' is a special case.
			if user_code == 'other':
				user_code = 0
				name = 'other'
			else:
				user_code = int(user_code)
				# Load user code name (if available)
				code_name_nodes = user_node.getElementsByTagName('userCodeName')
				if len(code_name_nodes) == 0:
					name = None
				else:
					name = _decode(_get_text_node('.', code_name_nodes[0]),
							code_name_nodes[0].getAttribute('enc'))

		# Load sub-data (if available)
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
	def __init__(self, auth_token, host, port = 80):
		self.auth_token = auth_token
		self.host = host
		self.port = port

	def _send_request(self, body):
		headers = {'Content-Type': 'text/xml;charset=us-ascii'}
		uri = "http://%s:%d/System/usermaint/" % \
			(self.host, self.port)

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
		""" % (self.auth_token, oper)
		return self._send_request(body)

	def add_user(self, user):
		"""Add a user account."""
		body = """<addUserRequest>
					<target>
						<userCode>%u</userCode>
					</target>
					%s
				</addUserRequest>
		""" % (user.user_code, user.to_xml())
		doc = self._perform_operation(body)

		error_code = _get_operation_result(doc, 'addUserResult')
		if error_code is not None:
			raise UserMaintException('failed to add user (code %s)' %\
					error_code)
		user.notify_flushed()

	def delete_user(self, user_code):
		"""Delete a user account."""
		body = """<deleteUserRequest>
					<target>
						<userCode>%u</userCode>
					</target>
				</deleteUserRequest>
		""" % user_code
		doc = self._perform_operation(body)

		error_code = _get_operation_result(doc, 'deleteUserResult')
		if error_code is not None:
			raise UserMaintException('failed to delete user (code %s)' %\
					error_code)

	def get_user_info(self, user_code='', req_user_code = True,
			req_user_code_name = True, req_restrict_info = True,
			req_statistics_info = True):
		"""Get information about a user account."""
		body = """<getUserInfoRequest>
					<target>
						<userCode>%s</userCode>
					</target>
					<user version="1.1">""" % user_code
		if req_user_code:
			body += '<userCode/>'
		if req_user_code_name:
			body += '<userCodeName/>'
		if req_restrict_info:
			body += '<restrictInfo/>'
		if req_statistics_info:
			body += '<statisticsInfo/>'
		body += """</user>
				</getUserInfoRequest>"""
		doc = self._perform_operation(body)

		error_code = _get_operation_result(doc, 'getUserInfoResult')
		if error_code is not None:
			raise UserMaintException('failed to retrieve user info (code %s)' %\
					error_code)

		users = {}
		# Iterate over the users.
		for user_node in xpath.Evaluate(
				'operationResult/getUserInfoResult/result/user', doc):
			user = User.from_xml(user_node)
			users[user.user_code] = user
		return users

	def set_user_info(self, user):
		"""Modify a user account."""
		body = """<setUserInfoRequest>
					<target>
						<userCode>%u</userCode>
						<deviceId></deviceId>
					</target>
					%s
				</setUserInfoRequest>""" % (user.orig_user_code, user.to_xml())
		doc = self._perform_operation(body)

		error_code = _get_operation_result(doc, 'setUserInfoResult')
		if error_code is not None:
			raise UserMaintException('failed to modify user (code %s)' %\
					error_code)
		user.notify_flushed()
