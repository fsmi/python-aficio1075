# -*- coding: utf-8 -*-
# vim:set ft=python ts=4 sw=4 et:

# aficio1075/config_utils.py -- Support functions used for aficio1075.conf
#   parsing.
#
# Copyright (C) 2010 Fabian Knittel <fabian.knittel@avona.com>
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


CONFIG_PATH = '/etc/aficio1075.conf'

def list_to_dict(attr_name, list):
    d = {}
    for e in list:
        d[getattr(e, attr_name)] = e
    return d

def comma_string_to_list(s):
    return [e.strip() for e in s.split(',')]

def region_to_int_pair(s):
    start, end = s.split('-')
    return (int(start.strip()), int(end.strip()))

def str_to_code_regions(s):
    return [region_to_int_pair(region) for region in comma_string_to_list(s)]

def user_code_within_regions(code, regions):
    for region in regions:
        if code >= region[0] and code <= region[1]:
            return True
    return False
