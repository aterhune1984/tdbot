from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
#from functions import click, webdriver, show_me, get, find
import time
import numpy as np
from selenium.webdriver import Firefox
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from random import randint
url = 'https://www.tradingview.com/chart/02A8Mtco/'  # enter your trading view profile link here.
min_value = 1  # enter your minimum stop loss value.
max_value = 50  # enter your maximum stop loss value.
increment = 1  # You can increment count in decimals or in whole numbers.
range = np.arange(min_value, max_value, increment)


def run_script():
    """find the best stop loss value."""
    opts = Options()
    user='aterhune1984'

    browser = Firefox(options=opts)
    browser.get("https://www.tradingview.com/#signin")
    WebDriverWait(browser, 600).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[6]/div/div[2]/div/div/div/div/div/div/div[1]/div[4]/div/span')))
    time.sleep(randint(1, 4))
    browser.find_element_by_xpath('/html/body/div[6]/div/div[2]/div/div/div/div/div/div/div[1]/div[4]/div/span').click()
    WebDriverWait(browser, 600).until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id,'email-signin__user-name-input_')]")))
    time.sleep(randint(1, 4))

    # email-signin__user-name-input__75b8e4e7-dcde-4d45-8c2e-89330575b293
    username = browser.find_element_by_xpath("//*[contains(@id,'email-signin__user-name-input_')]")
    time.sleep(randint(1, 4))

    username.send_keys(user)
    password = browser.find_element_by_xpath("//*[contains(@id,'email-signin__password-input_')]")
    time.sleep(randint(1, 4))

    password.send_keys('l+<9UgZr)GMK@&18df<RQuWQrl-,}Gt')
    submit_button = browser.find_element_by_xpath('/html/body/div[6]/div/div[2]/div/div/div/div/div/div/form/div[5]/div[2]/button/span[2]')
    time.sleep(randint(1, 4))

    submit_button.click()
    WebDriverWait(browser, 600).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[3]/div[6]/div/div/div/div/div/div/div[1]/div/div[1]/div[1]/h2/a')))

    browser.get('https://www.tradingview.com/chart/1WKRpxiU/')
    while True:
        try:
            input("Press Enter to continue...")
            totalprofit = 0
            positive = 0
            symbols = ['ADIL','AFMD','CAPR','CTXR','GROY','ORGS','SDPI','SND','WPG']
            for s in symbols:
                WebDriverWait(browser, 2).until(EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="header-toolbar-symbol-search"]')))
                searchfield = browser.find_element_by_xpath('//*[@id="header-toolbar-symbol-search"]')
                searchfield.click()
                WebDriverWait(browser, 2).until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, '.search-Hsmn_0WX')))
                symbolbar = browser.find_element_by_css_selector('.search-Hsmn_0WX')
                symbolbar.send_keys(s)
                symbolbar.send_keys(Keys.ENTER)
                try:
                    WebDriverWait(browser, 10).until(EC.text_to_be_present_in_element(
                        (By.CSS_SELECTOR, '.report-data'), 'Net Profit'))
                    time.sleep(1)
                    profit = browser.find_element_by_css_selector('.report-data')
                    number = str(float(profit.text.split('$\u2009')[1].split('\n')[0]))
                    print(s + " " + number)
                    if float(number) > 0:
                        positive += 1
                    totalprofit += float(profit.text.split('$\u2009')[1].split('\n')[0])
                except:
                    totalprofit += 0

            print("    " + str(totalprofit))
            print(str(positive) + ' / ' + str(len(symbols)))
        except Exception as e:
            print('try again')
            pass
    # // *[ @ id = "email-signin__password-input__7bba0683-9868-4eb9-930b-b1f39cde1c39"]
    # // *[ @ id = "email-signin__user-name-input__75b8e4e7-dcde-4d45-8c2e-89330575b293"]
#  l+<9UgZr)GMK@&18df<RQuWQrl-,}Gt
    print('now what')
    #click.strategy_tester()
    ##try:
    #    click.overview()
    #except NoSuchElementException:
    #    time.sleep(1)
    #    click.overview()

    print("Generating Max Profit For Stop Loss.\n")
    print("Loading script...")
    #for number in range:
    #    count = round(number, 2)
    #    try:
    #        click.settings_button(wait)
    #        click.stoploss_input(count, wait)
    #        get.net_profit(count, wait)
    #    except (StaleElementReferenceException, TimeoutException, NoSuchElementException):
    #        print("script has timed out.")
    #        break

    # adding the new value to your strategy.
    #click.settings_button(wait)
    #best_key = find.best_key()
    #click.stoploss_input(best_key, wait)
    #time.sleep(.5)

    print("\n----------Results----------\n")
    #click.overview()
    #show_me.best_stoploss()
    #click.performance_summary()
    #show_me.total_closed_trades()
    #show_me.win_rate()
    #show_me.net_profit()
    #show_me.max_drawdown()
    #show_me.sharpe_ratio()
    #show_me.win_loss_ratio()
    #show_me.avg_win_trade()
    #show_me.avg_loss_trade()
    #show_me.avg_bars_in_winning_trades()
    # show_me.gross_profit()
    # show_me.gross_loss()
    # show_me.buy_and_hold_return()
    # show_me.max_contracts_held()
    # show_me.open_pl()
    # show_me.commission_paid()
    # show_me.total_open_trades()
    # show_me.number_winning_trades()
    # show_me.number_losing_trades()
    # show_me.percent_profitable()
    # show_me.avg_trade()
    # show_me.largest_win_trade()
    # show_me.largest_loss_trade()
    # show_me.avg_bars_in_trades()
    # show_me.avg_bars_in_losing_trades()


if __name__ == '__main__':
    run_script()
