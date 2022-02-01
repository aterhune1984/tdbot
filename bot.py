#!/usr/bin/env python

from keys import ameritrade, GMAILPASS

from ratelimit import limits, sleep_and_retry
import sys
from bs4 import BeautifulSoup
import pandas_ta as ta
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
FROM_PWD = GMAILPASS
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
        high_volume = False
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
                            #if timediff.total_seconds() < 300:
                            if True:
                                try:
                                    soup = BeautifulSoup(response[1], 'html.parser')
                                except:
                                    print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'i failed')
                                try:
                                    if 'AA_aterhune1984' in soup.get_text() or ' SOLD ' in soup.get_text():
                                        quit=True
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                    elif 'ichimoku_filter' in ','.join(soup.get_text().split('\nAlert')).replace('=\r\n',''):
                                        quit = True
                                        up_text = soup.get_text().split('\nAlert')[1]
                                        print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), "Received email...")
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                    #    # mark the mail as deleted
                                    else:
                                        quit = True
                                        imap.store(mail, "+FLAGS", "\\Deleted")
                                        break
                                except Exception as e:
                                    print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), e)

                    if quit:
                        break

            imap.expunge()
        imap.close()
        imap.logout()
        return up_text, down_text, high_volume


    except Exception as e:
        traceback.print_exc()
        print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), str(e))


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
    while num <= 1:
        time.sleep(1)
        try:
            if option == 'get_price_history':
                data = c.get_price_history(ticker,
                                           frequency_type=Client.PriceHistory.FrequencyType.DAILY,
                                           frequency=Client.PriceHistory.Frequency.DAILY,
                                           period_type=Client.PriceHistory.PeriodType.YEAR,
                                           period=Client.PriceHistory.Period.TWO_YEARS,
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

                canbuy = False

                data = c.get_price_history(ticker,
                                           frequency_type=Client.PriceHistory.FrequencyType.DAILY,
                                           frequency=Client.PriceHistory.Frequency.DAILY,
                                           period_type=Client.PriceHistory.PeriodType.YEAR,
                                           period=Client.PriceHistory.Period.TWO_YEARS,
                                           need_extended_hours_data=False)
                data_json = data.json()
                df = ta.DataFrame(data_json['candles'], columns=['open', 'high', 'low', 'close', 'volume', 'datetime'])
                df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=200)
                atrval = float(df[-1:]['atr'])

                max_to_risk = orderinfo['cash_balance'] * .02
                if orderinfo['volume']:

                    shares_to_risk_max = int(max_to_risk/round(atrval*2, 2)//1)
                else:
                    shares_to_risk_max = int(max_to_risk/round(atrval*2, 2)//1)

                cost_to_buy_shares = orderinfo['price'] * shares_to_risk_max
                max_cost_per_symbol = int((orderinfo['cash_balance'] / orderinfo['num_symbols']) // 1)
                if cost_to_buy_shares < max_cost_per_symbol:
                    num_to_buy = shares_to_risk_max
                else:
                    num_to_buy = int(max_cost_per_symbol // orderinfo['price'])  # number I can afford
                if (num_to_buy*orderinfo['price']) < orderinfo['cash_available_for_trade'] and num_to_buy != 0:
                    canbuy = True
                else:
                    pass

                if canbuy:
                    if num_to_buy > 0:
                        orderinfo['volume'] = False
                        if orderinfo['volume']:


                            # todo not implimented yet as i'm not sure how to reserve 1 division of my balance to keep on hold for volume...

                            obj1 = equity_buy_market(orderinfo['symbol'], num_to_buy)
                            obj1.set_session(Session.NORMAL)
                            obj1.set_duration(Duration.DAY)
                            obj2 = equity_sell_market(orderinfo['symbol'], num_to_buy)
                            obj2.set_order_type(OrderType.TRAILING_STOP)
                            obj2.set_session(Session.NORMAL)
                            obj2.set_duration(Duration.GOOD_TILL_CANCEL)
                            obj2.set_stop_price_offset(round(atrval * 2, 1))  # offset in dollars
                            obj2.set_stop_price_link_basis(StopPriceLinkBasis.LAST)
                            obj2.set_stop_price_link_type(StopPriceLinkType.VALUE)
                            x = c.place_order(TD_ACCOUNT,  first_triggers_second(obj1, obj2).build())
                            if str(x.status_code).startswith('2'):
                                print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'placed both orders succesfully for {} of {}'.format(num_to_buy, orderinfo['symbol']))
                                return True
                            else:
                                num += 1
                                print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'something went wrong')
                        if not orderinfo['volume']:
                            obj1 = equity_buy_market(orderinfo['symbol'], num_to_buy)
                            obj1.set_session(Session.NORMAL)
                            obj1.set_duration(Duration.DAY)

                            obj2 = equity_sell_market(orderinfo['symbol'], num_to_buy)
                            obj2.set_order_type(OrderType.STOP)
                            obj2.set_session(Session.NORMAL)
                            obj2.set_duration(Duration.GOOD_TILL_CANCEL)
                            obj2.set_stop_price(orderinfo['price'] - round(atrval*2, 2))  # offset in dollars
                            obj2.set_stop_price_link_basis(StopPriceLinkBasis.LAST)
                            obj2.set_stop_price_link_type(StopPriceLinkType.VALUE)


                            obj3 = equity_sell_limit(orderinfo['symbol'], num_to_buy, (orderinfo['price']+(atrval*6)))
                            obj3.set_order_type(OrderType.LIMIT)
                            obj3.set_session(Session.NORMAL)
                            obj3.set_duration(Duration.GOOD_TILL_CANCEL)


                            x = c.place_order(TD_ACCOUNT, first_triggers_second(obj1,  one_cancels_other(obj2, obj3)).build())
                            if str(x.status_code).startswith('2'):
                                print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'placed both orders succesfully for {} of {}'.format(num_to_buy, orderinfo['symbol']))
                                return True
                            else:
                                num += 1
                                print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'something went wrong')
                else:
                    return False

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
                                print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'canceled trailing stop order successfully')

                                obj = equity_sell_market(orderinfo['symbol'], orderinfo['qty'])
                                obj.set_session(Session.NORMAL)
                                obj.set_duration(Duration.DAY)
                                order = obj.build()
                                x = c.place_order(TD_ACCOUNT, order)
                                if str(x.status_code).startswith('2'):
                                    print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'placed sell order successfully')
                                    return True
                                else:
                                    num += 1
                                    print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'something went wrong')
        except Exception as e:
            num += 1
            time.sleep(60)
    return False



def parse_alert(text):
    try:
        symbols = text.replace('=\r\n', '').split(' w')[0].split(': ')[-1].split(', ')
    except Exception:
        try:
            symbols = [text.split('=\r\n ')[1].split(' was added')[0]]
        except Exception as e:
            print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), e)
    return symbols


global runningpl
runningpl = 0


token_path = '{}/token.pickle'.format(os.getcwd())
api_key = '{}@AMER.OAUTHAP'.format(ameritrade)
redirect_uri = 'http://localhost:8000'
restricted_symbols = ['RXT']
print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'Starting TDBOT...')

while True:
    backtest_dict = {}
    try:
        c = auth.client_from_token_file(token_path, api_key)
    except:
        from selenium import webdriver

        with webdriver.Chrome() as driver:
            c = auth.client_from_login_flow(
                driver, api_key, redirect_uri, token_path)
    while True:
        try:
            account_info = c.get_accounts().json()[0]
            break
        except Exception as e:
            print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'getting accounts ... x')
            time.sleep(60)
            pass
    try:
        cash_balance = account_info['securitiesAccount']['currentBalances']['liquidationValue']
        cash_available_for_trade = account_info['securitiesAccount']['projectedBalances']['cashAvailableForTrading']
    except KeyError:
        cash_balance = 0.0
        cash_available_for_trade = 0.0
    while True:
        try:

            up_text, down_text, high_volume = read_email_from_gmail()
            break
        except Exception as e:
            print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'getting email ... x')
            time.sleep(60)
            pass
    while True:
        try:
            market_hours = c.get_hours_for_single_market(c.Markets.EQUITY, datetime.datetime.now())
            marketstart = market_hours.json()['equity']['EQ']['sessionHours']['regularMarket'][0]['start']
            marketend = market_hours.json()['equity']['EQ']['sessionHours']['regularMarket'][0]['end']
            break
        except Exception as e:
            print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'getting market hours ... x')
            time.sleep(60)
            pass
    # test if we are in regular market hours
    if (datetime.datetime.fromisoformat(marketstart)) <= datetime.datetime.now(datetime.datetime.fromisoformat(marketstart).tzinfo) <= datetime.datetime.fromisoformat(marketend):

        num_symbols = 30
        numforvolspike = cash_balance / (num_symbols + 1)

        if high_volume:
            print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'drop everything and buy!!!!')
            continue
            symbols = parse_alert(up_text)
            positions = td_client_request('get_positions', c)
            positions = positions['securitiesAccount'].get('positions')
            positiondict = {}
            if positions:
                for p in positions:
                    if p['instrument']['assetType'] == 'EQUITY':
                        positiondict[p['instrument']['symbol']] = p['longQuantity']
            symbols_i_own = [x for x in symbols if x in positiondict.keys()]
            reduced_symbols = [x for x in symbols if x not in symbols_i_own]
            prices = td_client_request('get_quotes', c, reduced_symbols)
            affordable_symbols = [x[0] for x in prices.items() if x[1]['lastPrice'] < cash_available_for_trade]
            affordable_symbols = [x for x in affordable_symbols if x not in restricted_symbols]
            symbol_to_buy = random.choice(affordable_symbols)
            orderinfo = {'symbol': symbol_to_buy,
                         'price': prices[symbol_to_buy]['lastPrice'],
                         'cash_available_for_trade': cash_available_for_trade,
                         'cash_balance': cash_balance,
                         'num_symbols': False,
                         'volume': True,
                         'numforvolspike': numforvolspike}
            td_client_request('place_order', c, ticker=symbol_to_buy, orderinfo=orderinfo)

        if up_text and not high_volume:
            symbols = parse_alert(up_text)
            print(datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p"), 'received buy signal, pulling {}'.format(symbols))
            #uptext_handler
            if len(symbols) > 10:
                reduced_symbols = random.sample(symbols, 10)  # pick 10 stocks at random, too many will take too long
            else:
                reduced_symbols = symbols

            positions = td_client_request('get_positions', c)
            positions = positions['securitiesAccount'].get('positions')
            positiondict = {}
            if positions:
                for p in positions:
                    if p['instrument']['assetType'] == 'EQUITY':
                        positiondict[p['instrument']['symbol']] = p['longQuantity']
            symbols_i_own = [x for x in symbols if x in positiondict.keys()]
            reduced_symbols = [x for x in reduced_symbols if x not in symbols_i_own]
            if reduced_symbols:
                prices = td_client_request('get_quotes', c, reduced_symbols)
                # get list of symbols that I can afford

                affordable_symbols = [x[0] for x in prices.items() if x[1]['lastPrice'] < cash_balance / num_symbols]
                affordable_symbols = [x for x in affordable_symbols if x not in restricted_symbols]
                if affordable_symbols:
                    for symbol in affordable_symbols:
                        cash_available_for_trade = account_info['securitiesAccount']['projectedBalances'][
                            'cashAvailableForTrading']
                        if cash_available_for_trade > prices[symbol]['lastPrice']:
                            #symbol_to_invest = random.choice(affordable_symbols)   # its a crapshoot so lets just choose a random one.
                            #number_to_buy = math.floor((cash_balance / num_symbols) / prices[symbol]['lastPrice'])
                            #print('buying {} of {}  at {}'.format(number_to_buy, symbol, prices[symbol]['lastPrice']))
                            orderinfo = {'symbol': symbol,
                                         'price': prices[symbol]['lastPrice'],
                                         'cash_available_for_trade': cash_available_for_trade,
                                         'cash_balance': cash_balance,
                                         'num_symbols': num_symbols,
                                         'volume': False,
                                         'numforvolspike': numforvolspike}
                            td_client_request('place_order', c, ticker=symbol, orderinfo=orderinfo)

                pass
        #if down_text:
        #    positions = td_client_request('get_positions', c)
        #    positiondict = {}
        #    for p in positions['securitiesAccount']['positions']:
        #        if p['instrument']['assetType'] == 'EQUITY':
        #            positiondict[p['instrument']['symbol']] = p['longQuantity']
        ##    symbols = parse_alert(down_text)
        #    print('received sell signal, pulling {}'.format(symbols))
        #    symbols_i_own = [x for x in symbols if x in positiondict.keys()]
        #    for s in symbols_i_own:
        #        orderinfo = {'symbol': s,
        #                     'qty': positiondict[s]}
        #        td_client_request('sell_order', c, orderinfo=orderinfo)
        #        print('received sell signal for {}'.format(s))

        #    pass
        else:
            time.sleep(300)
            continue

    else:
        time.sleep(300)
        continue
    time.sleep(300)

