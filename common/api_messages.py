from dataclasses import dataclass
import json
from typing import Dict, List, Union

from json import JSONEncoder
class MyEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


def cleanNones(o):
    return {k: v for k,
            v in o.__dict__.items() if v is not None}


class ApiMessage:
    def toJSON(self):
        return json.dumps(self, separators=(',', ':'), default=cleanNones)


def arrToJson(arr: List[ApiMessage]):
    return json.dumps([cleanNones(e) for e in arr], separators=(',', ':'), cls=MyEncoder)


@dataclass
class ErrorResponse(ApiMessage):
    msg: str


@dataclass
class Hotel(ApiMessage):
    id: int
    hotelUid: str
    name: str
    country: str
    city: str
    address: str
    stars: int
    price: int


@dataclass
class PaymentInfo(ApiMessage):
    status: str
    price: int


@dataclass
class HotelsPage(ApiMessage):
    page: int
    pageSize: int
    totalElements: int
    items: List[Hotel]


@dataclass
class HotelInfo(ApiMessage):
    hotelUid: str
    name: str
    fullAddress: str
    stars: int


@dataclass
class Reservation(ApiMessage):
    reservationUid: str
    startDate: str
    endDate: str
    status: str
    payment: PaymentInfo
    hotel: HotelInfo


@dataclass
class INT_Reservation(ApiMessage):
    reservationUid: str
    startDate: str
    endDate: str
    status: str
    hotel: HotelInfo
    payment_uid: str  # JOIN


@dataclass
class ReservationRequest(ApiMessage):
    username: str
    hotelUid: str
    startDate: str
    endDate: str
