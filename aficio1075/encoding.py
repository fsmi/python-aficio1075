# vim:set ft=python ts=4 sw=4 et fileencoding=utf-8:

# aficio1075/encoding.py -- Provides common encoding and decoding mechanisms
#   needed for communication with Ricoh Aficio 1075 printers.
#
# Copyright (C) 2008 Fabian Knittel <fabian.knittel@lettink.de>
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
import codecs

DEFAULT_STRING_ENCODING = 'Windows-1252'

def decode(str, encoding=DEFAULT_STRING_ENCODING):
    if encoding == 'none' or encoding is None or encoding == '':
        return str
    else:
        return codecs.getdecoder(encoding)(b64decode(str))[0]

def encode(str, encoding=DEFAULT_STRING_ENCODING, error='ignore'):
    if encoding == 'none' or encoding is None or encoding == '':
        return str
    else:
        return b64encode(codecs.getencoder(encoding)(str, error)[0])
