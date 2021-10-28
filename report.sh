#!/usr/bin/env bash
IFS=$'\n'
filename=$1
LOSS=$(cat $filename | awk -F";" '{print $7}' | sed '/^$/d' | egrep -oc '^\(\$')
echo -n "Losses: "
echo $LOSS
WIN=$(cat $filename | awk -F";" '{print $7}' | sed '/^$/d' | egrep -oc '^\$')
echo -n "Wins: "
echo $WIN
echo -n "P/L Ratio: "
echo "$WIN/($LOSS+$WIN)*100" | bc -l
NET=$(cat $filename | grep 'Total P/L' | awk '{print $3}' | tr -d '$,;')
echo -n "Net Earnings: "
echo $NET



LASTLINE=$(cat $filename | grep -B3 "Max trade" | head -1)

TRADES=0
AVGDAYS=0

for line in $(cat $filename); do
    if  [[ $line =~ "to Open" ]]; then
        OPEN=$(echo $line | awk -F";" '{print $6}' | awk -F"," '{print $1}')
    elif [[ $line =~ "to Close" ]]; then
        CLOSE=$(echo $line | awk -F";" '{print $6}' | awk -F"," '{print $1}')
    fi
    if [[ $line =~ "Max trade" ]]; then
        if [[ $LASTLINE =~ "to Open" ]]; then
            CLOSE=$(date +'%m/%d/%y')
        fi
    fi

    if test "$CLOSE"; then
        echo -n "$OPEN - $CLOSE "
        DAYS=$(echo $(ddiff -i '%m/%d/%y' $OPEN $CLOSE))
        ((AVGDAYS+=DAYS))
        ((TRADES++))
        echo $DAYS
        unset OPEN
        unset CLOSE
    fi
done
echo "Number of trades: " $TRADES

echo "Average Days Open: " $(echo "$AVGDAYS/$TRADES" | bc)
