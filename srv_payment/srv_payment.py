import flask
from flask_api import status
import psycopg2

import sys
from urllib.request import Request
from time import sleep
import uuid

import common.services as services
from common.api_messages import *


app = flask.Flask(__name__)

while True:
    try:
        conn = psycopg2.connect(
            host="postgres",
            database="payments",
            user="program",
            password="test")
        break
    except:
        print('Reconnecting to DB...')
        sleep(3)

# psycopg2.extras.register_uuid()


def getPayment(uid: str) -> PaymentInfo:
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT status, price FROM payment WHERE payment_uid = %s', (uid,))
        return PaymentInfo(*cursor.fetchone())


def createPayment(price: int) -> str:
    payment_uuid = str(uuid.uuid4())
    with conn.cursor() as cursor:
        cursor.execute(
            "INSERT INTO payment(payment_uid, status, price) VALUES (%s, 'PAID', %s)",
            (payment_uuid, price))
    conn.commit()
    return payment_uuid


def cancelPayment(uid: str):
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE payment SET status = 'CANCELED' WHERE payment_uid = %s", (uid,))
    conn.commit()


@app.route('/payment', methods=['GET'])
def paymentRoute():
    uid = flask.request.args.get('uid')
    payment = getPayment(uid)
    resp = flask.Response(payment.toJSON())
    resp.headers['Content-Type'] = 'application/json'
    return resp


# Returns UUID
@app.route('/create_payment', methods=['GET'])
def crPaymentRoute():
    price = int(flask.request.args.get('price'))
    payment = createPayment(price)
    resp = flask.Response(payment)
    resp.headers['Content-Type'] = 'application/text'
    return resp


@app.route('/cancel', methods=['GET'])
def paymentCancelRoute():
    uid = flask.request.args.get('uid')
    cancelPayment(uid)
    resp = flask.Response('')
    resp.headers['Content-Type'] = 'application/text'
    return resp


app.run(host="0.0.0.0", port=services.PAYMENT_PORT)
