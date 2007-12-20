#!/bin/bash

if [ x$1 == "x" ]; then
echo "Usage: $0 <eigene IP-Adresse>"
exit 1
fi

# Melde dich am Gerät an. Du bekommst dafür ein ticket, welches du im nächsten Aufruf brauchst.
locked=0
while [ $locked -eq 0 ]; do
info=$(cat delivery/auth-delivery.xml|netcat fsi-pr2 80|tail -n2)
if [ $(echo $info|xmlstarlet sel -t -m '//*' -v 'returnValue') == "DIRC_OK" ]; then
ticket=$(echo $info|xmlstarlet sel -t -m '//*' -v 'ticket_out/string')
locked=1
echo
else
sleep 1
echo -n .
fi
done
# Wir haben unser Ticket bekommen.

# Das hier funktioniert auf jedenfall für 10.14.1.1, 10.14.1.10 und 10.14.1.20. Bei 10.14.1.244 hat es Probleme gemacht... müsste man vielleicht noch verbessern.
adresse=$(echo $1|perl -M"MIME::Base64" -ne 'print encode_base64($_)'|sed -e s/".="/"=="/)

# So.. jetzt können wir dem Drucker sagen, dass er uns Fragen soll wo er Scans abladen kann.
cat delivery/set-delivery.xml|sed -e s/"TICKETSTRING"/"$ticket"/ -e s/"ADRESSE"/"$adresse"/|netcat fsi-pr2 80
