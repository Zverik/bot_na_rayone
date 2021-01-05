import asyncio
import os
from raybot import config
from raybot.model import db


def validate_apartments():
    for k, v in config.ADDR['apartments'].items():
        if isinstance(v, list):
            for i in range(len(v) - 1):
                if i > 0 and not (2 <= v[i + 1] - v[i] + 1 <= 10):
                    print(f'Weird apmt sequence in {k}: {v[i]}, {v[i+1]}.')
            print(f'Entrance {k}: last floor {len(v)} apmt {v[-1]}')


async def aiorun():
    ids = set(config.ADDR['apartments'].keys())
    for street in config.ADDR['streets']:
        ids.update(street['buildings'].values())

    conn = await db.get_db()
    cursor = await conn.execute(
        "select str_id, photo_out from poi where str_id is not null and photo_out is not null")
    async for row in cursor:
        if not os.path.exists(os.path.join(config.PHOTOS, row[1] + '.jpg')):
            print(f'Missing photo: {row[1]}.jpg')
        ids.discard(row[0])
    await db.close()
    for str_id in sorted(ids):
        print(f'No photo listed: {str_id}')


def run():
    validate_apartments()
    asyncio.run(aiorun())
