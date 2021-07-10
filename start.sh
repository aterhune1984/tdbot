#!/bin/bash
cd /home/pi/tdbot; PYTHONUNBUFFERED=1 /home/pi/tdbotenv/bin/python /home/pi/tdbot/bot.py | tee >(split --additional-suffix=.log -d -b 100000 - debug.0)