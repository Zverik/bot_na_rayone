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
        lat1 = radians(self.lat)
        lat2 = radians(other.lat)
        lon1 = radians(self.lon)
        lon2 = radians(other.lon)
        x = (lon2 - lon1) * cos((lat1 + lat2) / 2)
        y = lat2 - lat1
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
    delete_reason: str = None

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
            self.delete_reason = row['delete_reason']
        else:
            self.id = None
            self.name = name
            self.location = location
            self.keywords = keywords
            self.phones = []
            self.links = []

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
    approved_by: int
    user_name: str
    ts: datetime
    poi_id: int
    poi_name: str
    field: str
    old_value: str
    new_value: str

    def __init__(self, row):
        self.id = row['id']
        self.user_id = row['user_id']
        self.approved_by = row['approved_by'] if 'approved_by' in row.keys() else None
        self.user_name = row['user_name'] if 'user_name' in row.keys() else None
        if not row['ts'] or isinstance(row['ts'], datetime):
            self.ts = row['ts']
        else:
            try:
                self.ts = datetime.strptime(row['ts'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Setting it to string, since we have no choice
                self.ts = row['ts']
        self.poi_id = row['poi_id']
        self.poi_name = row['poi_name'] if 'poi_name' in row.keys() else None
        self.field = row['field']
        self.old_value = row['old_value']
        self.new_value = row['new_value']
