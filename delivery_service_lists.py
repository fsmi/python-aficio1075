#!/usr/bin/python2.5
# -*- coding: utf-8 -*-
# vim:set ts=4 sw=4 noet:

# delivery_service_lists.py.py -- classes to read and write the Ricoh Aficio
#                                 1075 delivery service target lists.
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

import struct
import sys
import os

class UnpackBufException(Exception):
	pass

class UnpackBuf(object):
	def __init__(self, data):
		self.data = data
		self.cnt = 0

	def unpack(self, fmt):
		l = struct.calcsize(fmt)
		if self.cnt + l > len(self.data):
			raise UnpackBufException('not enough buffer left for unpacking '
					'(left %d, wanted %d)' % (len(self.data) - self.cnt, l))
		ret = struct.unpack(fmt, self.data[self.cnt : self.cnt + l])
		self.cnt += l
		return ret

class GroupException(Exception):
	pass

class GroupColumn(object):
	def __init__(self, nr, name):
		self.nr = nr
		self.name = name
	def __repr__(self):
		return "GroupColumn(nr = %d, name = '%s')" % (self.nr, self.name)

class Group(object):
	def __init__(self, short_columns = True, columns = []):
		self.short_columns = short_columns
		self._calc_max_columns()
		self.__columns = columns

	def __repr__(self):
		return "GroupColumn(short_columns = %s, columns = %s)" % \
				(str(self.short_columns), str(self.__columns))

	def _calc_max_columns(self):
		if self.short_columns:
			self.max_columns = 10
		else:
			self.max_columns = 5


	def add_column(self, column):
		if len(self.__columns) > self.max_columns:
			raise GroupException('Maximum number of columns in group exceeded')

		self.__columns.append(column)

	def dump(self):
		if self.short_columns:
			data = struct.pack(">L", 0xb)
		else:
			data = struct.pack(">L", 0x6)

		data += struct.pack(">L  4x  2x B B", 0x2, 0x80, 0x1) + \
		        struct.pack(">4s  B 3x  12x", 'Freq', 0x2e)

		for col in self.__columns:
			if self.short_columns:
				data += struct.pack(">L 4s 16x", col.nr, col.name)
			else:
				data += struct.pack(">L 8s 12x", col.nr, col.name)

		return data

	def load(self, data):
		data = UnpackBuf(data)

		flag, = data.unpack(">L")
		if flag == 0xb:
			self.short_columns = True
		elif flag == 0x6:
			self.short_columns = False
		else:
			raise GroupException('Unknown column format (0x%x)' % flag)
		self._calc_max_columns()

		# Skip various magic bytes.
		data.unpack("32x")

		self.__columns = []
		for i in range(1, self.max_columns):
			if self.short_columns:
				nr, name = data.unpack(">L 4s 16x")
			else:
				nr, name = data.unpack(">L 8s 12x")
			self.add_column(GroupColumn(nr, name))


	def _file_path(self, base_path, printer_mac, generation_nr):
		return os.path.join(
			os.path.join(base_path, 'Address'),
			"D%s.%d.grp" % (printer_mac, generation_nr))

	def dump_file(self, base_path, printer_mac, generation_nr):
		f = open(self._file_path(base_path, printer_mac, generation_nr), 'wb')
		f.write(self.dump())

	def load_file(self, base_path, printer_mac, generation_nr):
		f = open(self._file_path(base_path, printer_mac, generation_nr), 'rb')
		self.load(f.read())

	def load_config(self, config_file, section_name):
		self.short_columns = \
				config_file.getboolean(section_name, 'short_columns')
		self._calc_max_columns()

		self.__columns = []
		for nr in range(1, self.max_columns):
			name = config_file.get(section_name, 'col%d' % nr)
			self.add_column(GroupColumn(nr, name))

class IdentifierException(Exception):
	pass

class IdentifierEntry(object):
	def __init__(self, id, use_frequently, group_nr, name):
		self.id = id
		self.use_frequently = use_frequently
		self.group_nr = group_nr
		self.name = name

	def __repr__(self):
		return "IdentifierEntry(id = %d, use_frequently = %s, " \
			"group_nr = %d, name ='%s')" % \
			(self.id, str(self.use_frequently), self.group_nr, self.name)

class Identifiers(object):
	def __init__(self, revision_nr = 1, entries = []):
		self.revision_nr = revision_nr
		self.__entries = entries

	def __repr__(self):
		return "Identifier(revision_nr = %d, entries = %s)" % \
				(self.revision_nr, str(self.__entries))

	def add_entry(self, entry):
		self.__entries.append(entry)

	def dump(self):
		data = struct.pack(">L 4x L", len(self.__entries), self.revision_nr)

		for entry in self.__entries:
			data += struct.pack(">L", entry.id)
			if entry.use_frequently:
				data += struct.pack(">H", 0x8001)
			else:
				data += struct.pack(">H", 0x0000)
			data += struct.pack(">H 4x 7x B 16s", entry.group_nr, 0x2,
						entry.name)

		return data

	def load(self, data):
		data = UnpackBuf(data)

		num_entries, self.revision_nr = data.unpack(">L 4x L")

		self.__entries = []
		for i in range(num_entries):
			id, flag = data.unpack(">L H")
			if flag == 0x8001:
				use_frequently = True
			elif flag == 0:
				use_frequently = False
			else:
				raise IdentifierException('Unknown flag in identifier entry (0x%x)' % flag)

			group_nr, name = data.unpack(">H 4x 8x 16s")

			self.add_entry(IdentifierEntry(id, use_frequently, group_nr, name))

		return data

	def _file_path(self, base_path, printer_mac, generation_nr, suffix):
		return os.path.join(
			os.path.join(base_path, 'Address'),
			"D%s.%d.%s" % (printer_mac, generation_nr, suffix))

	def dump_file(self, base_path, printer_mac, generation_nr, suffix):
		f = open(self._file_path(base_path, printer_mac, generation_nr, suffix),
				 'wb')
		f.write(self.dump())

	def load_file(self, base_path, printer_mac, generation_nr, suffix):
		f = open(self._file_path(base_path, printer_mac, generation_nr, suffix),
				 'rb')
		self.load(f.read())

	def load_config(self, config_file, section_name):
		# We blindly assume, that the configuration data was changed.
		self.increase()

		self.__entries = []
		for id, data in config_file.items(section_name):
			id = int(id)
			name, use_frequently, group_nr = data.split(',')
			if use_frequently == 'true':
				use_frequently = True
			elif use_frequently == 'false':
				use_frequently = False
			else:
				raise IdentifierException('Unknown flag in identifier config " \
						"entry: "%s"' % use_frequently)
			group_nr = int(group_nr)
			self.add_entry(IdentifierEntry(id, use_frequently, group_nr, name))

	def increase(self):
		self.revision_nr += 1


class Version(object):
	def __init__(self, generation_nr = 1):
		self.generation_nr = generation_nr

	def __repr__(self):
		return "Version(generation_nr = %d)" % self.generation_nr


	def dump(self):
		data = struct.pack(">L", self.generation_nr)
		return data

	def load(self, data):
		self.generation_nr, = struct.unpack(">L", data)


	def _file_path(self, base_path, printer_mac):
		return os.path.join(
			os.path.join(base_path, 'Version'), "D%s.ver" % printer_mac)

	def dump_file(self, base_path, printer_mac):
		f = open(self._file_path(base_path, printer_mac), 'wb')
		f.write(self.dump())

	def load_file(self, base_path, printer_mac):
		f = open(self._file_path(base_path, printer_mac), 'rb')
		self.load(f.read())

	def increase(self):
		self.generation_nr += 1


class TargetList(object):
	def __init__(self, printer_mac):
		self.printer_mac = printer_mac

		self.version = Version()
		self.group = Group()
		self.__destinations_list = Identifiers()
		self.__senders_list = Identifiers()

	def __repr__(self):
		return "<TargetList(printer_mac = %s, version = %s, group = %s, "\
			   "destinations_list = %s, senders_list = %s)>" % \
			   (self.printer_mac, self.version, self.group,
			    self.__destinations_list, self.__senders_list)


	def set_dst(dself, st_list):
		# Assure that the new revision number is at least as large as the
		# previous number.
		dst_list.revision_nr = \
			max(dst_list.revision_nr, self.__destinations_list.revision_nr)

		self.__destinations_list = dst_list

	def get_dst(self):
		return self.__destinations_list

	destinations_list = property(get_dst, set_dst)


	def set_snd(self, snd_list):
		# Assure that the new revision number is at least as large as the
		# previous number.
		snd_list.revision_nr = \
			max(snd_list.revision_nr, self.__senders_list.revision_nr)

		self.__senders_list = snd_list

	def get_snd(self):
		return self.__senders_list

	senders_list = property(get_snd, set_snd)


	def dump_path(self, base_path):
		self.version.dump_file(base_path, self.printer_mac)
		self.group.dump_file(base_path, self.printer_mac,
				self.version.generation_nr)
		self.__destinations_list.dump_file(base_path, self.printer_mac,
				self.version.generation_nr, suffix = 'dst')
		self.__senders_list.dump_file(base_path, self.printer_mac,
				self.version.generation_nr, suffix = 'snd')

	def load_path(self, base_path):
		self.version.load_file(base_path, self.printer_mac)
		self.group.load_file(base_path, self.printer_mac,
				self.version.generation_nr)
		self.__destinations_list.load_file(base_path, self.printer_mac,
				self.version.generation_nr, suffix = 'dst')
		self.__senders_list.load_file(base_path, self.printer_mac,
				self.version.generation_nr, suffix = 'snd')


	def load_config(self, config_file):
		# Note: We do not load any version information here.
		self.group.load_config(config_file, 'ds_groups')
		self.__destinations_list.load_config(config_file, 'ds_destinations')
		self.__senders_list.load_config(config_file, 'ds_senders')

