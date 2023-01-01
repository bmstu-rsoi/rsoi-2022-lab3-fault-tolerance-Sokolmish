import sys
import threading
from time import sleep
import flask
from flask_api import status

import urllib.parse
import json
import requests
import datetime
from circuitbreaker import circuit

import common.services as services
from common.api_messages import *


app = flask.Flask(__name__)


delayed_tasks = []


@circuit
def getLoyaltyStatus(username: str):
    return requests.get(
        f'{services.LOYALTY_ADDR}/status?username={urllib.parse.quote(username)}'
    )


@circuit
def getLoyaltyDiscount(username: str) -> int:
    return requests.get(
        f'{services.LOYALTY_ADDR}/discount?username={urllib.parse.quote(username)}'
    ).json()['discount']


@app.route('/api/v1/hotels', methods=['GET'])
def hotelsRoute():
    page = int(flask.request.args.get('page', '0'))
    size = int(flask.request.args.get('size', '100'))
    r = requests.get(
        f'{services.RESERVATION_ADDR}/all_hotels?page={page}&size={size}')
    if r.status_code != status.HTTP_200_OK:
        return flask.Response('Smth went wrong', status.HTTP_400_BAD_REQUEST)
    resp = flask.Response(r.text)
    resp.headers['Content-Type'] = 'application/json'
    return resp


def get_user_reservations(name: str):
    r1 = requests.get(
        f'{services.RESERVATION_ADDR}/reservations?name={urllib.parse.quote(name)}').json()
    reservations = []
    for e in r1:
        r2 = requests.get(
            f'{services.PAYMENT_ADDR}/payment?uid={e["payment_uid_"]}').json()
        e.pop('payment_uid_', None)
        reservations.append(Reservation(payment=PaymentInfo(**r2), **e))
    return reservations


@app.route('/api/v1/me', methods=['GET'])
def meRoute():
    name = flask.request.headers.get('X-User-Name')
    reservations = get_user_reservations(name)
    try:
        loyalty = getLoyaltyStatus(name).json()
    except:
        loyalty = None

    res_dict = {
        'reservations': [],
        'loyalty': [],
    }
    if reservations is not None:
        res_dict['reservations'] = reservations
    if loyalty is not None:
        res_dict['loyalty'] = loyalty

    res = json.dumps(res_dict, indent=None, cls=MyEncoder)

    resp = flask.Response(res)
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/api/v1/reservations', methods=['GET', 'POST'])
def reservationsRoute():
    name = flask.request.headers.get('X-User-Name')

    if flask.request.method == 'GET':
        resp = flask.Response(arrToJson(get_user_reservations(name)))
        resp.headers['Content-Type'] = 'application/json'
        return resp

    elif flask.request.method == 'POST':
        reqData = flask.request.json
        # resReq = ReservationRequest(
        #     name, , reqData['startDate'], reqData['endDate'])

        start_date_s = reqData['startDate']
        end_date_s = reqData['endDate']

        # Get hotel
        hotel = requests.get(
            f'{services.RESERVATION_ADDR}/hotel?uid={urllib.parse.quote(reqData["hotelUid"])}'
        ).json()

        # Get discount
        try:
            discount = getLoyaltyDiscount(name)
        except:
            msg = {'message': 'Loyalty Service unavailable'}
            resp = flask.Response(json.dumps(
                msg, indent=None), status.HTTP_503_SERVICE_UNAVAILABLE)
            resp.headers['Content-Type'] = 'application/json'
            return resp

        # Calculate price
        startDate = datetime.datetime.fromisoformat(start_date_s)
        endDate = datetime.datetime.fromisoformat(end_date_s)
        nights = (endDate - startDate).days
        price = int((nights * hotel["price"]) * (1 - discount / 100))

        # Create payment record
        payment_uid = requests.get(
            f'{services.PAYMENT_ADDR}/create_payment?price={price}').text
        print('Payment UUID: ', payment_uid, file=sys.stderr)

        # Update loyalty status
        requests.get(
            f'{services.LOYALTY_ADDR}/update?username={urllib.parse.quote(name)}&delta=1')

        # Create reservation
        reserv_uuid = requests.get(
            f'{services.RESERVATION_ADDR}/create_reserv' +
            f'?username={urllib.parse.quote(name)}' +
            f'&payment={urllib.parse.quote(payment_uid)}' +
            f'&hotel={hotel["id"]}' +
            f"&start_date={reqData['startDate']}" +
            f"&end_date={reqData['endDate']}"
        ).text

        res = {
            "reservationUid": reserv_uuid,
            "hotelUid": hotel["hotelUid"],
            "startDate": start_date_s,
            "endDate": end_date_s,
            "discount": discount,
            "status": "PAID",
            "payment": {
                "status": "PAID",
                "price": price
            }
        }
        resp = flask.Response(json.dumps(res, separators=(',', ':')))
        resp.headers['Content-Type'] = 'application/json'
        return resp

    else:
        return flask.Response(
            ErrorResponse(msg='Smth went wrong: unexpected method').toJSON(),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.route('/api/v1/reservations/<uid>', methods=['GET', 'DELETE'])
def specReservationsRoute(uid):
    name = flask.request.headers.get('X-User-Name')

    if flask.request.method == 'GET':
        r1 = requests.get(
            f'{services.RESERVATION_ADDR}/get_reserv' +
            f'?name={urllib.parse.quote(name)}' +
            f'&uid={urllib.parse.quote(uid)}'
        ).json()
        r2 = requests.get(
            f'{services.PAYMENT_ADDR}/payment?uid={r1["payment_uid_"]}').json()
        r1.pop('payment_uid_', None)
        res = Reservation(payment=PaymentInfo(**r2), **r1)

        resp = flask.Response(res.toJSON())
        resp.headers['Content-Type'] = 'application/json'
        return resp

    elif flask.request.method == 'DELETE':
        payment_uuid = requests.get(
            f'{services.RESERVATION_ADDR}/get_reserv' +
            f'?name={urllib.parse.quote(name)}' +
            f'&uid={urllib.parse.quote(uid)}'
        ).json()["payment_uid_"]

        requests.get(
            f'{services.RESERVATION_ADDR}/cancel?uid={urllib.parse.quote(uid)}')
        requests.get(
            f'{services.PAYMENT_ADDR}/cancel?uid={urllib.parse.quote(payment_uuid)}')

        def loyalty_delayed_task(username):
            global delayed_tasks
            try:
                requests.get(
                    f'{services.LOYALTY_ADDR}/update?username={urllib.parse.quote(username)}&delta=-1')
            except:
                delayed_tasks.append((loyalty_delayed_task, (username,)))

        loyalty_delayed_task(name)

        resp = flask.Response('{}', status.HTTP_204_NO_CONTENT)
        resp.headers['Content-Type'] = 'application/json'
        return resp

    else:
        return flask.Response(
            ErrorResponse(msg='Smth went wrong: unexpected method').toJSON(),
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@app.route('/api/v1/loyalty', methods=['GET'])
def loyaltyRoute():
    name = flask.request.headers.get('X-User-Name')

    try:
        res = getLoyaltyStatus(name).text
    except:
        msg = {'message': 'Loyalty Service unavailable'}
        resp = flask.Response(json.dumps(msg, indent=None),
                              status.HTTP_503_SERVICE_UNAVAILABLE)
        resp.headers['Content-Type'] = 'application/json'
        return resp

    resp = flask.Response(res)
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/manage/health', methods=['GET'])
def gwHealthRoute():
    resp = flask.Response("")
    resp.headers['Content-Type'] = 'application/json'
    return resp


def delayed_tasks_executor():
    global delayed_tasks
    if len(delayed_tasks) != 0:
        tasks = delayed_tasks
        delayed_tasks = []
        for task in tasks:
            task[0](*task[1])
    sleep(10)


delayed_executor_thr = threading.Thread(target=delayed_tasks_executor)
delayed_executor_thr.start()

app.run(host="0.0.0.0", port=services.GATEWAY_PORT)
