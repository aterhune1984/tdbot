#!/usr/bin/env python

from keys import ameritrade, gmailpass

from ratelimit import limits, sleep_and_retry
import sys
from bs4 import BeautifulSoup

from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import datetime
from tda import auth
from tda.client import Client
from tda import streaming
from tda.orders.generic import OrderBuilder
from tda.orders.equities import equity_sell_limit, equity_buy_market,equity_buy_limit, equity_sell_market
from tda.orders.common import Duration, Session,OrderType,StopPriceLinkType,StopPriceLinkBasis, first_triggers_second,one_cancels_other
import time
import imaplib
import email
import traceback
import os
import random
import math
import pandas_ta as ta
import requests
import asyncio
import json
import pandas as pd

global runningpl
runningpl = 0
global pandas_data
pandas_data = {}
global df0
df0 = []

TD_ACCOUNT = '238433715'
token_path = '{}/token.pickle'.format(os.getcwd())
api_key = '{}@AMER.OAUTHAP'.format(ameritrade)
redirect_uri = 'http://localhost:8000'
restricted_symbols = ['RXT']

print('Starting TDBOT for Forex...')

try:
    c = auth.client_from_token_file(token_path, api_key)
except:
    from selenium import webdriver

    with webdriver.Firefox() as driver:
        c = auth.client_from_login_flow(
            driver, api_key, redirect_uri, token_path)

client = streaming.StreamClient(c, account_id=TD_ACCOUNT)

def unix_convert(ts):
    date = datetime.datetime.utcfromtimestamp(ts/1000)
    return date


def message_handler(msg):
    global pandas_data
    global df0
    if 'content' in msg:
        for i, c in enumerate(msg['content']):
            if 'BID_PRICE' in msg['content'][i]:
                if c['key'] not in pandas_data:
                    pandas_data[c['key']] = pd.DataFrame({'Timestamp': int(round(time.time() * 1000)), 'Price': 0}, index=[0])
                    pandas_data[c['key']]['Timestamp'] = pd.to_datetime(pandas_data[c['key']]['Timestamp'], unit='ms')
                    pandas_data[c['key']] = pandas_data[c['key']].set_index('Timestamp')

                #new_row = {"Timestamp": pd.to_datetime(c['QUOTE_TIME'], unit='ms'), 'Price': c['BID_PRICE']}
                pandas_data[c['key']].loc[pd.to_datetime(c['QUOTE_TIME'], unit='ms')] = [c['BID_PRICE']]
                #pandas_data[c['key']] = pandas_data[c['key']].append(new_row, ignore_index=True)
                if len(pandas_data[c['key']]) == 2 and (pandas_data[c['key']]['Price'] == 0.000).any():
                    pandas_data[c['key']] = pandas_data[c['key']][pandas_data[c['key']].Price != 0.000]
                if len(df0) < 20:
                    df0 = pandas_data[c['key']].resample('1min').ohlc()
                else:
                    oldest_timestamp = pd.to_datetime(df0.iloc[0].name.timestamp(), unit='s')
                    second_oldest_timestamp = pd.to_datetime(df0.iloc[1].name.timestamp(), unit='s')
                    drop = pandas_data[c['key']].loc[(pandas_data[c['key']].index > oldest_timestamp) & (pandas_data[c['key']].index < second_oldest_timestamp)]
                    pandas_data[c['key']].drop(drop.index, inplace=True)
                    df0 = pandas_data[c['key']].resample('1min').ohlc()
                    print(df0)

                #pandas_data[c['key']]['date'] = pandas_data[c['key']]['Timestamp'].map(lambda x: unix_convert(x))
                #pandas_data = pandas_data.append(val, ignore_index=True)
                print(msg['content'][i]['BID_PRICE'])

async def read_stream():
    await client.login()
    await client.quality_of_service(client.QOSLevel.REAL_TIME)

    await client.level_one_forex_subs(['USD/MXN'])
    client.add_level_one_forex_handler(message_handler)

    while True:
        await client.handle_message()

asyncio.get_event_loop().run_until_complete(read_stream())