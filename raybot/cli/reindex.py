import asyncio
from raybot.model import db
from raybot import config


async def reindex(conn):
    await conn.execute("delete from poisearch")
    # Create temporary tag table
    await conn.execute("create table tag_keywords (tag text not null, tagkw text not null)")
    await conn.executemany("insert into tag_keywords (tag, tagkw) values (?, ?)",
                           [(k, ' '.join(v)) for k, v in config.TAGS['tags'].items()])
    await conn.execute(
        "insert into poisearch (docid, name, keywords, tag) "
        "select poi.rowid, replace(name, 'ё', 'е') as name, keywords, tagkw as tag from poi "
        "left join tag_keywords on poi.tag = tag_keywords.tag "
        "where in_index and delete_reason is null"
    )
    await conn.execute("drop table tag_keywords")


async def aiorun():
    conn = await db.get_db()
    await reindex(conn)
    await conn.commit()
    await conn.close()


def run():
    asyncio.run(aiorun())
