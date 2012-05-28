# vim:set ft=python ts=4 sw=4 et fileencoding=utf-8:

# aficio1075/delivery_input.py -- adapter for the XMLRPC and SOAP interfaces of
#   Ricoh Aficio 1075
#
# Copyright (C) 2008, 2010 Fabian Knittel <fabian.knittel@lettink.de>
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

import httplib
import codecs
import socket
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement
from aficio1075.security import encode_password
from aficio1075.encoding import encode, decode


def _get_text_node(path, base_node):
    return base_node.find(path).text

class DeliveryInputException:
    def __init__(self, reason):
        self.reason = reason
    def __str__(self):
        return self.reason

def soap_name(tag):
    return '{http://schemas.xmlsoap.org/soap/envelope/}%s' % tag

def di_name(tag):
    return '{http://www.ricoh.co.jp/xmlns/soap/rdh/deliveryinput}%s' % tag

def add_encoded_str_tags(parent, encoded_str):
    SubElement(parent, 'encoding').text = 'CHARENC_WINDOWS_1252'
    SubElement(parent, 'string').text = encoded_str

class DeliveryInput(object):
    def __init__(self, *args, **kwargs):
        self.__host = kwargs['host']
        self.__port = kwargs['port']

        self.__auth_cookie = None

    def _send_request(self, func_name, body):
        headers = {
            'Content-Type':'text/xml; charset=UTF-8',
            'SOAPAction':'http://www.ricoh.co.jp' \
                    '/xmlns/soap/rdh/deliveryinput#%s' % func_name}

        conn = httplib.HTTPConnection(self.__host, self.__port)
        conn.request("POST", "/DeliveryInput", body, headers)
        resp = conn.getresponse()

        doc = ET.XML(resp.read())
        return doc

    def _perform_operation(self, func_name, oper):
        base = Element(soap_name('Envelope'))
        base.attrib[soap_name('encodingStyle')] = \
                "http://schemas.xmlsoap.org/soap/encoding/"
        body = SubElement(base, soap_name('Body'))
        body.append(oper)

        xml_str = '<?xml version="1.0" encoding="UTF-8" ?>\n' + \
                ET.tostring(base)
        return self._send_request(func_name, xml_str)

    def authenticate(self, passwd):
        encoded_auth_token = encode_password(passwd)

        auth = Element(di_name('authenticate'))
        pw = SubElement(auth, 'password')
        add_encoded_str_tags(pw, encoded_auth_token)
        doc = self._perform_operation('authenticate', auth)

        if _get_text_node('.//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Authentication failed')

        self.__auth_cookie = _get_text_node('.//*/ticket_out/string', doc)

    def _ticket_xml(self):
        if self.__auth_cookie is None:
            raise DeliveryInputException('Authentication required needed')

        ticket = Element('ticket')
        add_encoded_str_tags(ticket, self.__auth_cookie)
        return ticket

    def _encoded_host_xml(self, host):
        if host is None:
            host_ip_addr = '0.0.0.0'
        else:
            host_ip_addr = socket.gethostbyname(host)

        encoded_host = encode(host_ip_addr)
        address = Element('address')
        add_encoded_str_tags(address, encoded_host)
        return address

    def set_delivery_service(self, host):
        """
        Set a new delivery service host. If the host differs from what the
        printer currently considers to be the delivery service host, the printer
        retrieves the delivery lists.
        """
        oper = Element(di_name('setDeliveryService'))
        oper.append(self._ticket_xml())
        oper.append(self._encoded_host_xml(host))

        cap = SubElement(oper, 'capability')
        SubElement(cap, 'commentSupported').text = 'false'
        SubElement(cap, 'directMailAddressSupported').text = 'false'
        SubElement(cap, 'mdnSupported').text = 'false'
        SubElement(cap, 'autoSynchronizeSupported').text = 'true'
        SubElement(cap, 'faxDeliverySupported').text = 'false'

        doc = self._perform_operation('setDeliveryService', oper)

        if _get_text_node('.//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Failed to configure delivery service')

    def get_delivery_service(self):
        oper = Element(di_name('getDeliveryService'))
        oper.append(self._ticket_xml())

        doc = self._perform_operation('getDeliveryService', oper)

        if _get_text_node('.//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Failed to configure delivery service')

        delivery_host_ip_addr = decode(
                _get_text_node('.//*/address_out/string', doc))

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
        oper = Element(di_name('synchronize'))
        oper.append(self._ticket_xml())

        SubElement(oper, 'generation').text = '%d' % generation_nr
        oper.append(self._encoded_host_xml(host))

        doc = self._perform_operation('synchronize', oper)

        if _get_text_node('.//*/returnValue', doc) != u'DIRC_OK':
            raise DeliveryInputException('Failed to configure delivery service')
