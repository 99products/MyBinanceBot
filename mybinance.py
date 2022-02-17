import json
import time
import requests
import hashlib
import hmac
import datetime as dt
import db
import mybinance
import os

# config = json.load(open('config.json', 'r'))
api_key = os.getenv('binance_api_key')
secret_key = os.getenv('binance_secret_key')

BALANCE_URL = 'https://fapi.binance.com/fapi/v2/balance?{}&signature={}'
ACCOUNT_URL = 'https://fapi.binance.com/fapi/v2/account?{}&signature={}'
POSITIONS_URL = 'https://fapi.binance.com//fapi/v2/positionRisk?{}&signature={}'
KLINES_URL = 'https://fapi.binance.com/fapi/v1/continuousKlines?limit=5&pair=BTCUSDT&contractType=PERPETUAL&interval=1m'
FUNDING_URL = 'https://fapi.binance.com//fapi/v1/income?{}&signature={}'
TICKER_URL = 'https://api.binance.com/api/v3/ticker/price?symbol='


def binancerequest(url):
    timestamp = str(int(time.time_ns() / 1000000))
    query = 'timestamp=' + timestamp
    signature = hmac.new(bytes(secret_key, 'utf-8'), bytes(query, 'utf-8'), hashlib.sha256).hexdigest()

    url = url.format(query, signature)

    headers = {
        'X-MBX-APIKEY': api_key
    }

    response = requests.request("GET", url, headers=headers)
    return response


def fetchpositions():
    response = binancerequest(POSITIONS_URL)
    result: list = response.json()
    result = list(filter(lambda position: float(position['positionAmt']) != 0, result))
    result.sort(key=lambda position: float(position['unRealizedProfit']))
    return result


def showpositions():
    positions = fetchpositions()
    displaytext = ''
    for position in positions:
        displaytext = displaytext + fillspace(position['symbol'] + '@' + roundoff(position['markPrice'], 3),
                                              32) + fillspace(position['positionAmt'], 10) + roundoff(
            position['unRealizedProfit'], 2)
        displaytext = displaytext + '\n'
    # print(displaytext)


def fetchpnl():
    response = binancerequest(BALANCE_URL)
    pnl = float(list(filter(lambda account: account['asset'] == 'USDT', response.json()))[0]['crossUnPnl'])
    return pnl


def fundingfee():
    response = binancerequest(FUNDING_URL).json()
    totalfundfee = 0
    count = 0
    # print(len(response))
    firsttimestamp = ''
    for entry in response:
        if entry['incomeType'] == 'FUNDING_FEE':
            totalfundfee = totalfundfee + float(entry['income'])
        count = count + 1
        if count == 1:
            firsttimestamp = dt.datetime.fromtimestamp(int(entry['time']) / 1000).strftime('%Y-%m-%d %H:%M:%S')

    return totalfundfee, firsttimestamp


def fillspace(text: str, maxlen: int):
    spacestofill = maxlen - len(text)
    while (spacestofill > 0):
        text = text + ' '
        spacestofill = spacestofill - 1
    return text


def volumetracker():
    data = binancerequest(KLINES_URL).json()
    totallength = len(data)
    sumofvolumes = 0

    for entry in data[:-1]:
        sumofvolumes = sumofvolumes + float(entry[5])
    average = sumofvolumes / (totallength - 1)

    currentvolume = float(data[totallength - 1][5])
    lastprice = 0
    open = 0
    volume = 0
    if currentvolume > 1000:  # and currentvolume >2*average:
        open = float(data[totallength - 1][1])
        lastprice = float(data[totallength - 1][4])
        volume = currentvolume

    return volume, open, lastprice

def acccountinfo():
    account = binancerequest(ACCOUNT_URL).json()
    maintMargin = account['totalMaintMargin']
    marginBalance= account['totalMarginBalance']
    print(maintMargin+' '+marginBalance)
    return maintMargin,marginBalance


def ticker(symbol: str):
    response = binancerequest(TICKER_URL + symbol.upper())
    # print(response.status_code)
    return response.json()


def roundoff(number: str, precision: int):
    return number[:number.index('.') + precision + 1]


acccountinfo()
