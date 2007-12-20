#!/bin/bash

PRINTER_HOST="fsi-pr2"
PRINTER_PORT="80"

TARGET_IP="$1"
if [ "$TARGET_IP" == "" ]; then
	echo "Usage: $0 <eigene IP-Adresse>"
	exit 1
fi

# Melde dich am Gerät an. Du bekommst dafür ein ticket, welches du im nächsten
# Aufruf brauchst.
locked=0
while [ $locked -eq 0 ]; do
	info=$(cat delivery/auth-delivery.xml | \
	       netcat $PRINTER_HOST $PRINTER_PORT | \
	       tail -n2)

	return_value=$(echo $info | \
	               xmlstarlet sel -t -m '//*' -v 'returnValue')
	if [ "$return_value" == "DIRC_OK" ]; then
		ticket=$(echo $info | \
		         xmlstarlet sel -t -m '//*' -v 'ticket_out/string')
		locked=1
		echo
	else
		sleep 1
		echo -n .
	fi
done
# Wir haben unser Ticket bekommen.

adresse=$(echo $TARGET_IP | \
          perl -M"MIME::Base64" -ne 'print encode_base64($_)')

# Jetzt können wir dem Drucker sagen, dass er uns Fragen soll wo er Scans
# abladen kann.
cat delivery/set-delivery.xml | \
	sed -e s/"TICKETSTRING"/"$ticket"/ \
	    -e s/"ADRESSE"/"$adresse"/ | \
	netcat $PRINTER_HOST $PRINTER_PORT
