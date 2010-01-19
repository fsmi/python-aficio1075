# -*- coding: utf-8 -*-
# vim:set ft=python ts=4 sw=4 et:

# aficio1075/delivery_input.py -- adapter for the XMLRPC and SOAP interfaces of
#   Ricoh Aficio 1075
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
from xml.dom.ext.reader import Sax2
from xml import xpath
from aficio1075.security import encode_password
from aficio1075.encoding import encode, decode


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

    def authenticate(self, passwd):
        encoded_auth_token = encode_password(passwd)

        body = """
            <di:authenticate
                xmlns:di="http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput">
              <password>
                <encoding>CHARENC_WINDOWS_1252</encoding>
                <string>%s</string>
              </password>
            </di:authenticate>
        """ % encoded_auth_token
        doc = self._perform_operation('authenticate', body)

        if _get_text_node('//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Authentication failed')

        self.__auth_cookie = _get_text_node('//*/ticket_out/string', doc)

    def _ticket_xml(self):
        if self.__auth_cookie is None:
            raise DeliveryInputException('Authentication required needed')

        return """
              <ticket>
                <encoding>CHARENC_WINDOWS_1252</encoding>
                <string>%s</string>
              </ticket>
        """ % self.__auth_cookie

    def _encoded_host(self, host):
        if host is None:
            host_ip_addr = '0.0.0.0'
        else:
            host_ip_addr = socket.gethostbyname(host)

        encoded_host = encode(host_ip_addr)

        return """
              <address>
                <encoding>CHARENC_WINDOWS_1252</encoding>
                <string>%s</string>
              </address>
        """ % encoded_host

    def set_delivery_service(self, host):
        """
        Set a new delivery service host. If the host differs from what the
        printer currently considers to be the delivery service host, the printer
        retrieves the delivery lists.
        """
        body = """
            <di:setDeliveryService
                xmlns:di="http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput">
              %s
              %s
              <capability>
                <type>3</type>
                <commentSupported>false</commentSupported>
                <directMailAddressSupported>false</directMailAddressSupported>
                <mdnSupported>false</mdnSupported>
                <autoSynchronizeSupported>true</autoSynchronizeSupported>
                <faxDeliverySupported>false</faxDeliverySupported>
              </capability>
            </di:setDeliveryService>
        """ % (self._ticket_xml(), self._encoded_host(host))
        doc = self._perform_operation('setDeliveryService', body)

        if _get_text_node('//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Failed to configure delivery service')

    def get_delivery_service(self):
        body = """
            <di:getDeliveryService
                xmlns:di="http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput">
              %s
            </di:getDeliveryService>

        """ % self._ticket_xml()

        doc = self._perform_operation('getDeliveryService', body)

        if _get_text_node('//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Failed to configure delivery service')

        delivery_host_ip_addr = decode(
                _get_text_node('//*/address_out/string', doc))

        if delivery_host_ip_addr == '0.0.0.0':
            return None
        else:
            return socket.gethostbyaddr(delivery_host_ip_addr)[0]

    def synchronize(self, host, generation_nr):
        """
        Force the printer to retrieve the delivery lists from the indicated
        delivery service host.

        Current assumption: If the printer already knows the indicated
        generation number, it does nothing. (Apparently this isn't quite
        corrent, as the printer always checks for itsself, regardless of the
        generation number. Therefore the generation number appears to be
        unnecessary for this particular request.)
        """
        body = """
            <di:synchronize
                xmlns:di="http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput">
              %s
              <generation>%d</generation>
              %s
            </di:synchronize>
        """ % (self._ticket_xml(), generation_nr, self._encoded_host(host))
        doc = self._perform_operation('synchronize', body)

        if _get_text_node('//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Failed to configure delivery service')
