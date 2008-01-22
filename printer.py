#!/usr/bin/python2.5
# -*- coding: utf-8 -*-
# vim:set ts=4 sw=4 noet:

# printer.py -- adapter for the XMLRPC and SOAP interfaces of Ricoh Aficio 1075
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

# Depends on python-httplib2, python-xml

import httplib2
import codecs
import socket
from base64 import b64encode, b64decode
from xml.dom.ext.reader import Sax2
from xml import xpath

def _get_text_node(path, node):
	return xpath.Evaluate('string(%s)' % path, node)

class Printer(object):
	def __init__(self, *args, **kwargs):
		self.__host = kwargs['host']
		self.__port = kwargs['port']

	def get_host(self):
		return self.__host
	host = property(get_host)

	def get_port(self):
		return self.__port
	port = property(get_port)

class PrinterException:
	def __init__(self, reason):
		self.reason = reason
	def __str__(self):
		return self.reason

class DeliveryInputException(PrinterException):
	pass

class DeliveryInput(object):
	def __init__(self, *args, **kwargs):
		self.__printer = kwargs['printer']

		self.__auth_cookie = None

	def _send_request(self, func_name, body):
		headers = {
			'Content-Type': 'text/xml; charset=UTF-8',
			'SOAPAction': 'http://www.ricoh.co.jp' \
					'/xmlns/soap/rdh/deliveryinput#%s' % func_name}
		uri = "http://%s:%d/DeliveryInput" % \
			(self.__printer.host, self.__printer.port)

		h = httplib2.Http()
		(result, content) = h.request(uri, "POST", body = body,
					headers = headers)

		reader = Sax2.Reader()
		doc = reader.fromString(content)
		return doc

	def _perform_operation(self, func_name, oper):
		body = """<?xml version="1.0" encoding="UTF-8" ?>
		<s:Envelope
		    xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"
		    s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
		  <s:Body>
			%s
		  </s:Body>
		</s:Envelope>
		""" % oper
		return self._send_request(func_name, body)

	def authenticate(self, auth_token):
		# Apparently, there's more voodoo to it than the below.
		#encoded_auth_token = \
		#	b64encode(codecs.getencoder('windows-1252')(auth_token)[0])
		encoded_auth_token = auth_token

		body = """
			<di:authenticate
		        xmlns:di="http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput">
		      <password>
		        <encoding>CHARENC_WINDOWS_1252</encoding>
		        <string>%s</string>
		      </password>
		    </di:authenticate>
		""" % auth_token
		doc = self._perform_operation('authenticate', body)

		if _get_text_node('//*/returnValue', doc) != u'DIRC_OK':
			raise DeliveryInputException('Authentication failed')

		self.__auth_cookie = _get_text_node('//*/ticket_out/string', doc)

	def set_delivery_service(self, host):
		if self.__auth_cookie is None:
			raise DeliveryInputException('Authentication required needed')

		host_ip_addr = socket.gethostbyname(host)
		encoded_host = \
			b64encode(codecs.getencoder('windows-1252')(host_ip_addr)[0])

		body = """
		    <di:setDeliveryService
		        xmlns:di="http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput">
		      <ticket>
		        <encoding>CHARENC_WINDOWS_1252</encoding>
			    <string>%s</string>
		      </ticket>
		      <address>
		        <encoding>CHARENC_WINDOWS_1252</encoding>
			    <string>%s</string>
		      </address>
		      <capability>
		        <type>3</type>
			    <commentSupported>false</commentSupported>
			    <directMailAddressSupported>false</directMailAddressSupported>
			    <mdnSupported>false</mdnSupported>
			    <autoSynchronizeSupported>true</autoSynchronizeSupported>
			    <faxDeliverySupported>false</faxDeliverySupported>
		      </capability>
		    </di:setDeliveryService>
		""" % (self.__auth_cookie, encoded_host)
		doc = self._perform_operation('setDeliveryService', body)

		if _get_text_node('//*/returnValue', doc) != u'DIRC_OK':
			raise DeliveryInputException('Failed to configure delivery service')


class UserMaintException(PrinterException):
	pass

class UserMaint(object):
	def __init__(self, *args, **kwargs):
		self.__printer = kwargs['printer']
		self.__auth_token = kwargs['auth_token']

	def _send_request(self, body):
		headers = {'Content-Type': 'text/xml;charset=us-ascii'}
		uri = "http://%s:%d/System/usermaint/" % \
			(self.__printer.host, self.__printer.port)

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

	def add_user(self, usercode, name):
		encoded_name = b64encode(codecs.getencoder('windows-1252')(name)[0])
		body = """<addUserRequest>
					<target>
						<userCode>%u</userCode>
					</target>
					<user version="1.1">
						<userCode>%u</userCode>
						<userType>general</userType>
						<userCodeName enc="Windows-1252">%s</userCodeName>
						<restrictInfo>
							<copyInfo>
								<monochrome><available/></monochrome>
							</copyInfo>
							<printerInfo>
								<monochrome><available/></monochrome>
							</printerInfo>
							<scannerInfo>
								<scan><available/></scan>
							</scannerInfo>
							<localStorageInfo>
								<plot><available/></plot>
							</localStorageInfo>
						</restrictInfo>
					</user>
				</addUserRequest>
		""" % (usercode, usercode, encoded_name)
		doc = self._perform_operation(body)

		success = _get_text_node(
				'operationResult/addUserResult/isSucceeded', doc) == 'true'
		if not success:
			error_code = _get_text_node(
				'operationResult/addUserResult/errorCode', doc)
			raise UserMaintException('failed to add user (code %s)' %\
					error_code)

	def delete_user(self, usercode):
		body = """<deleteUserRequest>
					<target>
						<userCode>%u</userCode>
					</target>
				</deleteUserRequest>
		""" % usercode
		doc = self._perform_operation(body)

		success = _get_text_node(
				'operationResult/deleteUserResult/isSucceeded', doc) == 'true'
		if not success:
			error_code = _get_text_node(
					'operationResult/deleteUserResult/errorCode', doc)
			raise UserMaintException('failed to delete user (code %s)' %\
					error_code)

	def user_counter(self, usercode=''):
		body = """<getUserInfoRequest>
					<target>
						<userCode>%s</userCode>
					</target>
					<user version="1.1">
						<userCode/>
						<userCodeName/>
						<statisticsInfo/>
					</user>
				</getUserInfoRequest>
		""" % usercode
		doc = self._perform_operation(body)

		success = _get_text_node(
				'operationResult/getUserInfoResult/isSucceeded', doc) == 'true'
		if not success:
			error_code = _get_text_node(
					'operationResult/getUserInfoResult/errorCode', doc)
			raise UserMaintException('failed to retrieve user info (code %s)' %\
					error_code)

		list = []
		# Iterate over the users.
		for user in xpath.Evaluate(
				'operationResult/getUserInfoResult/result/user', doc):
			usercode = _get_text_node('userCode', user)
			if usercode == 'other':
				usercode = 0
				name = 'other'
			else:
				usercode = int(usercode)
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
			list.append((usercode, name, print_a3_count, print_a4_count,
					copy_a3_count, copy_a4_count))
		return list
