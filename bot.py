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

url = "https://api.tdameritrade.com/"
scheduler = BackgroundScheduler()

ORG_EMAIL = "@gmail.com"
FROM_EMAIL = "terhunetdbot" + ORG_EMAIL
FROM_PWD = gmailpass
SMTP_SERVER = "imap.gmail.com"
SMTP_PORT = 993
TD_ACCOUNT = '238433715'

def read_email_from_gmail():
    try:
        imap = imaplib.IMAP4_SSL(SMTP_SERVER)
        imap.login(FROM_EMAIL, FROM_PWD)
        imap.select('inbox')
        pacific = pytz.timezone('US/Pacific')

        status, messages = imap.search(None, 'ALL')
        messages = messages[0].split(b' ')
        down_text = False
        up_text = False
        quit = False
        if len(messages) > 0:  #  if there is mail in the mailbox...
            if messages[0] != b'':
                for mail in messages:
                    _, msg = imap.fetch(mail, "(RFC822)")
                    # you can delete the for loop for performance if you have a long list of emails
                    # because it is only for printing the SUBJECT of target email to delete
                    for response in msg:

                        if isinstance(response, tuple):
                            #msg = email.message_from_bytes(response[1])
                            # decode the email subject
                            # test how old the email is, if this is an old email, we dont want to be taking action based on this
                            # if its older than 5 min, ignore and delete the email.
                            timediff = datetime.datetime.now(tz=pacific) - datetime.datetime.strptime(
                                str(response[1]).split('Received:')[1].split('\\r\\n')[1].strip().split(' (')[0],
                                '%a, %d %b %Y %H:%M:%S %z')
                            #if timediff.total_seconds() < 60:
                            if True:
                                try:
                                    soup = BeautifulSoup(response[1],'html.parser')
                                except:
                                    print('i failed')
                                try:
                                    if 'AA_aterhune1984' in soup.get_text() or ' SOLD ' in soup.get_text():
                                        quit=True
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                    elif 'tradingview_macd_long_sell' in ','.join(soup.get_text().split('\nAlert')).replace('=\r\n',''):
                                        quit = True
                                        down_text = soup.get_text().split('\nAlert')[1]
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                        # mark the mail as deleted
                                    elif 'tradingview_macd_long' in ','.join(soup.get_text().split('\nAlert')).replace('=\r\n',''):
                                        quit = True
                                        up_text = soup.get_text().split('\nAlert')[1]
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                    else:
                                        quit = True
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                except Exception as e:
                                    print(e)
                            else:
                                imap.store(mail, "+FLAGS", "\\Deleted")
                    if quit:
                        break

            imap.expunge()
        imap.close()
        imap.logout()
        return up_text, down_text


    except Exception as e:
        traceback.print_exc()
        print(str(e))


def consolidate(data, thirtymincount=2):
    jsonobj=[]
    num = -1
    for i, e in enumerate(data):
        num += 1
        if num <= thirtymincount-1:
            if num == 0:
                open = e['open']
                high = max([x['high'] for x in data][i:i+thirtymincount])
                low = min([x['low'] for x in data][i:i+thirtymincount])
                vol = sum([x['volume'] for x in data][i:i+thirtymincount])
            if num == thirtymincount-1:
                close = e['close']
        if num == thirtymincount-1:
            jsonobj.append({'open': open, 'high': high, 'low': low, "close": close, "volume": vol})
            num = -1
    return jsonobj


def unix_convert(ts):
    date = datetime.datetime.utcfromtimestamp(ts/1000)
    return date

@sleep_and_retry
@limits(calls=120, period=60)
def td_client_request(option, c, ticker=False, orderinfo=False):
    num = 0
    while num <= 3:
        time.sleep(1)
        try:
            if option == 'get_price_history':
                data = c.get_price_history(ticker,
                                           frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                           frequency=Client.PriceHistory.Frequency.EVERY_FIFTEEN_MINUTES,
                                           start_datetime=datetime.datetime.now() - datetime.timedelta(days=5),
                                           end_datetime=datetime.date.today() + datetime.timedelta(days=1),
                                           need_extended_hours_data=False)

                return_val = data.json()
                return return_val
            if option == 'get_quotes':
                # in this case ticker is a list of symbols.
                data = c.get_quotes(ticker)
                return_val = data.json()
                return return_val
            if option == 'place_order':
                # we are going to try and place an order now.
                #todo test test test
                proceed = False
                data1 = c.get_price_history(orderinfo['symbol'],
                                           frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                           frequency=Client.PriceHistory.Frequency.EVERY_FIFTEEN_MINUTES,
                                           start_datetime=datetime.datetime.now() - datetime.timedelta(days=30),
                                           end_datetime=datetime.datetime.today() + datetime.timedelta(days=1),
                                           need_extended_hours_data=False)
                data1_json = data1.json()

                df1 = ta.DataFrame(data1_json['candles'], columns=['open', 'high', 'low', 'close', 'volume', 'datetime'])

                df1['date'] = df1['datetime'].map(lambda x: unix_convert(x))
                df2 = df1.resample('60min', on='date').agg(
                    {'volume': 'sum', 'open': 'first', 'close': 'last', 'high': 'max', 'low': 'min'})
                df3 = df1.resample('240min', on='date').agg(
                    {'volume': 'sum', 'open': 'first', 'close': 'last', 'high': 'max', 'low': 'min'})

                macd1 = df1.ta.macd(fast=3, slow=10, signal=16)
                macd2 = df2.ta.macd(fast=3, slow=10, signal=16)
                macd3 = df3.ta.macd(fast=3, slow=10, signal=16)

                # test if are still in the correct condition for the three macds
                lowtimehigher = float(macd1['MACDh_3_10_16'][-2:-1]) < float(macd1['MACDh_3_10_16'][-1:])
                midtimehigher = float(macd2['MACDh_3_10_16'][-2:-1]) < float(macd2['MACDh_3_10_16'][-1:])
                longtimehigher = float(macd3['MACDh_3_10_16'][-2:-1]) < float(macd3['MACDh_3_10_16'][-1:])

                lastlowtimelower = float(macd1['MACDh_3_10_16'][-3:-2]) > float(macd1['MACDh_3_10_16'][-2:-1])
                lastmidtimelower = float(macd2['MACDh_3_10_16'][-3:-2]) > float(macd2['MACDh_3_10_16'][-2:-1])
                lastlongtimelower = float(macd3['MACDh_3_10_16'][-3:-2]) > float(macd3['MACDh_3_10_16'][-2:-1])


                if lowtimehigher and midtimehigher and longtimehigher and (lastlongtimelower or lastmidtimelower or lastlowtimelower):
                    proceed = True

                if not proceed:
                    return False
                df1['atr'] = ta.atr(df1['high'], df1['low'], df1['close'])
                atrval = float(df1[-1:]['atr'])
                obj1 = equity_buy_limit(orderinfo['symbol'], orderinfo['qty'], orderinfo['price'])
                obj1.set_session(Session.NORMAL)
                obj1.set_duration(Duration.DAY)

                obj2 = equity_sell_market(orderinfo['symbol'], orderinfo['qty'])
                obj2.set_order_type(OrderType.STOP)
                obj2.set_session(Session.NORMAL)
                obj2.set_duration(Duration.GOOD_TILL_CANCEL)
                obj2.set_stop_price(orderinfo['price']-(atrval*2))
                obj2.set_stop_price_link_basis(StopPriceLinkBasis.TRIGGER)
                obj2.set_stop_price_link_type(StopPriceLinkType.PERCENT)


                obj3 = equity_sell_limit(orderinfo['symbol'], orderinfo['qty'],orderinfo['price']+(atrval*4))
                obj3.set_order_type(OrderType.LIMIT)
                obj3.set_session(Session.NORMAL)
                obj3.set_duration(Duration.GOOD_TILL_CANCEL)


                x = c.place_order(TD_ACCOUNT, first_triggers_second(obj1,  one_cancels_other(obj2, obj3)).build())
                #x = c.place_order(TD_ACCOUNT, first_triggers_second(obj1, obj2).build())
                if str(x.status_code).startswith('2'):
                    print('buying {} of {}  at {} with a stoploss of {}'.format(orderinfo['qty'],
                                                                                orderinfo['symbol'],
                                                                                orderinfo['price'],
                                                                                orderinfo['price']-(atrval*2)))
                    return True
                else:
                    num += 1
                    print('something went wrong')

            if option == 'get_positions':
                return c.get_accounts(fields=Client.Account.Fields.POSITIONS).json()[0]
            if option == 'sell_order':
                x = c.get_orders_by_path(TD_ACCOUNT, status=Client.Order.Status.FILLED)
                for y in x.json():
                    sym = y['orderLegCollection'][0]['instrument']['symbol']
                    if orderinfo['symbol'] == sym:
                        for i, cos in enumerate(y['childOrderStrategies']):
                            x = c.cancel_order(cos['childOrderStrategies'][i]['orderId'], TD_ACCOUNT)
                            if str(x.status_code).startswith('2'):
                                print('canceled trailing stop order successfully')

                                obj = equity_sell_market(orderinfo['symbol'], orderinfo['qty'])
                                obj.set_session(Session.NORMAL)
                                obj.set_duration(Duration.DAY)
                                order = obj.build()
                                x = c.place_order(TD_ACCOUNT, order)
                                if str(x.status_code).startswith('2'):
                                    print('placed sell order successfully')
                                    return True
                                else:
                                    num += 1
                                    print('something went wrong')
        except Exception as e:
            num += 1
            time.sleep(1)
    return False



def parse_alert(text):
    try:
        symbols = text.replace('=\r\n', '').split(' w')[0].split(': ')[-1].split(', ')
    except Exception:
        try:
            symbols = [text.split('=\r\n ')[1].split(' was added')[0]]
        except Exception as e:
            print(e)
    return symbols


global runningpl
runningpl = 0


token_path = '{}/token.pickle'.format(os.getcwd())
api_key = '{}@AMER.OAUTHAP'.format(ameritrade)
redirect_uri = 'http://localhost:8000'
restricted_symbols = ['RXT']
print('Starting TDBOT...')

while True:
    backtest_dict = {}
    try:
        c = auth.client_from_token_file(token_path, api_key)
    except:
        from selenium import webdriver

        with webdriver.Firefox() as driver:
            c = auth.client_from_login_flow(
                driver, api_key, redirect_uri, token_path)
    while True:
        try:
            account_info = c.get_accounts().json()[0]
            break
        except Exception as e:
            sys.stdout.write('x')
            time.sleep(1)
            pass
    cash_balance = account_info['securitiesAccount']['currentBalances']['liquidationValue']
    cash_available_for_trade = account_info['securitiesAccount']['projectedBalances']['cashAvailableForTrading']
    while True:
        try:
            up_text, down_text = read_email_from_gmail()
            break
        except:
            sys.stdout.write('x')
            time.sleep(1)
            pass
    while True:
        try:

            market_hours = c.get_hours_for_single_market(c.Markets.EQUITY, datetime.datetime.now())
            marketstart = market_hours.json()['equity']['EQ']['sessionHours']['regularMarket'][0]['start']
            marketend = market_hours.json()['equity']['EQ']['sessionHours']['regularMarket'][0]['end']
            break
        except:
            sys.stdout.write('x')
            time.sleep(1)
            pass
    # test if we are in regular market hours
    #if datetime.datetime.now(datetime.datetime.fromisoformat(marketstart).tzinfo) >= (datetime.datetime.fromisoformat(marketstart)) and datetime.datetime.now(datetime.datetime.fromisoformat(marketstart).tzinfo) <= datetime.datetime.fromisoformat(marketend):
    if True:
        if up_text:
            if datetime.datetime.now(datetime.datetime.fromisoformat(marketstart).tzinfo) >= (datetime.datetime.fromisoformat(marketstart) + datetime.timedelta(minutes=15)):
            #if True:
                #uptext_handler
                symbols = parse_alert(up_text)
                if len(symbols) > 10:
                    reduced_symbols = random.sample(symbols, 10)  # pick 5 stocks at random, too many will take too long
                else:
                    reduced_symbols = symbols
                print('received buy signal, pulling {}'.format(reduced_symbols))
                positions = td_client_request('get_positions', c)
                positiondict = {}
                for p in positions['securitiesAccount']['positions']:
                    if p['instrument']['assetType'] == 'EQUITY':
                        positiondict[p['instrument']['symbol']] = p['longQuantity']
                symbols_i_own = [x for x in symbols if x in positiondict.keys()]
                reduced_symbols = [x for x in reduced_symbols if x not in symbols_i_own]
                if reduced_symbols:
                    prices = td_client_request('get_quotes', c, reduced_symbols)
                    # get list of symbols that I can afford
                    num_symbols = 30
                    if cash_available_for_trade > (cash_balance / num_symbols):
                        affordable_symbols = [x[0] for x in prices.items() if x[1]['lastPrice'] < cash_balance / num_symbols]
                        affordable_symbols = [x for x in affordable_symbols if x not in restricted_symbols]
                        if affordable_symbols:
                            for symbol in affordable_symbols:
                                #symbol_to_invest = random.choice(affordable_symbols)   # its a crapshoot so lets just choose a random one.
                                number_to_buy = math.floor((cash_balance / num_symbols) / prices[symbol]['lastPrice'])

                                orderinfo = {'symbol': symbol,
                                             'qty': number_to_buy,
                                             'price': prices[symbol]['lastPrice'],
                                             'stoploss': prices[symbol]['lastPrice'] - (prices[symbol]['lastPrice']*.05)}
                                td_client_request('place_order', c, orderinfo=orderinfo)

                    pass
        if down_text:
            positions = td_client_request('get_positions', c)
            positiondict = {}
            for p in positions['securitiesAccount']['positions']:
                if p['instrument']['assetType'] == 'EQUITY':
                    positiondict[p['instrument']['symbol']] = p['longQuantity']
            symbols = parse_alert(down_text)
            print('received sell signal, pulling {}'.format(symbols))
            symbols_i_own = [x for x in symbols if x in positiondict.keys()]
            for s in symbols_i_own:
                orderinfo = {'symbol': s,
                             'qty': positiondict[s]}
                td_client_request('sell_order', c, orderinfo=orderinfo)
                print('received sell signal for {}'.format(s))

            pass
        else:
            time.sleep(2)
            continue
    else:
        time.sleep(2)
        continue