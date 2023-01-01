import sys
import uuid
import flask
from flask_api import status
import psycopg2

from urllib.request import Request
from time import sleep, strftime

import common.services as services
from common.api_messages import *


app = flask.Flask(__name__)

while True:
    try:
        conn = psycopg2.connect(
            host="postgres",
            database="reservations",
            user="program",
            password="test")
        break
    except:
        print('Reconnecting to DB...')
        sleep(3)


def getHotelsPage(pageNum: int, pageSize: int) -> HotelsPage:
    lim = pageSize
    offs = pageSize * (pageNum - 1)
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT id, hotel_uid, name, country, city, address, stars, price ' +
            'FROM hotels LIMIT %s OFFSET %s',
            (lim, offs))
        hotels = [Hotel(*e) for e in cursor]
        hPage = HotelsPage(pageNum, pageSize, len(hotels), hotels)
        return hPage


def getHotel(uid: str) -> Hotel:
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT id, hotel_uid, name, country, city, address, stars, price ' +
            'FROM hotels WHERE hotel_uid = %s',
            (uid,))
        return Hotel(*cursor.fetchone())


def getUserReservations(name: str) -> list[Reservation]:
    with conn.cursor() as cursor:
        cursor.execute(
            'SELECT r.reservation_uid, r.start_date, r.end_date, r.status, r.payment_uid, ' +
            'h.hotel_uid, h.name, h.stars, h.country, h.city, h.address ' +
            'FROM reservation r INNER JOIN hotels h ON r.hotel_id = h.id ' +
            'WHERE username = %s',
            (name,)
        )
        res = []
        for raw in cursor:
            # res.append(*raw[:5], HotelInfo(*raw[5:]))
            res.append({
                "reservationUid": raw[0],
                "startDate": raw[1].strftime('%Y-%m-%d'),
                "endDate": raw[2].strftime('%Y-%m-%d'),
                "status": raw[3],
                "payment_uid_": raw[4],
                "hotel": {
                    "hotelUid": raw[5],
                    "name": raw[6],
                    "stars": raw[7],
                    "fullAddress": f'{raw[8]}, {raw[9]}, {raw[10]}',
                },
            })
    return res


def addReserv(user, payment, hotel_id, start_date, end_date) -> str:
    reserv_uuid = str(uuid.uuid4())
    with conn.cursor() as cursor:
        cursor.execute(
            'INSERT INTO reservation(reservation_uid, username, payment_uid, ' +
            "hotel_id, status, start_date, end_date) VALUES (%s, %s, %s, %s, 'PAID', %s, %s)",
            (reserv_uuid, user, payment, hotel_id, start_date, end_date))
    conn.commit()
    return reserv_uuid


def cancelReservation(uuid):
    with conn.cursor() as cursor:
        cursor.execute(
            "UPDATE reservation SET status = 'CANCELED' WHERE reservation_uid = %s",
            (uuid,)
        )
    conn.commit()


@app.route('/all_hotels', methods=['GET'])
def allHotelsRoute():
    pageNum = int(flask.request.args.get('page', '1'))
    pageSize = int(flask.request.args.get('size', '100'))
    hPage = getHotelsPage(pageNum, pageSize)
    resp = flask.Response(hPage.toJSON())
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/reservations', methods=['GET'])
def reservationsRoute():
    name = flask.request.args.get('name')
    reservations = getUserReservations(name)
    resp = flask.Response(json.dumps(reservations, separators=(',', ':')))
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/hotel', methods=['GET'])
def hotelRoute():
    uid = flask.request.args.get('uid')
    hotel = getHotel(uid)
    resp = flask.Response(hotel.toJSON())
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/create_reserv', methods=['GET'])
def create_reservRoute():
    user = flask.request.args.get('username')
    payment = flask.request.args.get('payment')
    hotel_id = int(flask.request.args.get('hotel'))
    start_date = flask.request.args.get('start_date')
    end_date = flask.request.args.get('end_date')

    res_uuid = addReserv(user, payment, hotel_id, start_date, end_date)

    resp = flask.Response(res_uuid)
    resp.headers['Content-Type'] = 'application/text'
    return resp


@app.route('/get_reserv', methods=['GET'])
def getReservRoute():
    user = flask.request.args.get('name')
    uid = flask.request.args.get('uid')

    res = None
    reservs = getUserReservations(user)
    for e in reservs:
        # print(e['reservationUid'], uid, file=sys.stderr)
        if e['reservationUid'] == uid:
            res = e
            break

    resp = flask.Response(json.dumps(res, separators=(',', ':')))
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/cancel', methods=['GET'])
def cancelRoute():
    # user = flasks.request.args.get('name')
    uid = flask.request.args.get('uid')
    cancelReservation(uid)
    resp = flask.Response('[]')
    resp.headers['Content-Type'] = 'application/json'
    return resp


app.run(host="0.0.0.0", port=services.RESERVATION_PORT)
