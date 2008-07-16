#!/usr/bin/python2.5
# mac_address - Linux specific helper to determine a remote host's MAC address.
# Copyright (C) 2007  Fabian Knittel <fabian.knittel@fsmi.uni-karlsruhe.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""
mac_address - Linux specific helper to determine a remote host's MAC address.

If the address isn't statically stored on the local machine, the remote host
needs to be connected to the local network and must reply to ARP requests.

Usage on cmd-line: ./mac_address.py <host_name or IPv4 address>
"""

from __future__ import with_statement
import socket
import sys
import re

def _http_ping_host(ipv4_addr):
	"""
	The main idea is to force the local host to look-up the remote's MAC
	address. Any type of IPv4 operation should suffice to achieve this. This
	function emulates a tcp ping.

	Does not return a result but expects to have side-effects.
	"""
	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

		# Don't wait for hosts that have a packet-dropping firewall.
		s.settimeout(0.5)

		# Attempt to open a TCP connection. Most likely won't work, but
		# the local host will have tried.
		s.connect((ipv4_addr, 1))

		s.close()
	except:
		pass

def _read_arp():
	ARP_RE = '^(\d+\.\d+\.\d+\.\d+) +0x\d+ +0x\d+ +(..:..:..:..:..:..) +.*$'
	entry_re = re.compile(ARP_RE)

	with open('/proc/net/arp', 'r') as arp_file:
		# Skip header.
		arp_file.readline()

		arp_entries = {}
		for line in arp_file:
			res = entry_re.search(line)
			if res is not None:
				arp_entries[res.group(1)] = res.group(2)

	return arp_entries

def get_mac_address(ipv4_addr):
	"""
	Returns the MAC address of the passed IPv4 address or None if the
	discovery fails.

	The MAC address is returned as a string in the typical hexadecimal
	notation, i.e. 'XX:XX:XX:XX:XX:XX'.
	"""
	_http_ping_host(ipv4_addr)
	arp_entries = _read_arp()
	if ipv4_addr not in arp_entries:
		return None
	return arp_entries[ipv4_addr]

def compact_mac_address(mac_address):
	"""
	Convenience function to strip down mac addresses.
	"""
	if mac_address is not None:
		return ''.join(mac_address.lower().split(':'))

__all__ = [ get_mac_address, compact_mac_address ]

if __name__ == '__main__':
	host = sys.argv[1]
	try:
		ipv4_addr = socket.gethostbyname(host)
	except socket.gaierror, ex:
		sys.stderr.write('mac_address: %s (#%d)\n' % \
			(ex.args[1], ex.args[0]))
		sys.exit(1)
	print '%s: %s' % (host, get_mac_address(ipv4_addr))
