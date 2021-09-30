import json
import binance

import telegram
from deta import App
from telegram.ext import Dispatcher, CallbackQueryHandler, CommandHandler
from queue import Queue
from fastapi import Request, FastAPI
import db

HELP_TEXT = 'Its my personal binance alert bot, checkout my source to setup your own'
CHANGE_PERCENT = 20
THRESHOLD_TO_NOTIFY = 5
app = App(FastAPI())
config=json.load(open('config.json', 'r'))
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
            else:
                start(update)
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
    volume,open,close=binance.volumetracker()
    if volume>0:
        bot.sendMessage(chat_id=TELEGRAM_CHAT_ID,text='BTC Volume change: #'+volume+' '+'Open: '+open+' Close: '+close)

def notsupported(update):
    bot.sendMessage(chat_id=update.message.chat.id, text="The bot is reserved only for ThiyagaB. Contact @digi_nomad")

def showpnl(update):
    value = pnltracker()
    bot.sendMessage(chat_id=update.message.chat.id, text=roundoff(str(value), 2))


def showpositions(update):
    positions = binance.fetchpositions()
    displaytext = "```\n"
    totalprofit=0
    for position in positions:
        displaytext = displaytext + fillspace(position['symbol'] + '@' + roundoff(position['markPrice'], 3),
                                              20) + fillspace(position['positionAmt'], 7) + roundoff(
            position['unRealizedProfit'], 2)
        displaytext = displaytext + '\n'
        totalprofit=totalprofit+float(position['unRealizedProfit'])
    displaytext=displaytext+"\nTotal Profit: "+roundoff(str(totalprofit),2)+"```"

    bot.sendMessage(chat_id=update.message.chat.id, text=displaytext,parse_mode="Markdown")


def fillspace(text: str, maxlen: int):
    spacestofill = maxlen - len(text)
    while (spacestofill > 0):
        text = text + ' '
        spacestofill = spacestofill - 1
    return text


def start(update):
    print(update.message.chat.id)
    bot.sendMessage(chat_id=update.message.chat.id, text=HELP_TEXT)


def pnltracker():
    pnl = binance.fetchpnl()
    data = db.get(binance.api_key)
    print(data)
    if data and len(data) > 0:
        oldpnl = data['pnl']
    else:
        db.insert({'pnl': pnl, 'key': binance.api_key})
    if checkrule(oldpnl, pnl, data):
        db.insert({'pnl': pnl, 'key': binance.api_key})
        print('changed: ' + str(oldpnl - pnl))
        text = 'Overall pnl ' + ('increased' if pnl > oldpnl else 'decreased') + ' by more than ' + str(
            CHANGE_PERCENT) + '% from ' + roundoff(str(
            oldpnl), 2) + ' to ' + roundoff(str(pnl), 2)
        bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=text)
    else:
        print(pnl)
    return pnl


def checkrule(oldpnl, pnl, data):
    global CHANGE_PERCENT
    if 'change' in data:
        CHANGE_PERCENT = data['change']
    return abs(pnl) > THRESHOLD_TO_NOTIFY and abs(oldpnl - pnl) > abs(oldpnl * (CHANGE_PERCENT / 100))


# lazy to find the standard method
def roundoff(number: str, precision: int):
    return number[:number.index('.') + precision + 1]


