import os
import asyncio
import hashlib
from collections import defaultdict
from PIL import Image
from raybot.model import db
from raybot.config import PHOTOS


def hashall(photos):
    result = defaultdict(list)
    for photo in photos:
        path = os.path.join(PHOTOS, photo + '.jpg')
        image = Image.open(path)
        h = hashlib.md5()
        h.update(image.tobytes())
        result[h.digest()].append(photo)
    return result


async def aiorun():
    conn = await db.get_db()
    cursor = await conn.execute("select id, photo_out, photo_in from poi order by id")
    photos = set()
    refs = {}
    async for row in cursor:
        for i in ('photo_out', 'photo_in'):
            if row[i]:
                photos.add(row[i])
                refs[(row[i], i)] = row['id']

    # Find sizes
    sizes = defaultdict(list)
    for photo in photos:
        path = os.path.join(PHOTOS, photo + '.jpg')
        if os.path.exists(path):
            sizes[os.path.getsize(path)].append(photo)

    # Remove duplicates
    removed = 0
    hashes = hashall(sum(sizes.values(), []))
    for s, ph in hashes.items():
        if len(ph) > 1:
            for k in ('photo_out', 'photo_in'):
                ids = [refs[p, k] for p in ph[1:] if (p, k) in refs]
                await conn.execute("update poi set {} = ? where id in ({})".format(
                    k, ','.join('?' * len(ids))), (ph[0], *ids))
            for photo in ph[1:]:
                path = os.path.join(PHOTOS, photo + '.jpg')
                os.remove(path)
                removed += 1
    await conn.commit()
    await conn.close()
    print(f'Deleted {removed} duplicate photos.')


def run():
    asyncio.run(aiorun())
