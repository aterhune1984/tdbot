#!/usr/bin/env python

from keys import ameritrade, gmailpass
import requests
import time
import json
import pickle as pkl
from ratelimit import limits, sleep_and_retry
import sys
import backtrader as bt

import os
from glob import glob
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
import yfinance as yf
import pandas_ta as ta
import numpy as np
import talib
import datetime
from tda import auth
from tda.client import Client
import smtplib
import time
import imaplib
import email
import traceback
from email.header import decode_header

url = "https://api.tdameritrade.com/"
scheduler = BackgroundScheduler()

ORG_EMAIL = "@gmail.com"
FROM_EMAIL = "terhunetdbot" + ORG_EMAIL
FROM_PWD = gmailpass
SMTP_SERVER = "imap.gmail.com"
SMTP_PORT = 993

def read_email_from_gmail():
    try:
        imap = imaplib.IMAP4_SSL(SMTP_SERVER)
        imap.login(FROM_EMAIL, FROM_PWD)
        imap.select('inbox')

        status, messages = imap.search(None, 'ALL')
        messages = messages[0].split(b' ')
        down_text = False
        up_text = False
        if len(messages) > 0:  #  if there is mail in the mailbox...
            if messages[0] != b'':
                for mail in messages:
                    _, msg = imap.fetch(mail, "(RFC822)")
                    # you can delete the for loop for performance if you have a long list of emails
                    # because it is only for printing the SUBJECT of target email to delete
                    for response in msg:
                        if isinstance(response, tuple):
                            msg = email.message_from_bytes(response[1])
                            # decode the email subject
                            subject = decode_header(msg["Subject"])[0][0]
                            if isinstance(subject, bytes):
                                # if it's a bytes type, decode to str
                                subject = subject.decode()
                            if 'macd_down' in msg._payload.split('">Alert: New symbols:')[1]:
                                down_text = msg._payload.split('">Alert: New symbols:')[1].split('</p></td>\r\n')[0]
                                imap.store(mail, "+FLAGS", "\\Deleted")
                                # mark the mail as deleted
                            if 'macd_up' in msg._payload.split('">Alert: New symbols:')[1]:
                                up_text = msg._payload.split('">Alert: New symbols:')[1].split('</p></td>\r\n')[0]
                                imap.store(mail, "+FLAGS", "\\Deleted")
            imap.expunge()
        imap.close()
        imap.logout()
        return up_text, down_text


    except Exception as e:
        traceback.print_exc()
        print(str(e))




@sleep_and_retry
@limits(calls=120, period=60)
def td_client_request(c, ticker=False):
    data = c.get_price_history(ticker,
                               frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                               frequency=Client.PriceHistory.Frequency.EVERY_FIFTEEN_MINUTES,
                               start_datetime=datetime.datetime.now() - datetime.timedelta(360),
                               end_datetime=datetime.datetime.now())
    try:
        return data.json()
    except Exception as e:
        print(e)



class threeema(bt.Strategy):

    def __init__(self):

        self.sma = bt.indicators.SMA(self.data, period=5)
        self.mma = bt.indicators.EMA(self.data, period=8)
        self.lma = bt.indicators.EMA(self.data, period=13)



    def notify_order(self, order):
        if not order.status == order.Completed:
            return  # discard any other notification

        if not self.position:  # we left the market
            #print('SELL@price: {:.2f}'.format(order.executed.price))
            return

        # We have entered the market
        #print('BUY @price: {:.2f}'.format(order.executed.price))
        self.buyprice = order.executed.price
        self.lipsunder = False

    def next(self):
        #self.closeness = self.sma[0] * .001
        if not self.position:
            if self.sma < self.mma and self.sma < self.lma:
                self.lipsunder = True
            else:
                self.lipsunder = False
            if self.lipsunder and self.data.close > self.mma:
                self.buy(size=1)
                self.lipsunder = False

        else:
            if self.data.close < self.sma:
                self.close()


def parse_alert(text):
    symbols = ''.join(text.split('=\r\n')).split('were added')[0].strip(' ').split(', ')
    return symbols


def backtest(ticker, df):
    startcash = 200000
    cerebro = bt.Cerebro()
    cerebro.addstrategy(threeema)
    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data, name="Real")
    cerebro.broker.setcash(startcash)
    cerebro.run()
    # Get final portfolio Value
    portvalue = cerebro.broker.getvalue()
    pnl = portvalue - startcash
    print('Final Portfolio Value: ${}'.format(round(portvalue, 2)))
    print('P/L: ${}'.format(round(pnl, 2)))


def backtest_symbols(c, symbols):
    ticker_df = {}
    for ticker in symbols:
        # for each ticker, get the price history to do check if it meets our criteria
        data = td_client_request(c, ticker)

        try:
            if not data.get('error'):
                ticker_df[ticker] = pd.DataFrame(data['candles'])
                first_column = ticker_df[ticker].pop('datetime')
                ticker_df[ticker].insert(0, 'date', first_column)
                ticker_df[ticker]['date'] = pd.to_datetime(ticker_df[ticker]['date'], format="%Y/%m/%d %H:%M:%S")
                ticker_df[ticker].set_index('date', inplace=True)
                # apply strategy to each ticker to find the good ones.
                if len(data['candles']) > 50:
                    # now backtest this symbol with strategy and see if its profitable
                    print('processing {}'.format(ticker))
                    backtest(ticker, ticker_df[ticker])

                    #sys.stdout.write(".")

        except Exception as e:
            print(e)





token_path = './/token.pickle'
api_key = '{}@AMER.OAUTHAP'.format(ameritrade)
redirect_uri = 'http://localhost:8000'

while True:
    try:
        c = auth.client_from_token_file(token_path, api_key)
    except FileNotFoundError:
        from selenium import webdriver

        with webdriver.Firefox() as driver:
            c = auth.client_from_login_flow(
                driver, api_key, redirect_uri, token_path)
    account_info = c.get_accounts().json()[0]
    cash_balance = account_info['securitiesAccount']['currentBalances']['cashBalance']
    cash_available_for_trade = account_info['securitiesAccount']['currentBalances']['buyingPowerNonMarginableTrade']
    up_text, down_text = read_email_from_gmail()
    if up_text:
        #uptext_handler
        symbols = parse_alert(up_text)
        print('received buy signal, pulling {}'.format(symbols))
        backtest_symbols(c, symbols)
        pass
    if down_text:
        #downtext_handler
        symbols = parse_alert(down_text)
        print(symbols)
        print('received sell signal, closing positions if in any')

        pass
    else:
        time.sleep(2)
        continue


