#!/usr/bin/env python

from keys import ameritrade, gmailpass
import requests
import time
import json
import pickle as pkl
from ratelimit import limits, sleep_and_retry
import sys
import backtrader as bt
from bs4 import BeautifulSoup
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
                            soup = BeautifulSoup(msg._payload, 'html.parser')
                            if 'macd_down' in soup.get_text().split('\nAlert')[1]:
                                down_text = soup.get_text().split('\nAlert')[1]
                                imap.store(mail, "+FLAGS", "\\Deleted")
                                # mark the mail as deleted
                            if 'macd_up' in soup.get_text().split('\nAlert')[1]:
                                up_text = soup.get_text().split('\nAlert')[1]
                                imap.store(mail, "+FLAGS", "\\Deleted")
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
                               start_datetime=datetime.datetime.now() - datetime.timedelta(60),
                               end_datetime=datetime.datetime.now())
    try:
        return data.json()
    except Exception as e:
        return False



class hull(bt.Strategy):
    params = dict(
        stop_loss=0.02,  # price is 2% less than the entry point
        trail=False,
    )

    def __init__(self):
        self.hull = bt.indicators.HullMovingAverage(self.data)
        self.uptrend = False


    def notify_order(self, order):
        if not order.status == order.Completed:
            return  # discard any other notification

        if not self.position:  # we left the market
            print('SELL@price: {:.2f}'.format(order.executed.price))
            return

        print('BUY @price: {:.2f}'.format(order.executed.price))


    def next(self):
        if self.hull.lines.hma[0] > self.hull.lines.hma[-1]:
            self.uptrend = True
        else:
            self.uptrend = False
        #self.closeness = self.sma[0] * .001
        if not self.position:
            if self.uptrend:
                self.buy(size=1)
                if not self.p.trail:
                    stop_price = self.data.close[0] * (1.0 - self.p.stop_loss)
                    self.sell(exectype=bt.Order.Stop, price=stop_price)
                else:
                    self.sell(exectype=bt.Order.StopTrail,
                              trailamount=self.p.trail)
        else:
            if not self.uptrend:
                self.close()


class macd(bt.Strategy):
    params = dict(
        stop_loss=0.02,  # price is 2% less than the entry point
        trail=False,
    )

    def __init__(self):
        self.lma = bt.indicators.MovingAverageSimple(self.data, period=200)
        self.macd = bt.indicators.MACDHisto(self.data)
        self.uptrend = False


    def notify_order(self, order):
        if not order.status == order.Completed:
            return  # discard any other notification

        if not self.position:  # we left the market
            print('SELL@price: {:.2f}'.format(order.executed.price))
            return

        print('BUY @price: {:.2f}'.format(order.executed.price))


    def next(self):
        if (self.data.tick_close * .1) < (self.data.tick_close - self.data.close[200]):
            self.uptrend = True
        else:
            self.uptrend = False
        #self.closeness = self.sma[0] * .001
        if not self.position:
            if self.uptrend:
                if self.macd.lines.histo > 0:
                    self.buy(size=1)
                    if not self.p.trail:
                        stop_price = self.data.close[0] * (1.0 - self.p.stop_loss)
                        self.sell(exectype=bt.Order.Stop, price=stop_price)
                    else:
                        self.sell(exectype=bt.Order.StopTrail,
                                  trailamount=self.p.trail)
        else:
            if not self.uptrend or self.macd.lines.histo < 0:
                self.close()


def parse_alert(text):
    try:
        symbols = ''.join(text.split('\r\n: ')[1].split(' were added')[0].split('=\r\n')).split(', ')
    except Exception:
        try:
            symbols = [text.split('=\r\n ')[1].split(' was added')[0]]
        except Exception as e:
            print(e)
    return symbols


def backtest(ticker, df):
    for s in [macd]:
        startcash = 200000
        cerebro = bt.Cerebro()
        cerebro.addstrategy(s)
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data, name="Real")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe_ratio')
        cerebro.broker.setcash(startcash)
        cerebro.run()
        # Get final portfolio Value
        portvalue = cerebro.broker.getvalue()
        pnl = portvalue - startcash
        print('Final Portfolio Value: ${}'.format(round(portvalue, 2)))
        print('P/L: ${}'.format(round(pnl, 2)))
        cerebro.plot(style='candlestick')
        print('pause')



def backtest_symbols(c, symbols):
    ticker_df = {}
    for ticker in symbols:
        # for each ticker, get the price history to do check if it meets our criteria
        data = td_client_request(c, ticker)
        if data:
            try:
                if not data.get('error'):
                    ticker_df[ticker] = pd.DataFrame(data['candles'])
                    first_column = ticker_df[ticker].pop('datetime')
                    ticker_df[ticker].insert(0, 'date', first_column)
                    ticker_df[ticker]['date'] = pd.to_datetime(ticker_df[ticker]['date'], format="%Y/%m/%d %H:%M:%S")
                    ticker_df[ticker].set_index('date', inplace=True)
                    # apply strategy to each ticker to find the good ones.
                    if len(data['candles']) > 200:
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
    while True:
        try:
            account_info = c.get_accounts().json()[0]
            break
        except KeyError as e:
            time.sleep(1)
            pass
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


