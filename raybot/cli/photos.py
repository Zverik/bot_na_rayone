import asyncio
import os
from raybot import config
from raybot.model import db


async def aiorun():
    photos = set()
    for name in os.listdir(config.PHOTOS):
        if name.endswith('.jpg'):
            photos.add(name.rsplit('.', 1)[0])

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
    await db.close()
    for name in sorted(photos):
        print(f'Photo not used: {name}')


def run():
    asyncio.run(aiorun())
