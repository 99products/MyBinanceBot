import json
import mybinance

import telegram
from deta import App
from telegram.ext import Dispatcher, CallbackQueryHandler, CommandHandler
from queue import Queue
from fastapi import Request, FastAPI
import db

HELP_TEXT = 'Its my personal binance alert bot, checkout my source at https://github.com/99products/MyBinanceBot to setup your own'
CHANGE_PERCENT = 20
THRESHOLD_TO_NOTIFY = 5
app = App(FastAPI())
config = json.load(open('config.json', 'r'))
TELEGRAM_TOKEN = config['telegram_token']
TELEGRAM_CHAT_ID = config['my_telegram_id']

bot = telegram.Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot=bot, use_context=True, update_queue=Queue())


@app.get("/")
def hello_world():
    return "Working.."


@app.post("/")
async def process(request: Request):
    request_data = await request.json()
    update = telegram.Update.de_json(request_data, bot)
    dispatcher.process_update(update)
    if update.message:
        text = update.message.text.lower()
        if update.message.chat.id == TELEGRAM_CHAT_ID:
            if 'pnl' in text:
                showpnl(update)
            elif 'positions' in text:
                showpositions(update)
            elif 'fee' in text:
                fundingfee(update)
            elif 'margin' in text:
                margin(update)
            else:
                ticker(update)
        else:
            notsupported(update)
    return 'ok'


@app.lib.cron()
def schedule_balance(event):
    if event.type == 'cron':
        pnltracker()
        volumetracker()
    return 'ok'


def volumetracker():
    volume, open, close = mybinance.volumetracker()
    upordown = '🔼'
    if (float(close) < float(open)):
        upordown = '🔽'
    if volume > 0:
        bot.sendMessage(chat_id=TELEGRAM_CHAT_ID,
                        text=upordown + ' ' + str(volume) + ' ' + str(open) + ' to ' + str(close))


def notsupported(update):
    bot.sendMessage(chat_id=update.message.chat.id, text="The bot is reserved only for ThiyagaB. Contact @digi_nomad")


def showpnl(update):
    value = pnltracker()
    bot.sendMessage(chat_id=update.message.chat.id, text=roundoff(str(value), 2))


def fundingfee(update):
    value = mybinance.fundingfee()
    text = str(value[0]) + ' from ' + value[1]
    bot.sendMessage(chat_id=update.message.chat.id, text=text)


def showpositions(update):
    positions = mybinance.fetchpositions()
    maintMargin,marginBalance = mybinance.acccountinfo()
    displaytext = construct_positions_text(positions)
    displaytext = displaytext + '\n' + 'Maintenance Margin: ' + str(maintMargin) + '\n' + 'Margin Balance: ' + str(marginBalance)
    bot.sendMessage(chat_id=update.message.chat.id, text=displaytext, parse_mode="Markdown")


def construct_positions_text(positions):
    # positions = mybinance.fetchpositions()
    displaytext = "```\n"
    totalprofit = 0
    for position in positions:
        displaytext = displaytext + fillspace(position['symbol'] + '@' + roundoff(position['markPrice'], 3),
                                              20) + fillspace(position['positionAmt'], 7) + roundoff(
            position['unRealizedProfit'], 2)
        displaytext = displaytext + '\n'
        totalprofit = totalprofit + float(position['unRealizedProfit'])
    displaytext = "Total Profit: " + roundoff(str(totalprofit), 2) + "\n\n" + displaytext + "```"
    return displaytext


def fillspace(text: str, maxlen: int):
    spacestofill = maxlen - len(text)
    while (spacestofill > 0):
        text = text + ' '
        spacestofill = spacestofill - 1
    return text


def ticker(update):
    # print(update.message.chat.id)
    symbol = update.message.text
    if symbol.startswith('/'):
        symbol = symbol[1:]
    if symbol:
        if len(symbol) < 6: symbol = symbol + 'usdt'
        value = mybinance.ticker(symbol)
        if 'symbol' in value:
            tickertext = '/' + value['symbol'] + ' @ ' + value['price']
            bot.sendMessage(chat_id=update.message.chat.id, text=tickertext)


def start(update):
    # print(update.message.chat.id)
    bot.sendMessage(chat_id=update.message.chat.id, text=HELP_TEXT)


def pnltracker():
    pnl = mybinance.fetchpnl()
    data = db.get(mybinance.api_key)
    # print(data)
    positions = mybinance.fetchpositions()
    maintMargin,marginBalance=mybinance.acccountinfo()

    oldpnl = 0
    if data and len(data) > 0:
        oldpnl = data['pnl']
    else:
        db.insert({'pnl': pnl, 'key': mybinance.api_key, "positions": positions})
    if checkMargin(maintMargin,marginBalance) or checkrule(oldpnl, pnl, data, positions):
        db.insert({'pnl': pnl, 'key': mybinance.api_key, "positions": positions})
        displayText = construct_positions_text()
        displayText = displayText + '\n' + 'Maintenance Margin: ' + str(maintMargin) + '\n' + 'Margin Balance: ' + str(marginBalance)
        bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=displayText, parse_mode="Markdown",
                        disable_notification=False)
    else:
        print(pnl)
    return pnl

def checkMargin(maintMargin,marginBalance):
    if(float(maintMargin)/float(marginBalance)>0.2):
        return True

def checkrule(oldpnl, pnl, data, positions):
    global CHANGE_PERCENT
    if 'change' in data:
        CHANGE_PERCENT = data['change']
    if oldpnl < -100:
        CHANGE_PERCENT = CHANGE_PERCENT/2
    if len(positions) != len(data['positions']) or checkQuantities(data['positions'], positions):
        return True
    return abs(pnl) > THRESHOLD_TO_NOTIFY and abs(oldpnl - pnl) > abs(oldpnl * (CHANGE_PERCENT / 100))


def checkQuantities(oldpositions, positions):
    for position in positions:
        for oldposition in oldpositions:
            if position['symbol'] == oldposition['symbol'] and position['positionSide'] == oldposition['positionSide']:
                if float(position['positionAmt']) != float(oldposition['positionAmt']):
                    return True

    return False

def margin(update):
    maintMargin,marginBalance = mybinance.acccountinfo()
    bot.sendMessage(chat_id=update.message.chat.id, text=maintMargin + ' ' + marginBalance)


# lazy to find the standard method
def roundoff(number: str, precision: int):
    if '.' in number:
        return number[:number.index('.') + precision + 1]
    else:
        return number
