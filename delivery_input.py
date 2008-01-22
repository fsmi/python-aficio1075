#!/usr/bin/python2.5
# -*- coding: utf-8 -*-
# vim:set ts=4 sw=4 noet:

# delivery_input.py -- adapter for the XMLRPC and SOAP interfaces of Ricoh
#                      Aficio 1075
#
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


def _get_text_node(path, node):
	return xpath.Evaluate('string(%s)' % path, node)

class DeliveryInputException:
	def __init__(self, reason):
		self.reason = reason
	def __str__(self):
		return self.reason

class DeliveryInput(object):
	def __init__(self, *args, **kwargs):
		self.__host = kwargs['host']
		self.__port = kwargs['port']

		self.__auth_cookie = None

	def _send_request(self, func_name, body):
		headers = {
			'Content-Type': 'text/xml; charset=UTF-8',
			'SOAPAction': 'http://www.ricoh.co.jp' \
					'/xmlns/soap/rdh/deliveryinput#%s' % func_name}
		uri = "http://%s:%d/DeliveryInput" % \
			(self.__host, self.__port)

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
