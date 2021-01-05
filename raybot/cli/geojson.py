import json
import datetime
import asyncio
import sys
from raybot.model import db
from raybot import config


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
        if 'id' in p:
            if p['id'] in ids:
                raise ValueError(f'Duplicate id: {p["id"]}')
            ids.add(p['id'])
        links = [l.strip().split() for l in p.get('links', '').split(';') if l.strip()]
        links = None if not links else json.dumps(links)
        if 'id' in p:
            refs[p['id']] = row
        now = datetime.datetime.now()
        values.append([
            row,
            p.get('id'), p['name'], g[0], g[1], p.get('desc'),
            p.get('keywords'), p.get('photo'), p.get('inside'), p.get('tag'),
            p.get('hours'), links, yesno_to_bool(p.get('wifi')), yesno_to_bool(p.get('cards')),
            p.get('phone'), p.get('comment'), p.get('address'), 0 if p.get('index') == 'no' else 1,
            p.get('created_at', now), p.get('updated_at', now),
            1 if p.get('needs_check') == 'yes' else 0,
            p.get('house')
        ])
        row += 1

    # Fix house references
    for v in values:
        if v[-1]:
            if v[-1] not in refs:
                raise IndexError(f'POI "{v[2]}" references missing key {v[-1]}.')
            # keeping house as string
            # v[-1] = refs[v[-1]]

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
        created,  updated,   needs_check, house
    ) values (
        ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?
    )""", values)
    # Create temporary tag table
    await conn.execute("create table tag_keywords (tag text not null, tagkw text not null)")
    await conn.executemany("insert into tag_keywords (tag, tagkw) values (?, ?)",
                           [(k, ' '.join(v)) for k, v in config.MSG['tags'].items()])
    await conn.execute(
        "insert into poisearch (docid, name, keywords, tag) "
        "select poi.rowid, replace(name, 'ё', 'е') as name, keywords, tagkw as tag from poi "
        "left join tag_keywords on poi.tag = tag_keywords.tag where in_index"
    )
    await conn.execute("drop table tag_keywords")
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
            'index': 'no' if row['in_index'] is False else None,
            '$created_at': row['created'],
            '$updated_at': row['updated'],
            'needs_check': 'yes' if row['needs_check'] else None,
            'house': row['house_id'],
            'active': 'no' if row['active'] == 0 else None,
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
