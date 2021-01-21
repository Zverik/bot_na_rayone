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

    # Special processing for missing floors.
    missing['floor'] = []
    cursor = await conn.execute(
        "select poi.name as name, h.name as house_name "
        "from poi left join poi h on h.str_id = poi.house "
        "where poi.house is not null and poi.flor is null "
        "and (poi.tag is null or poi.tag not in ('building', 'entrance')) "
        "and poi.house in (select distinct house from poi "
        "where house is not null and flor is not null)")
    async for row in cursor:
        v = f"{row['name']} ({row['house_name']})"
        missing['floor'].append(v)

    # Close the connection and print the results.
    await db.close()
    for k in missing:
        print(f'Value for {k} is missing in {len(missing[k])} places.')
        if len(missing[k]) <= 30:
            for name in missing[k]:
                print(f'- {name}')


def run():
    asyncio.run(aiorun())
