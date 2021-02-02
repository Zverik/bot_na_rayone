import json
import csv
import datetime
from raybot import config
from raybot.model import db
from io import StringIO


async def import_geojson(f):
    def yesno_to_bool(v):
        if not v:
            return None
        return 1 if v[0] == 'y' else 0

    values = []
    refs = {}
    ids = set()
    row = 1
    data = json.load(f)
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
            p.get('$created', now), p.get('$updated', now), p.get('floor'),
            1 if p.get('needs_check') == 'yes' else 0, p.get('house'), p.get('reason')
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
        created,  updated,   flor,
        needs_check, house, delete_reason
    ) values (
        ?,
        ?, ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?, ?,
        ?, ?, ?,
        ?, ?, ?
    )""", values)
    await conn.commit()
    await db.reindex()


async def export_geojson(f):
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
            'floor': row['flor'],
            'reason': row['delete_reason'],
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
    data = {'type': 'FeatureCollection', 'features': features}
    json.dump(data, f, indent=1, ensure_ascii=False)


async def export_tags(f):
    conn = await db.get_db()
    cur = await conn.execute(
        "select id, name, tag, '', description, comment, address "
        "from poi where tag is null or tag not in ('building', 'entrance')")
    w = csv.writer(f)
    w.writerow('id name tag type description comment address'.split())
    async for row in cur:
        row = list(row)
        row[3] = config.TAGS['tags'].get(row[2], [''])[0]
        w.writerow(row)


async def import_tags(f):
    """Returns a StrinIO file with YAML contents for new tags."""
    conn = await db.get_db()
    cur = await conn.execute("select id, tag from poi")
    poi_tags = {row[0]: row[1] async for row in cur}
    new_tags = {}
    for row in csv.DictReader(f):
        if not row['id'].isdecimal():
            continue
        poi_id = int(row['id'])
        tag = row['tag'].strip()
        if not tag:
            continue
        if poi_id not in poi_tags:
            continue
        if tag != poi_tags[poi_id]:
            await conn.execute("update poi set tag = ? where id = ?", (tag, poi_id))
        if tag not in config.TAGS['tags']:
            if tag not in new_tags or not new_tags[tag]:
                new_tags[tag] = row['type'].strip()
    await conn.commit()

    if not new_tags:
        return None

    outfile = StringIO()
    print('tags:', file=outfile)
    for k, v in new_tags.items():
        print(f'  {k}: [{v}]', file=outfile)
    outfile.seek(0)
    return outfile


def get_file_type(filename):
    with open(filename, 'r') as f:
        start = f.read(200)
    if not start:
        return 'empty'
    if start[0] == '{':
        return 'geojson'
    if start.replace(' ', '').startswith('id,name'):
        return 'tags'
    return 'unknown'
