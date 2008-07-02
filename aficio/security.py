# -*- coding: utf-8 -*-
# vim:set ft=python ts=4 sw=4 noet:

# aficio/security.py -- Password encryption and decryption used by the Ricoh
#   Aficio 1075.
#
# Copyright (C) 2008 Philipp Kern <philipp.kern@fsmi.uni-karlsruhe.de>
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

from base64 import b64encode, b64decode

MIN_PW_LEN = 3
MAX_PW_LEN = 8

class PasswordError(RuntimeError):
	pass

def _encode_char(c):
	val = ord(c)
	return chr((val >> 2) | ((val & (2**1 + 2**0)) << 6))

def _decode_char(c):
	val = ord(c)
	return chr(((val << 2) | ((val & (2**6 + 2**7)) >> 6)) & 0xff)

def _mangle_password(str, func):
	return ''.join(map(lambda x: func(x), str))

def decode_password(data):
	return _mangle_password(b64decode(data), _decode_char)

def encode_password(passwd):
	if len(passwd) < MIN_PW_LEN:
		raise PasswordError('Password too short; must have at least %u '
				'characters' % MIN_PW_LEN)
	if len(passwd) > MAX_PW_LEN:
		raise PasswordError('Password too long; must not exceed %u '
				'characters' % MAX_PW_LEN)
	return b64encode(mangle_password(passwd, _encode_char))
