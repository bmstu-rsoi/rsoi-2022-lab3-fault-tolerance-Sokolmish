import flask
from flask_api import status
import psycopg2

from urllib.request import Request
from time import sleep
import json

import common.services as services


app = flask.Flask(__name__)

while True:
    try:
        conn = psycopg2.connect(
            host="postgres",
            database="loyalties",
            user="program",
            password="test")
        break
    except:
        print('Reconnecting to DB...')
        sleep(3)


def calcStatus(rcnt: int) -> str:
    if rcnt > 20:
        return ['GOLD', 10]
    elif rcnt > 10:
        return ['SILVER', 7]
    else:
        return ['BRONZE', 5]


def getReservCount(name: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT reservation_count FROM loyalty WHERE username = %s', (name,))
        return int(cursor.fetchall()[0][0])


def getDiscount(name: str) -> str:
    return json.dumps({'discount': calcStatus(getReservCount(name))[1]}, indent=None)


def updateRcnt(name: str, delta: int):
    with conn.cursor() as cursor:
        cursor.execute(
            'UPDATE loyalty SET reservation_count = reservation_count + %s WHERE username = %s',
            (delta, name))


def getStatus(name: str) -> str:
    rcnt = getReservCount(name)
    status = calcStatus(rcnt)
    return json.dumps({
        "status": status[0],
        "discount": status[1],
        "reservationCount": rcnt,
    }, indent=None)


@app.route('/discount', methods=['GET'])
def discountRoute():
    name = flask.request.args.get('username')
    resp = flask.Response(getDiscount(name))
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/update', methods=['GET'])
def updateRoute():
    name = flask.request.args.get('username')
    delta = flask.request.args.get('delta')
    updateRcnt(name, delta)
    resp = flask.Response('[]')
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/status', methods=['GET'])
def statusRoute():
    name = flask.request.args.get('username')
    resp = flask.Response(getStatus(name))
    resp.headers['Content-Type'] = 'application/json'
    return resp


app.run(host="0.0.0.0", port=services.LOYALTY_PORT)
