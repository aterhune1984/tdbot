#!/usr/bin/env bash

filename=$1
LOSS=$(cat $filename | awk -F";" '{print $7}' | sed '/^$/d' | egrep -oc '^\(\$')
echo -n "Losses: "
echo $LOSS
WIN=$(cat $filename | awk -F";" '{print $7}' | sed '/^$/d' | egrep -oc '^\$')
echo -n "Wins: "
echo $WIN
echo -n "P/L Ratio: "
echo "$WIN/($LOSS+$WIN)*100" | bc -l