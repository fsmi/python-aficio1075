# vim:set ft=python ts=4 sw=4 et encoding=utf-8:

# aficio1075/accounts.py -- Adapter for the XMLRPC interfaces of Ricoh Aficio
#   1075 concerning account management.
#
# Copyright (C) 2007 Philipp Kern <philipp.kern@fsmi.uni-karlsruhe.de>
# Copyright (C) 2008, 2010 Fabian Knittel <fabian.knittel@avona.com>
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

import httplib
import codecs
from xml.etree.ElementTree import XML
import time
from aficio1075 import security
from aficio1075.encoding import encode, decode, DEFAULT_STRING_ENCODING


def _get_text_node(path, base_node):
    return base_node.find(path).text

def _get_operation_result(operation_node, oper_name):
    if operation_node.tag != 'operationResult':
        return 'unknown failure'

    success = _get_text_node(
            '%s/isSucceeded' % oper_name, operation_node) == 'true'
    if success:
        return None
    else:
        result_node = operation_node.find(oper_name)
        if result_node is None:
            result_node = operation_node.find('serverError')
            if result_node is None:
                return 'unknown failure'

        error_code = _get_text_node('errorCode', result_node)
        return error_code

class UserMaintError(RuntimeError):
    def __init__(self, msg, code=None):
        RuntimeError.__init__(self, msg)
        self.code = code

class UserStatistics(object):
    def __init__(self, copy_a4=0, copy_a3=0, print_a4=0,
            print_a3=0, scan_a4=0, scan_a3=0):
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

    @property
    def copy_a4_total(self):
        return self.copy_a4 + (self.copy_a3 * 2)

    @property
    def print_a4_total(self):
        return self.print_a4 + (self.print_a3 * 2)

    @property
    def scan_a4_total(self):
        return self.scan_a4 + (self.scan_a3 * 2)

    def is_zero(self):
        return self.copy_a4_total == 0 and \
                self.print_a4_total == 0 and \
                self.scan_a4_total == 0

    @staticmethod
    def from_xml(stats_node):
        assert stats_node.tag == 'statisticsInfo'
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


def _avail_str(is_available):
    if is_available:
        return '<available/>'
    else:
        return '<restricted/>'

class UserRestrict(object):
    def __init__(self, grant_copy=False, grant_printer=False,
            grant_scanner=False, grant_storage=False):
        self.grant_copy = grant_copy
        self.grant_printer = grant_printer
        self.grant_scanner = grant_scanner
        self.grant_storage = grant_storage

    def __repr__(self):
        return '<UserRestrict c%dp%ds%dst%d>' % (self.grant_copy,
                self.grant_printer, self.grant_scanner, self.grant_storage)

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
        return """\
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
            </restrictInfo>""" % (
                    _avail_str(self.grant_copy),
                    _avail_str(self.grant_printer),
                    _avail_str(self.grant_scanner),
                    _avail_str(self.grant_storage))

    @staticmethod
    def from_xml(restrict_node):
        assert restrict_node.tag == 'restrictInfo'
        return UserRestrict(
                grant_copy=restrict_node.find(
                        'copyInfo/monochrome/available') is not None,
                grant_printer=restrict_node.find(
                        'printerInfo/monochrome/available') is not None,
                grant_scanner=restrict_node.find(
                        'scannerInfo/scan/available') is not None,
                grant_storage=restrict_node.find(
                        'localStorageInfo/plot/available') is not None)

class User(object):
    MAX_NAME_LEN = 20

    def __init__(self, user_code, name, restrict=None, stats=None):
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
        if len(name) > self.MAX_NAME_LEN:
            raise UserMaintError('user name "%s" too long, max %d ' \
                    'characters' % (name, self.MAX_NAME_LEN))
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
            encoded_name = encode(self.name, DEFAULT_STRING_ENCODING)
            xml_str += '<userCodeName enc="%s">%s</userCodeName>' % (
                    DEFAULT_STRING_ENCODING, encoded_name)
        if self.restrict is not None:
            xml_str += self.restrict.to_xml()
        xml_str += '</user>'
        return xml_str

    @staticmethod
    def from_xml(user_node):
        assert user_node.tag == 'user' and \
                user_node.attrib['version'] == '1.1'

        # Load user code (if available)
        user_code_node = user_node.find('userCode')
        if user_code_node is None:
            user_code = None
        else:
            user_code = user_code_node.text
            # 'other' is a special case.
            if user_code == 'other':
                user_code = 0
                name = 'other'
            else:
                user_code = int(user_code)
                # Load user code name (if available)
                code_name_node = user_node.find('userCodeName')
                if code_name_node is None:
                    name = None
                else:
                    name = decode(code_name_node.text,
                            code_name_node.attrib['enc'])

        # Load sub-data (if available)
        restrict_node = user_node.find('restrictInfo')
        if restrict_node is None:
            restrict = None
        else:
            restrict = UserRestrict.from_xml(restrict_node)
        stats_node = user_node.find('statisticsInfo')
        if stats_node is None:
            stats = None
        else:
            stats = UserStatistics.from_xml(stats_node)

        return User(user_code=user_code, name=name, restrict=restrict,
                stats=stats)

class UserMaintSession(object):
    """
    Objects of this class represent a user maintainance session. They provide
    methods to retrieve and modify user accounts.

    There is no session on the network level: Each request initiates a
    self-contained XML-RPC request.
    """
    BUSY_CODE = 'systemBusy'

    def __init__(self, passwd, host, port=80, retry_busy=False):
        self.passwd = passwd
        self.host = host
        self.port = port
        self.retry_busy = retry_busy

    def _send_request(self, body):
        headers = {'Content-Type': 'text/xml;charset=us-ascii'}

        conn = httplib.HTTPConnection(self.host, self.port)
        conn.request("POST", "/System/usermaint/", body, headers)
        resp = conn.getresponse()

        doc = XML(resp.read())
        return doc

    def _perform_operation(self, oper):
        body = """<?xml version='1.0' encoding='us-ascii'?>
            <operation>
                <authorization>%s</authorization>
            %s
            </operation>
        """ % (security.encode_password(self.passwd), oper)
        return self._send_request(body)

    def _perform_checked_operation(self, oper, result_name):
        # In case we retry on busy, loop until we get a non-busy error code.
        # Otherwise just exit.
        while True:
            doc = self._perform_operation(oper)
            error_code = _get_operation_result(doc, result_name)
            if not self.retry_busy or error_code != self.BUSY_CODE:
                return (doc, error_code)
            time.sleep(0.2)

    def add_user(self, user):
        """Add a user account."""
        body = """<addUserRequest>
                    <target>
                        <userCode>%u</userCode>
                    </target>
                    %s
                </addUserRequest>
        """ % (user.user_code, user.to_xml())
        doc, error_code = self._perform_checked_operation(body, 'addUserResult')
        if error_code is not None:
            raise UserMaintError('failed to add user (code %s)' %\
                    error_code, code=error_code)
        user.notify_flushed()

    def delete_user(self, user_code):
        """Delete a user account."""
        body = """<deleteUserRequest>
                    <target>
                        <userCode>%u</userCode>
                    </target>
                </deleteUserRequest>
        """ % user_code
        doc, error_code = self._perform_checked_operation(body,
                'deleteUserResult')
        if error_code is not None:
            raise UserMaintError('failed to delete user (code %s)' %\
                    error_code)

    def get_user_info(self, user_code, req_user_code=True,
            req_user_code_name=True, req_restrict_info=True,
            req_statistics_info=True):
        """Get information about a user account.
        Returns a User instance in case the user was found or else throws a
        UserMaintError."""
        return self._get_user_info(user_code, req_user_code, req_user_code_name,
                req_restrict_info, req_statistics_info)[0]

    def get_user_infos(self, req_user_code=True,
            req_user_code_name=True, req_restrict_info=True,
            req_statistics_info=True):
        """Request information about all user accounts.
        Returns a list of User instances. Throws a UserMaintError in case of an
        error."""
        return self._get_user_info(req_user_code=req_user_code,
                req_user_code_name=req_user_code_name,
                req_restrict_info=req_restrict_info,
                req_statistics_info=req_statistics_info)

    def _get_user_info(self, user_code='', req_user_code=True,
            req_user_code_name=True, req_restrict_info=True,
            req_statistics_info=True):
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
        doc, error_code = self._perform_checked_operation(body,
                'getUserInfoResult')
        if error_code is not None:
            raise UserMaintError('failed to retrieve user info (code %s)' %\
                    error_code)

        users = []
        # Iterate over the users.
        for user_node in doc.findall('getUserInfoResult/result/user'):
            users.append(User.from_xml(user_node))
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
        doc, error_code = self._perform_checked_operation(body,
                'setUserInfoResult')
        if error_code is not None:
            raise UserMaintError('failed to modify user (code %s)' % \
                    error_code)
        user.notify_flushed()
