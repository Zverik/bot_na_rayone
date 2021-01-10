import asyncio
from raybot.model import db


async def aiorun():
    conn = await db.get_db()
    cursor = await conn.execute(
        "select poi.name as name, h.name as house_name, "
        "poi.house, poi.tag, poi.hours, poi.keywords, poi.links "
        "from poi left join poi h on h.str_id = poi.house "
        "where poi.tag is null or poi.tag not in ('building', 'entrance')")
    keys = ['house', 'keywords', 'links', 'tag', 'hours']
    missing = {k: [] for k in keys}
    async for row in cursor:
        v = row['name'] if not row['house_name'] else f"{row['name']} ({row['house_name']})"
        for k in keys:
            if not row[k]:
                missing[k].append(v)
    await db.close()
    for k in keys:
        print(f'Value for {k} is missing in {len(missing[k])} places.')
        if len(missing[k]) <= 30:
            for name in missing[k]:
                print(f'- {name}')


def run():
    asyncio.run(aiorun())
