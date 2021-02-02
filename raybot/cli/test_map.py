from raybot.util import get_map
from raybot.model import Location
from raybot import config
import sys
import sqlite3
import logging


def run():
    if len(sys.argv) < 3:
        print('Usage: {} test_map <str_id1,strid2,...> [<map.jpg>]'.format(sys.argv[0]))
        sys.exit(1)

    locations = []
    with sqlite3.connect(config.DATABASE) as conn:
        for str_id in sys.argv[2].split(','):
            cursor = conn.execute("select lon, lat from poi where str_id = ?", (str_id,))
            row = cursor.fetchone()
            if not row:
                print(f'Cannot find {str_id} in the database.')
                sys.exit(2)
            locations.append(Location(lon=row[0], lat=row[1]))

    logging.basicConfig(level=logging.INFO)
    fp = get_map(locations)
    filename = 'test_map.jpg' if len(sys.argv) < 4 else sys.argv[3]
    with open(filename, 'wb') as f:
        data = fp.read()
        f.write(data)
    fp.close()
