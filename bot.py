#!/usr/bin/env python

from keys import ameritrade, gmailpass

from ratelimit import limits, sleep_and_retry
import sys
from bs4 import BeautifulSoup

from apscheduler.schedulers.background import BackgroundScheduler

import datetime
from tda import auth
from tda.client import Client
from tda.orders.generic import OrderBuilder
from tda.orders.equities import equity_sell_limit, equity_buy_market,equity_buy_limit, equity_sell_market
from tda.orders.common import Duration, Session,OrderType,StopPriceLinkType,StopPriceLinkBasis, first_triggers_second
import time
import imaplib
import email
import traceback
import random
import math

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
                            msg = email.message_from_bytes(response[1])
                            # decode the email subject
                            soup = BeautifulSoup(msg._payload, 'html.parser')
                            try:
                                if 'AA_aterhune1984' in soup.get_text() or ' SOLD ' in soup.get_text():
                                    quit=True
                                    imap.store(mail, "+FLAGS", "\\Deleted")
                                    break
                                if 'tradingview_macd_long_sell' in soup.get_text().split('\nAlert')[1].replace('=\r\n', ''):
                                    quit = True
                                    down_text = soup.get_text().split('\nAlert')[1]
                                    imap.store(mail, "+FLAGS", "\\Deleted")
                                    break
                                    # mark the mail as deleted
                                elif 'tradingview_macd_long' in soup.get_text().split('\nAlert')[1].replace('=\r\n', ''):
                                    quit = True
                                    up_text = soup.get_text().split('\nAlert')[1]
                                    imap.store(mail, "+FLAGS", "\\Deleted")
                                    break
                            except Exception as e:
                                print(e)
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




@sleep_and_retry
@limits(calls=120, period=60)
def td_client_request(option, c, ticker=False, orderinfo=False):
    num = 0
    while num <= 10:
        try:
            if option == 'get_price_history':
                data = c.get_price_history(ticker,
                                           frequency_type=Client.PriceHistory.FrequencyType.MINUTE,
                                           frequency=Client.PriceHistory.Frequency.EVERY_FIFTEEN_MINUTES,
                                           start_datetime=datetime.datetime.now() - datetime.timedelta(60),
                                           end_datetime=datetime.datetime.now(),
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
                obj1 = equity_buy_market(orderinfo['symbol'], orderinfo['qty'])
                obj1.set_session(Session.NORMAL)
                obj1.set_duration(Duration.DAY)

                order1 = obj1.build()
                x = c.place_order(TD_ACCOUNT, order1)
                time.sleep(1)

                if str(x.status_code).startswith('2'):


                    # we are going to place a trailing stop order for the order we just placed.
                    obj2 = equity_sell_market(orderinfo['symbol'], orderinfo['qty'])
                    obj2.set_order_type(OrderType.STOP)
                    obj2.set_session(Session.NORMAL)
                    obj2.set_duration(Duration.GOOD_TILL_CANCEL)
                    obj2.set_stop_price_link_basis(StopPriceLinkBasis.LAST)
                    obj2.set_stop_price_link_type(StopPriceLinkType.VALUE)
                    stoploss = round(orderinfo['stoploss'], 2)
                    if stoploss == 0.00:
                        stoploss = 0.01
                    obj2.set_stop_price(stoploss)
                    order2 = obj2.build()
                    x = c.place_order(TD_ACCOUNT, order2)
                    if str(x.status_code).startswith('2'):
                        print('placed both orders succesfully')
                        return True
                    else:
                        print('something went wrong')
                else:
                    print('something went wrong')
            if option == 'get_positions':
                return c.get_accounts(fields=Client.Account.Fields.POSITIONS).json()[0]
            if option == 'sell_order':
                obj = equity_sell_market(orderinfo['symbol'], orderinfo['qty'])
                obj.set_session(Session.NORMAL)
                obj.set_duration(Duration.DAY)
                order = obj.build()
                x = c.place_order(TD_ACCOUNT, order)
                if str(x.status_code).startswith('2'):
                    return True
                else:
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



token_path = './token.pickle'
api_key = '{}@AMER.OAUTHAP'.format(ameritrade)
redirect_uri = 'http://localhost:8000'
restricted_symbols = ['RXT']

while True:
    backtest_dict = {}
    try:
        c = auth.client_from_token_file(token_path, api_key)
    except FileNotFoundError:
        from selenium import webdriver

        with webdriver.PhantomJS() as driver:
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
    cash_available_for_trade = account_info['securitiesAccount']['currentBalances']['cashAvailableForTrading']
    up_text, down_text = read_email_from_gmail()
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
    if datetime.datetime.now(datetime.datetime.fromisoformat(marketstart).tzinfo) >= datetime.datetime.fromisoformat(marketstart) and datetime.datetime.now(datetime.datetime.fromisoformat(marketstart).tzinfo) <= datetime.datetime.fromisoformat(marketend):
        if up_text:
            #uptext_handler
            symbols = parse_alert(up_text)
            if len(symbols) > 5:
                reduced_symbols = random.sample(symbols, 5)  # pick 5 stocks at random, too many will take too long
            else:
                reduced_symbols = symbols
            print('received buy signal, pulling {}'.format(reduced_symbols))

            if reduced_symbols:
                prices = td_client_request('get_quotes', c, reduced_symbols)
                # get list of symbols that I can afford
                num_symbols = 10
                if cash_available_for_trade > (cash_balance / num_symbols):
                    affordable_symbols = [x[0] for x in prices.items() if x[1]['lastPrice'] < cash_balance / num_symbols]
                    affordable_symbols = [x for x in affordable_symbols if x not in restricted_symbols]
                    if affordable_symbols:
                        symbol_to_invest = random.choice(affordable_symbols)   # its a crapshoot so lets just choose a random one.
                        number_to_buy = math.floor((cash_balance / num_symbols) / prices[symbol_to_invest]['lastPrice'])
                        print('buying {} of {}  at {} with a stoploss of {}'.format(number_to_buy,
                                                                                    symbol_to_invest,
                                                                                    prices[symbol_to_invest]['lastPrice'],
                                                                                    prices[symbol_to_invest]['lastPrice'] - (prices[symbol_to_invest]['lastPrice']*.02)))
                        orderinfo = {'symbol': symbol_to_invest,
                                     'qty': number_to_buy,
                                     'price': prices[symbol_to_invest]['lastPrice'],
                                     'stoploss': prices[symbol_to_invest]['lastPrice'] - (prices[symbol_to_invest]['lastPrice']*.02)}
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