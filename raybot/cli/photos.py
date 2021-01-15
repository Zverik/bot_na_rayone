import asyncio
import os
from raybot import config
from raybot.model import db


async def aiorun():
    photos = set()
    for name in os.listdir(config.PHOTOS):
        if name.endswith('.jpg'):
            photos.add(name.rsplit('.', 1)[0])
    for predef in config.RESP['responses']:
        if 'photo' in predef:
            if not os.path.exists(os.path.join(config.PHOTOS, predef['photo'])):
                print(f'Missing photo for predef resp "{predef["name"]}": {predef["photo"]}')
            photos.discard(predef['photo'].rsplit('.', 1)[0])

    conn = await db.get_db()
    cursor = await conn.execute(
        "select name, photo_out, photo_in from poi where photo_out is not null "
        "or photo_in is not null")
    async for row in cursor:
        for c in (1, 2):
            if row[c]:
                if not os.path.exists(os.path.join(config.PHOTOS, row[c] + '.jpg')):
                    print(f'Missing photo for "{row[0]}": {row[c]}.jpg')
                photos.discard(row[c])
    for name in sorted(photos):
        print(f'Photo not used: {name}')

    cursor = await conn.execute(
        "select poi.name, h.name from poi left join poi h on h.str_id = poi.house "
        "where poi.photo_out is null")
    async for row in cursor:
        print(f'Outside photo is missing: {row[0]} ({row[1]})')
    await db.close()


def run():
    asyncio.run(aiorun())
