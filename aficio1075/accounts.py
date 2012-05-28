# vim:set ft=python ts=4 sw=4 et fileencoding=utf-8:
"""
Adapter for the XMLRPC account management interfaces of Ricoh Aficio 1075
printers.

Provides :class:`UserMaintSession` which allows :class:`User`s to be queried,
added, modified and deleted.  A user has associated :class:`UserStatistics` and
:class:`UserRestrict` instances, which represent printer statistics and access
restrictions (respectively).
"""
# Copyright (C) 2007 Philipp Kern <philipp.kern@fsmi.uni-karlsruhe.de>
# Copyright (C) 2008, 2010, 2012 Fabian Knittel <fabian.knittel@lettink.de>
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
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement
import time
from aficio1075 import security
from aficio1075.encoding import encode, decode, DEFAULT_STRING_ENCODING


def _get_text_node(path, base_node):
    if base_node is None:
        return None
    node = base_node.find(path)
    if node is None:
        return None
    return node.text

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
    """This class represents a set of print operation statistics.

    `copy_a4` is the number of performed copies of size A4.  Same for `copy_a3`
    only for size A3.

    `print_a4` and `print_a3` note the number of prints and `scan_a4` and
    `scan_a3` note the number of scans.

    It supports serialisation to and deserialisation from XML using
    :meth:`to_xml` and :meth:`from_xml`.

    The class tracks whether it was modified, using the `modified` attribute.
    Class users need to reset `modified` as needed.
    """
    def __init__(self, copy_a4=0, copy_a3=0, print_a4=0,
            print_a3=0, scan_a4=0, scan_a3=0):
        self._copy_a4 = copy_a4
        self._copy_a3 = copy_a3
        self._print_a4 = print_a4
        self._print_a3 = print_a3
        self._scan_a4 = scan_a4
        self._scan_a3 = scan_a3
        self.modified = True

    def __repr__(self):
        return '<UserStatistics c%u,%u p%u,%u s%u,%u %s>' % (self.copy_a4,
                self.copy_a3, self.print_a4, self.print_a3,
                self.scan_a4, self.scan_a3,
                'modified' if self.modified else 'unmodified')

    def set_zero(self):
        """Resets all counters to zero.
        """
        # Note: The properties implicitly set the modified flag.
        self.copy_a4 = 0
        self.copy_a3 = 0
        self.print_a4 = 0
        self.print_a3 = 0
        self.scan_a4 = 0
        self.scan_a3 = 0

    def get_copy_a4(self):
        """Holds the number of A4 copies created."""
        return self._copy_a4
    def set_copy_a4(self, val):
        self.modified = True
        self._copy_a4 = val
    copy_a4 = property(get_copy_a4, set_copy_a4)

    def get_copy_a3(self):
        """Holds the number of A3 copies created."""
        return self._copy_a3
    def set_copy_a3(self, val):
        self.modified = True
        self._copy_a3 = val
    copy_a3 = property(get_copy_a3, set_copy_a3)

    def get_print_a4(self):
        """Holds the number of A4 prints created."""
        return self._print_a4
    def set_print_a4(self, val):
        self.modified = True
        self._print_a4 = val
    print_a4 = property(get_print_a4, set_print_a4)

    def get_print_a3(self):
        """Holds the number of A3 prints created."""
        return self._print_a3
    def set_print_a3(self, val):
        self.modified = True
        self._print_a3 = val
    print_a3 = property(get_print_a3, set_print_a3)

    def get_scan_a4(self):
        """Holds the number of A4 scans created."""
        return self._scan_a4
    def set_scan_a4(self, val):
        self.modified = True
        self._scan_a4 = val
    scan_a4 = property(get_scan_a4, set_scan_a4)

    def get_scan_a3(self):
        """Holds the number of A3 scans created."""
        return self._scan_a3
    def set_scan_a3(self, val):
        self.modified = True
        self._scan_a3 = val
    scan_a3 = property(get_scan_a3, set_scan_a3)

    @property
    def copy_a4_total(self):
        """Total number of copies created, calculcated in A4 equivalents. (One
        A3 page is counted as two A4 pages.)
        """
        return self.copy_a4 + (self.copy_a3 * 2)

    @property
    def print_a4_total(self):
        """Total number of prints created, calculcated in A4 equivalents. (One
        A3 page is counted as two A4 pages.)
        """
        return self.print_a4 + (self.print_a3 * 2)

    @property
    def scan_a4_total(self):
        """Total number of scans created, calculcated in A4 equivalents. (One
        A3 page is counted as two A4 pages.)
        """
        return self.scan_a4 + (self.scan_a3 * 2)

    def is_zero(self):
        """Returns ``True`` in case all page counters are zero.
        """
        return self.copy_a4_total == 0 and \
                self.print_a4_total == 0 and \
                self.scan_a4_total == 0

    @staticmethod
    def from_xml(stats_node):
        assert stats_node.tag == 'statisticsInfo'
        stats = UserStatistics(
                copy_a4=int(_get_text_node(
                    'copyInfo/monochrome/singleSize', stats_node)),
                copy_a3=int(_get_text_node(
                    'copyInfo/monochrome/doubleSize', stats_node)),
                print_a4=int(_get_text_node(
                    'printerInfo/monochrome/singleSize', stats_node)),
                print_a3=int(_get_text_node(
                    'printerInfo/monochrome/doubleSize', stats_node)),
                scan_a4=int(_get_text_node(
                    'scannerInfo/monochrome/singleSize', stats_node)),
                scan_a3=int(_get_text_node(
                    'scannerInfo/monochrome/doubleSize', stats_node)))
        stats.modified = False
        return stats

    @staticmethod
    def _sub_info_to_xml(parent_node, single_val, double_val):
        mono = SubElement(parent_node, 'monochrome')
        SubElement(mono, 'singleSize').text = '%u' % single_val
        SubElement(mono, 'doubleSize').text = '%u' % double_val

    def to_xml(self):
        stats_node = Element('statisticsInfo')
        self._sub_info_to_xml(SubElement(stats_node, 'copyInfo'),
                self.copy_a4, self.copy_a3)
        self._sub_info_to_xml(SubElement(stats_node, 'printerInfo'),
                self.print_a4, self.print_a3)
        self._sub_info_to_xml(SubElement(stats_node, 'scannerInfo'),
                self.scan_a4, self.scan_a3)
        return stats_node


class UserRestrict(object):
    """This class represents a set of access restrictions.

    If `grant_copy` is ``True``, then use of the printer's copy function is
    granted.
    If `grant_printer` is ``True``, then use of the printer's print function is
    granted.
    If `grant_scanner` is ``True``, then use of the printer's scan function is
    granted.
    If `grant_storage` is ``True``, then use of the printer's document storage
    function is granted.

    It supports serialisation to and deserialisation from XML using
    :meth:`to_xml` and :meth:`from_xml`.
    """
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
        def _avail(parent, is_available):
            if is_available:
                return SubElement(parent, 'available')
            else:
                return SubElement(parent, 'restricted')

        restrict_node = Element('restrictInfo')
        _avail(SubElement(SubElement(restrict_node, 'copyInfo'),
                'monochrome'), self.grant_copy)
        _avail(SubElement(SubElement(restrict_node, 'printerInfo'),
                'monochrome'), self.grant_printer)
        _avail(SubElement(SubElement(restrict_node, 'scannerInfo'),
                'scan'), self.grant_scanner)
        _avail(SubElement(SubElement(restrict_node, 'localStorageInfo'),
                'plot'), self.grant_storage)
        return restrict_node

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
    """This class represents a single user in the printer's user accounting.  It
    can have a user name `name`, a user code `user_code`, a set of access
    restrictions `restrict` of type :class:`UserRestrict` and printing
    statistics of type :class:`UserStatistics` associated with itsself.

    It supports serialisation to and deserialisation from XML using
    :meth:`to_xml` and :meth:`from_xml`.
    """

    MAX_NAME_LEN = 20

    def __init__(self, user_code, name, restrict=None, stats=None):
        self.user_code = user_code
        self.name = name
        self.restrict = restrict
        self.stats = stats

    def _set_user_code(self, user_code):
        if not hasattr(self, '_orig_user_code'):
            # Remember the original user code, as currently known to the
            # printer, so that any changes can be properly associated with that
            # user code.
            if hasattr(self, '_user_code'):
                self._orig_user_code = self._user_code
        self._user_code = user_code
    def _get_user_code(self):
        """The account's user code property."""
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
            # The server now knows of the updated user code.
            del self._orig_user_code
        if self.stats is not None and self.stats.modified:
            self.stats.modified = False

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
        user = Element('user', version='1.1')
        if self.user_code is not None:
            # 'other' is a special case.
            if self.user_code == 0:
                user_code_str = 'other'
                SubElement(user, 'userType').text = 'other'
            else:
                user_code_str = '%u' % self.user_code
                SubElement(user, 'userType').text = 'general'
            SubElement(user, 'userCode').text = user_code_str
        if self.name is not None:
            SubElement(user, 'userCodeName', enc=DEFAULT_STRING_ENCODING)\
                    .text = encode(self.name, DEFAULT_STRING_ENCODING)
        if self.restrict is not None:
            user.append(self.restrict.to_xml())
        if self.stats is not None and self.stats.modified:
            user.append(self.stats.to_xml())
        return user

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

        doc = ET.XML(resp.read())
        return doc

    def _perform_operation(self, oper):
        base = Element('operation')
        SubElement(base, 'authorization').text = \
                security.encode_password(self.passwd)
        base.append(oper)

        body = "<?xml version='1.0' encoding='us-ascii'?>\n" + \
                ET.tostring(base)
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
        """Add object `user` of type :class:`User` as user account."""
        req = Element('addUserRequest')
        target = SubElement(req, 'target')
        SubElement(target, 'userCode').text = '%u' % user.user_code
        req.append(user.to_xml())

        doc, error_code = self._perform_checked_operation(req, 'addUserResult')
        if error_code is not None:
            raise UserMaintError('failed to add user (code %s)' %\
                    error_code, code=error_code)
        user.notify_flushed()

    def delete_user(self, user_code):
        """Delete user account with user code number `user_code`."""
        req = Element('deleteUserRequest')
        target = SubElement(req, 'target')
        SubElement(target, 'userCode').text = '%u' % user_code
        doc, error_code = self._perform_checked_operation(req,
                'deleteUserResult')
        if error_code is not None:
            raise UserMaintError('failed to delete user (code %s)' %\
                    error_code)

    def get_user_info(self, user_code, req_user_code=True,
            req_user_code_name=True, req_restrict_info=True,
            req_statistics_info=True):
        """Get information about user account with user code number `user_code`.
        Returns a :class:`User` instance in case the user was found or else
        throws :class:`UserMaintError`.
        If `req_user_code` is ``True``, the user's user code is requested.
        If `req_user_code_name` is ``True``, the user's name is requested.
        If `req_restrict_info` is ``True``, the user's access restrictions are
        requested.
        If `req_statistics_info` is ``True``, the user's printing statistics are
        requested.
        """
        return self._get_user_info(user_code=user_code,
                req_user_code=req_user_code,
                req_user_code_name=req_user_code_name,
                req_restrict_info=req_restrict_info,
                req_statistics_info=req_statistics_info)[0]

    def get_user_infos(self, req_user_code=True,
            req_user_code_name=True, req_restrict_info=True,
            req_statistics_info=True):
        """Request information about all user accounts.
        Returns a list of :class:`User` instances. Throws
        :class:`UserMaintError` in case of an error.
        If `req_user_code` is ``True``, the users' user codes are requested.
        If `req_user_code_name` is ``True``, the users' names are requested.
        If `req_restrict_info` is ``True``, the users' access restrictions are
        requested.
        If `req_statistics_info` is ``True``, the users' printing statistics are
        requested.
        """
        return self._get_user_info(req_user_code=req_user_code,
                req_user_code_name=req_user_code_name,
                req_restrict_info=req_restrict_info,
                req_statistics_info=req_statistics_info)

    def _get_user_info(self, user_code='', req_user_code=True,
            req_user_code_name=True, req_restrict_info=True,
            req_statistics_info=True):
        req = Element('getUserInfoRequest')
        target = SubElement(req, 'target')
        # 'other' is a special case.
        if user_code == 0:
            user_code_str = 'other'
        else:
            user_code_str = str(user_code)
        SubElement(target, 'userCode').text = user_code_str

        user = SubElement(req, 'user', version='1.1')

        if req_user_code:
            SubElement(user, 'userCode')
        if req_user_code_name:
            SubElement(user, 'userCodeName')
        if req_restrict_info:
            SubElement(user, 'restrictInfo')
        if req_statistics_info:
            SubElement(user, 'statisticsInfo')

        doc, error_code = self._perform_checked_operation(req,
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
        """Modify user account associated with `user`, which is an instance of
        :class:`User`.
        Throws :class:`UserMaintError` in case of an error.
        """
        req = Element('setUserInfoRequest')
        target = SubElement(req, 'target')
        # 'other' is a special case.
        if user.orig_user_code == 0:
            user_code_str = 'other'
        else:
            user_code_str = str(user.orig_user_code)
        SubElement(target, 'userCode').text = user_code_str
        SubElement(target, 'deviceId')
        req.append(user.to_xml())

        doc, error_code = self._perform_checked_operation(req,
                'setUserInfoResult')
        if error_code is not None:
            raise UserMaintError('failed to modify user (code %s)' % \
                    error_code)
        user.notify_flushed()
