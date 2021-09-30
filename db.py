from deta import Deta
import json

deta_key = json.load(open('config.json', 'r'))['deta_key']
db = Deta(deta_key)
data = db.Base('binance_alerts')


def get(key: str):
    value = data.get(key)
    return value


def update(key: str, updates: dict):
    data.update(updates, key)


def insert(alert):
    data.put(alert)


def delete(key: str):
    data.delete(key)
