from dataclasses import dataclass, field
from typing import List, Tuple
from raybot import config
import humanized_opening_hours as hoh
import json
from time import time
from datetime import datetime
from math import radians, cos, sqrt


@dataclass
class Location:
    lon: float
    lat: float

    def distance(self, other) -> float:
        """Not exact!"""
        f1 = radians(self.lat)
        f2 = radians(other.lat)
        l1 = radians(self.lon)
        l2 = radians(other.lon)
        x = (l2 - l1) * cos((f1 + f2) / 2)
        y = f2 - f1
        return sqrt(x * x + y * y) * 6371e3


@dataclass
class POI:
    id: int
    name: str
    location: Location
    keywords: str
    key: str = None
    hours: hoh.OHParser = None
    hours_src: str = None
    photo_out: str = None
    photo_in: str = None
    links: List[Tuple[str, str]] = field(default_factory=list)
    description: str = None
    comment: str = None
    address_part: str = None
    has_wifi: bool = None
    accepts_cards: bool = None
    needs_check: bool = None
    phones: List[str] = field(default_factory=list)
    house: str = None
    house_name: str = None
    tag: str = None

    def __init__(self, row=None, name=None, location=None, keywords=None):
        if row:
            self.id = row['id']
            self.name = row['name']
            self.key = row['str_id']
            self.hours_src = row['hours']
            self.hours = hoh.OHParser(row['hours']) if row['hours'] else None
            self.links = json.loads(row['links'] or '[]')
            self.photo_out = row['photo_out']
            self.photo_in = row['photo_in']
            self.location = Location(lon=row['lon'], lat=row['lat'])
            self.description = row['description']
            self.comment = row['comment']
            self.house = row['house']
            self.house_name = row['h_address'] if 'h_address' in row.keys() else None
            self.address_part = row['address']
            self.keywords = row['keywords']
            if not row['phones']:
                self.phones = []
            else:
                self.phones = [p.strip() for p in row['phones'].split(';')]
            self.has_wifi = None if row['has_wifi'] is None else row['has_wifi'] == 1
            self.accepts_cards = None if row['accepts_cards'] is None else row['accepts_cards'] == 1
            self.tag = row['tag']
            self.needs_check = row['needs_check'] == 1
        else:
            self.id = None
            self.name = name
            self.location = location
            self.keywords = keywords
            self.phones = []
            self.links = []

    @property
    def address(self):
        return ', '.join([s for s in (self.house_name, self.address_part) if s])

    def get_db_fields(self, orig=None) -> dict:
        def bool_to_int(v):
            if v is None:
                return None
            return 1 if v else 0

        fields = {
            'name': self.name,
            'lon': self.location.lon,
            'lat': self.location.lat,
            'description': self.description,
            'keywords': self.keywords,
            'photo_out': self.photo_out,
            'photo_in': self.photo_in,
            'tag': self.tag,
            'hours': self.hours_src,
            'links': None if not self.links else json.dumps(self.links, ensure_ascii=False),
            'has_wifi': bool_to_int(self.has_wifi),
            'accepts_cards': bool_to_int(self.accepts_cards),
            'phones': '; '.join(self.phones) or None,
            'comment': self.comment,
            'address': self.address_part,
            'house': self.house,
            'needs_check': 1 if self.needs_check else 0,
        }
        if orig:
            orig_fields = orig.get_db_fields()
            for k in list(fields.keys()):
                if fields[k] == orig_fields[k]:
                    del fields[k]
        return fields


@dataclass(eq=False)
class UserInfo:
    id: int
    name: str
    _location: Location = None  # user's location
    location_time: int = 0  # To forget location after 5 minutes
    last_access: int = 0  # Last access time
    roles: List[str] = field(default_factory=list)

    def __init__(self, user=None, user_id=None, user_name=None):
        if user:
            self.id = user.id
            self.name = ' '.join(s for s in [user.first_name, user.last_name] if s)
        elif user_id:
            self.id = user_id
            self.name = user_name
        else:
            raise ValueError('Either a user or an id and name are required.')
        self.roles = []
        self.last_access = time()

    @property
    def location(self) -> Location:
        if time() - self.location_time > 60 * 5:
            self._location = None
        return self._location

    @location.setter
    def location(self, location: Location) -> None:
        self._location = location
        self.location_time = time()

    def is_moderator(self) -> bool:
        return self.id == config.ADMIN or 'moderator' in self.roles


@dataclass
class QueueMessage:
    id: int
    user_id: int
    user_name: str
    ts: datetime
    poi_id: int
    field: str
    old_value: str
    new_value: str

    def __init__(self, row):
        self.id = row['id']
        self.user_id = row['user_id']
        self.user_name = row['user_name']
        self.ts = row['ts']
        self.poi_id = row['poi_id']
        self.field = row['field']
        self.old_value = row['old_value']
        self.new_value = row['new_value']
