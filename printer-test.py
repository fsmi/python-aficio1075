#!/usr/bin/python2.5
# -*- coding: utf-8 -*-
# vim:set ts=4 sw=4 noet:

from printer import Printer, DeliveryInput, UserMaint

p = Printer(host = 'fsi-pr2', port = 80)
#sdi = DeliveryInput(printer = p)
#sdi.authenticate('nJscW1hamx0=')
#sdi.set_delivery_service('fsi-pc1')

um = UserMaint(printer = p, auth_token = 'mdgamxkbjEw=')

#print um.delete_user(6000)
print um.delete_user(6000)
print um.add_user(6000, u"Äpfel und Bänänën")
for user in um.user_counter(usercode = 6000):
	print "%s %s %s %s %s %s" % user
