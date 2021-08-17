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
import talib

import math
import pandas_ta as ta
import requests
import asyncio
import json
import pandas as pd
from tinydb import TinyDB, Query


global runningpl
runningpl = 0
global pandas_data
pandas_data = {}
global df2
global df0
df2 = []
df0 = []
global make_sale
make_sale = True
global db
global df_len
df_len = 0
global old_df0_len
old_df0_len = 0
db = TinyDB('./db.json')

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
    global df2
    global df_len
    global old_df0_len
    global make_sale
    if 'content' in msg:
        for i, content in enumerate(msg['content']):
            if 'BID_PRICE' in msg['content'][i]:



                if len(df0) == 0 and os.path.exists('./pandas_pickle'):
                    pandas_data = pd.read_pickle('./pandas_pickle')
                    df0 = pandas_data[content['key']].resample('1min').ohlc().dropna()
                    df1 = pandas_data[content['key']].resample('5min').ohlc().dropna()
                    df2 = pandas_data[content['key']].resample('15min').ohlc().dropna()
                    df_len = len(df0)

                if content['key'] not in pandas_data:
                    pandas_data[content['key']] = pd.DataFrame({'Timestamp': int(round(time.time() * 1000)), 'Price': 0}, index=[0])
                    pandas_data[content['key']]['Timestamp'] = pd.to_datetime(pandas_data[content['key']]['Timestamp'], unit='ms')
                    pandas_data[content['key']] = pandas_data[content['key']].set_index('Timestamp')

                # here is where I am adding a new value to pandas_data
                pandas_data[content['key']].loc[pd.to_datetime(content['QUOTE_TIME'], unit='ms')] = [content['BID_PRICE']]




                if len(pandas_data[content['key']]) == 2 and (pandas_data[content['key']]['Price'] == 0.000).any():
                    pandas_data[content['key']] = pandas_data[content['key']][pandas_data[content['key']].Price != 0.000]
                if len(df2) < 30:

                    df2 = pandas_data[content['key']].resample('15min').ohlc().dropna()

                else:
                    df0 = pandas_data[content['key']].resample('1min').ohlc().dropna()
                    if len(df0) >= 375:
                        print('running through calcs')
                        #print('writing pickle')
                        pd.to_pickle(pandas_data, './pandas_pickle')
                        df1 = pandas_data[content['key']].resample('5min').ohlc().dropna()
                        df2 = pandas_data[content['key']].resample('15min').ohlc().dropna()
                        #macd0 = df0['Price'].ta.macd(fast=3, slow=10, signal=16)
                        #macd1 = df1['Price'].ta.macd(fast=3, slow=10, signal=16)
                        #macd2 = df2['Price'].ta.macd(fast=3, slow=10, signal=16)

                        # short time
                        df0['short_ema'] = df0['Price'].close.ewm(span=3, adjust=False).mean()
                        df0['long_ema'] = df0['Price'].close.ewm(span=10, adjust=False).mean()
                        df0['macd_val'] = df0['short_ema'] - df0['long_ema']
                        df0['macd_avg'] = df0['macd_val'].ewm(span=16, adjust=False).mean()
                        df0['macd_diff'] = df0['macd_val'] - df0['macd_avg']

                        # mid time
                        df1['short_ema'] = df1['Price'].close.ewm(span=3, adjust=False).mean()
                        df1['long_ema'] = df1['Price'].close.ewm(span=10, adjust=False).mean()
                        df1['macd_val'] = df1['short_ema'] - df1['long_ema']
                        df1['macd_avg'] = df1['macd_val'].ewm(span=16, adjust=False).mean()
                        df1['macd_diff'] = df1['macd_val'] - df1['macd_avg']

                        # long time
                        df2['short_ema'] = df2['Price'].close.ewm(span=3, adjust=False).mean()
                        df2['long_ema'] = df2['Price'].close.ewm(span=10, adjust=False).mean()
                        df2['macd_val'] = df2['short_ema'] - df2['long_ema']
                        df2['macd_avg'] = df2['macd_val'].ewm(span=16, adjust=False).mean()
                        df2['macd_diff'] = df2['macd_val'] - df2['macd_avg']

                        #macd0, macd0_signal, macd0_hist = talib.MACDEXT(df0['Price'].close, fastperiod=3, fastmatype=0, slowperiod=10, slowmatype=0, signalperiod=16, signalmatype=0)

                        #todo this is not working as I would expect it.  This must be working before it can be made live
                        # test if are still in the correct condition for the three macds
                        #lowtimehigher = float(macd0['MACDh_3_10_16'][-2:-1]) < float(macd0['MACDh_3_10_16'][-1:])
                        #midtimehigher = float(macd1['MACDh_3_10_16'][-2:-1]) < float(macd1['MACDh_3_10_16'][-1:])
                        #longtimehigher = float(macd2['MACDh_3_10_16'][-2:-1]) < float(macd2['MACDh_3_10_16'][-1:])

                        #lastlowtimelower = float(macd0['MACDh_3_10_16'][-3:-2]) > float(macd0['MACDh_3_10_16'][-2:-1])
                        #lastmidtimelower = float(macd1['MACDh_3_10_16'][-3:-2]) > float(macd1['MACDh_3_10_16'][-2:-1])
                        #lastlongtimelower = float(macd2['MACDh_3_10_16'][-3:-2]) > float(macd2['MACDh_3_10_16'][-2:-1])

                        #if lowtimehigher and midtimehigher and longtimehigher and (
                        #        lastlongtimelower or lastmidtimelower or lastlowtimelower):
                        #    proceed = True
                        #else:
                        #    proceed = False

                        #df0['atr'] = ta.atr(df0['Price']['high'], df0['Price']['low'], df0['Price']['close'])
                        #atrval = float(df0[-1:]['atr'])
                        #old_df0_len = len(df0)
                        #if proceed:
                        #    print('buy something')

                        oldest_timestamp = pd.to_datetime(df0.iloc[0].name.timestamp(), unit='s')
                        second_oldest_timestamp = pd.to_datetime(df0.iloc[1].name.timestamp(), unit='s')
                        drop = pandas_data[content['key']].loc[(pandas_data[content['key']].index > oldest_timestamp) & (
                                    pandas_data[content['key']].index < second_oldest_timestamp)]
                        pandas_data[content['key']].drop(drop.index, inplace=True)
                        #old_df0_len = len(df0)

                    #df0 = pandas_data[content['key']].resample('1min').ohlc().dropna()
                #pandas_data[content['key']]['date'] = pandas_data[content['key']]['Timestamp'].map(lambda x: unix_convert(x))
                #pandas_data = pandas_data.append(val, ignore_index=True)
                print(msg['content'][i]['BID_PRICE'])

async def read_stream():
    await client.login()
    await client.quality_of_service(client.QOSLevel.FAST)

    await client.level_one_forex_subs(['USD/MXN'])
    client.add_level_one_forex_handler(message_handler)

    while True:
        try:
            await client.handle_message()
        except Exception as e:
            pass

while True:
    try:
        asyncio.get_event_loop().run_until_complete(read_stream())
    except:
        print('app failed, starting over')
