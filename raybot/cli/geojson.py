import json
import datetime
import asyncio
import sys
from raybot.model import db
from raybot.cli.reindex import reindex


async def do_import(data):
    def yesno_to_bool(v):
        if not v:
            return None
        return 1 if v[0] == 'y' else 0

    values = []
    refs = {}
    ids = set()
    row = 1
    for f in data['features']:
        if f['geometry']['type'] != 'Point':
            continue
        g = f['geometry']['coordinates']
        p = f['properties']
        if '$rowid' in p:
            row = p['$rowid']
        if 'id' in p:
            if p['id'] in ids:
                raise ValueError(f'Duplicate id: {p["id"]}')
            ids.add(p['id'])
            refs[p['id']] = row
        links = [l.strip().split() for l in p.get('links', '').split(';') if l.strip()]
        links = None if not links else json.dumps(links, ensure_ascii=False)
        now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        values.append([
            row,
            p.get('id'), p['name'], g[0], g[1], p.get('desc'),
            p.get('keywords'), p.get('photo'), p.get('inside'), p.get('tag'),
            p.get('hours'), links, yesno_to_bool(p.get('wifi')), yesno_to_bool(p.get('cards')),
            p.get('phones'), p.get('comment'), p.get('address'), 0 if p.get('index') == 'no' else 1,
            p.get('$created', now), p.get('$updated', now),
            1 if p.get('needs_check') == 'yes' else 0, p.get('house'),
            0 if p.get('active') == 'no' else 1
        ])
        row += 1

    # Validate house references
    for v in values:
        if v[-2] and v[-2] not in refs:
            raise IndexError(f'POI "{v[2]}" references missing key {v[-2]}.')

    # Upload to the database
    conn = await db.get_db()
    await conn.execute("delete from poi")
    await conn.execute("delete from poisearch")
    await conn.executemany("""insert into poi (
        rowid,
        str_id,   name,      lon, lat,    description,
        keywords, photo_out, photo_in,    tag,
        hours,    links,     has_wifi,    accepts_cards,
        phones,   comment,   address,     in_index,
        created,  updated,
        needs_check, house,
        active
    ) values (
        ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?,
        ?, ?,
        ?
    )""", values)
    await reindex(conn)
    await conn.commit()
    await conn.close()


async def do_export():
    def bool_to_yesno(b):
        if b is None:
            return None
        return 'yes' if b else 'no'

    conn = await db.get_db()
    features = []
    cursor = await conn.execute(
        "select p1.*, h.str_id as house_id from poi p1 left join poi h on p1.house = h.rowid")
    async for row in cursor:
        props = {
            '$rowid': row['id'],
            'id': row['str_id'],
            'name': row['name'],
            'desc': row['description'],
            'keywords': row['keywords'],
            'photo': row['photo_out'],
            'inside': row['photo_in'],
            'tag': row['tag'],
            'hours': row['hours'],
            'wifi': bool_to_yesno(row['has_wifi']),
            'cards': bool_to_yesno(row['accepts_cards']),
            'phones': row['phones'],
            'comment': row['comment'],
            'address': row['address'],
            'index': 'no' if not row['in_index'] else None,
            '$created': row['created'],
            '$updated': row['updated'],
            'needs_check': 'yes' if row['needs_check'] else None,
            'house': row['house'],
            'active': 'no' if 'active' in row.keys() and not row['active'] else None,
        }
        if row['links']:
            props['links'] = '; '.join([' '.join(l) for l in json.loads(row['links'])])
        for k in list(props.keys()):
            if props[k] is None:
                del props[k]
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [row['lon'], row['lat']]
            },
            'properties': props
        })
    await conn.close()
    return {'type': 'FeatureCollection', 'features': features}


def run_import():
    if len(sys.argv) < 3:
        print('Usage: {} import <file.geojson>'.format(sys.argv[0]))
        sys.exit(1)
    with open(sys.argv[2], 'r') as f:
        data = json.load(f)
    asyncio.run(do_import(data))


def run_export():
    if len(sys.argv) < 3:
        print('Usage: {} export <file.geojson>'.format(sys.argv[0]))
        sys.exit(1)
    data = asyncio.run(do_export())
    with open(sys.argv[2], 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
