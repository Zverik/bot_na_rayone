import aiosqlite
import logging
import os
import json
from raybot import config
from .entities import POI, UserInfo, QueueMessage
from typing import List, Dict


_db = None


async def get_db():
    global _db
    if _db is not None and _db._running:
        return _db
    _db = await aiosqlite.connect(config.DATABASE)
    _db.row_factory = aiosqlite.Row
    exists_query = ("select count(*) from sqlite_master where type = 'table' "
                    "and name in ('poi', 'poisearch', 'roles')")
    async with _db.execute(exists_query) as cursor:
        has_tables = (await cursor.fetchone())[0] == 3
    if not has_tables:
        logging.info('Creating tables')
        with open(os.path.join(os.path.dirname(__file__), 'create_tables.sql'), 'r') as f:
            queries = [q.strip() for q in f.read().split(';')]
        for q in queries:
            if q:
                await _db.execute(q)
    return _db


async def close():
    if _db is not None and _db._running:
        await _db.close()


async def get_poi_by_id(poi_id: int) -> POI:
    query = ("select poi.*, h.name as h_address from poi "
             "left join poi h on h.str_id = poi.house where poi.id = ?")
    db = await get_db()
    cursor = await db.execute(query, (poi_id,))
    row = await cursor.fetchone()
    return None if not row else POI(row)


async def get_poi_by_ids(poi_ids: List[int]) -> POI:
    query = "select * from poi where id in ({})".format(','.join('?' * len(poi_ids)))
    db = await get_db()
    cursor = await db.execute(query, tuple(poi_ids))
    return [POI(r) async for r in cursor]


async def get_poi_by_house(house: str) -> POI:
    query = ("select * from poi where house = ? and in_index and delete_reason is null and "
             "(tag is null or tag not in ('entrance', 'building'))")
    db = await get_db()
    cursor = await db.execute(query, (house,))
    return [POI(r) async for r in cursor]


async def get_poi_by_key(str_id: str) -> POI:
    query = "select * from poi where str_id = ?"
    db = await get_db()
    cursor = await db.execute(query, (str_id,))
    row = await cursor.fetchone()
    return None if not row else POI(row)


async def find_poi(keywords: str) -> List[POI]:
    query = ("select poi.*, h.name as h_address from poi "
             "left join poi h on h.str_id = poi.house "
             "where poi.in_index and poi.delete_reason is null and "
             "poi.rowid in (select docid from poisearch where poisearch match ?)")
    db = await get_db()
    cursor = await db.execute(query, (keywords,))
    return [POI(r) async for r in cursor]


async def get_roles(user_id: int) -> List[str]:
    query = "select role from roles where user_id = ?"
    db = await get_db()
    cursor = await db.execute(query, (user_id,))
    return [r[0] async for r in cursor]


async def get_role_users(role: str) -> List[UserInfo]:
    query = "select user_id, name from roles where role = ?"
    db = await get_db()
    cursor = await db.execute(query, (role,))
    return [UserInfo(user_id=r[0], user_name=r[1]) async for r in cursor]


async def add_user_to_role(user: UserInfo, role: str, added_by: UserInfo):
    query = "insert into roles (user_id, name, role, added_by) values (?, ?, ?, ?)"
    db = await get_db()
    await db.execute(query, (user.id, user.name, role, added_by.name))
    await db.commit()


async def remove_user_from_role(user_id: int, role: str):
    query = "delete from roles where user_id = ? and role = ?"
    db = await get_db()
    await db.execute(query, (user_id, role))
    await db.commit()


async def get_entrances(building: str) -> List[str]:
    query = "select str_id from poi where house = ? and tag = 'entrance'"
    db = await get_db()
    cursor = await db.execute(query, (building,))
    return [r[0] async for r in cursor]


async def store_file_id(path: str, size: int, file_id: str) -> None:
    query = "insert or ignore into file_ids (path, size, file_id) values (?, ?, ?)"
    db = await get_db()
    await db.execute(query, (path, size, file_id))
    await db.commit()


async def find_file_ids(paths: Dict[str, int]) -> Dict[str, str]:
    """Parameter 1: dict of "file path" -> file size."""
    fpaths = [p for p in paths.keys() if p]
    if not fpaths:
        return {}
    query = "select path, size, file_id from file_ids where path in ({})".format(
        ','.join('?' * len(fpaths)))
    db = await get_db()
    cursor = await db.execute(query, tuple(fpaths))
    return {r['path']: r['file_id'] async for r in cursor
            if r['size'] == paths[r['path']]}


async def find_path_for_file_id(file_id: str) -> str:
    db = await get_db()
    query = "select path from file_ids where file_id = ? limit 1"
    cursor = await db.execute(query, (file_id,))
    row = await cursor.fetchone()
    return None if not row else row[0]


async def get_houses() -> List[POI]:
    query = "select * from poi where str_id is not null and tag = 'building'"
    db = await get_db()
    cursor = await db.execute(query)
    return [POI(r) async for r in cursor]


async def insert_poi(user_id: int, poi: POI):
    if poi.id is not None:
        return await update_poi(user_id, poi)

    # Insert the row
    fields = poi.get_db_fields()
    query = "insert into poi ({}) values ({})".format(
        ','.join(fields.keys()),
        ','.join('?' * len(fields))
    )
    db = await get_db()
    await db.execute(query, tuple(fields.values()))

    # Update audit
    cursor = await db.execute("select last_insert_rowid()")
    rowid = (await cursor.fetchone())[0]
    poi.id = rowid
    await save_audit(user_id, user_id, None, poi)

    # Now update the search index
    tagkw = ' '.join(config.TAGS['tags'].get(poi.tag, [])) or None
    query2 = ("insert into poisearch (docid, name, keywords, tag) "
              "select rowid, replace(name, 'ё', 'е') as name, keywords, ? "
              "from poi where id = ?")
    await db.execute(query2, (tagkw, rowid))
    await db.commit()
    return poi.id


async def update_poi(user_id: int, poi: POI):
    orig = await get_poi_by_id(poi.id)
    fields = poi.get_db_fields(orig)
    if not fields:
        return poi.id

    query = "update poi set {}, updated = current_timestamp where id = ?".format(
        ','.join([f'{k} = ?' for k in fields.keys()]))
    db = await get_db()
    await db.execute(query, (*fields.values(), poi.id))
    await save_audit(user_id, user_id, orig, poi)
    if 'keywords' in fields or 'tag' in fields or 'name' in fields:
        tagkw = ' '.join(config.TAGS['tags'].get(poi.tag, [])) or None
        query2 = ("update poisearch set keywords = ?, name = ?, "
                  "tag = ? where docid = ?")
        await db.execute(query2, (poi.keywords, poi.name, tagkw, poi.id))
    await db.commit()
    return poi.id


async def delete_poi(user_id: int, poi: POI, reason: str):
    db = await get_db()
    query = ("insert into poi_audit (user_id, approved_by, poi_id, field, "
             "old_value, new_value) values (?, ?, ?, 'delete_reason', ?, ?)")
    await db.execute(query, (user_id, user_id, poi.id, None, reason))
    await db.execute("delete from poisearch where docid = ?", (poi.id,))
    await db.execute("update poi set delete_reason = ?, updated = current_timestamp "
                     "where id = ?", (reason, poi.id))
    await db.commit()


async def restore_poi(user_id: int, poi: POI):
    db = await get_db()
    query = ("insert into poi_audit (user_id, approved_by, poi_id, field, "
             "old_value, new_value) values (?, ?, ?, 'delete_reason', ?, ?)")
    await db.execute(query, (user_id, user_id, poi.id, poi.delete_reason, None))
    await db.execute("update poi set delete_reason = null, updated = current_timestamp "
                     "where id = ?", (poi.id, ))
    tagkw = ' '.join(config.TAGS['tags'].get(poi.tag, [])) or None
    query2 = "insert into poisearch (keywords, name, tag, docid) values (?, ?, ?, ?)"
    await db.execute(query2, (poi.keywords, poi.name, tagkw, poi.id))
    await db.commit()


async def save_audit(user_id: int, approved_by: int, oldpoi: POI, poi: POI):
    """Warning: does not do db.commit()."""
    db = await get_db()
    if oldpoi is None:
        query = ("insert into poi_audit (user_id, approved_by, poi_id, field, new_value) "
                 "values (?, ?, ?, 'poi', ?)")
        data = json.dumps(poi.get_db_fields())
        await db.execute(query, (user_id, approved_by, poi.id, data))
    elif poi is None:
        query = ("insert into poi_audit (user_id, approved_by, poi_id, field, old_value) "
                 "values (?, ?, ?, 'poi', ?)")
        data = json.dumps(oldpoi.get_db_fields())
        await db.execute(query, (user_id, approved_by, oldpoi.id, data))
    else:
        query = ("insert into poi_audit (user_id, approved_by, poi_id, field, "
                 "old_value, new_value) values (?, ?, ?, ?, ?, ?)")
        old_fields = oldpoi.get_db_fields()
        fields = poi.get_db_fields(oldpoi)
        for field in fields:
            await db.execute(query, (user_id, approved_by, poi.id, field,
                                     old_fields[field], fields[field]))


async def add_to_queue(user: UserInfo, poi: POI, message: str = None):
    if poi.id is None:
        raise ValueError(f'POI id should not be None. Msg = "{message}"')
    db = await get_db()
    if message:
        query = ("insert into queue (user_id, user_name, poi_id, field, new_value) "
                 "values (?, ?, ?, 'message', ?)")
        await db.execute(query, (user.id, user.name, poi.id, message))
    else:
        query = ("insert into queue (user_id, user_name, poi_id, field, old_value, new_value) "
                 "values (?, ?, ?, ?, ?, ?)")
        orig = await get_poi_by_id(poi.id)
        old_fields = orig.get_db_fields()
        fields = poi.get_db_fields(orig)
        for field in fields:
            await db.execute(query, (user.id, user.name, poi.id, field,
                                     old_fields[field], fields[field]))
    await db.commit()


async def get_queue(count: int = 1):
    query = f"select * from queue order by ts desc limit {count}"
    db = await get_db()
    cursor = await db.execute(query)
    return [QueueMessage(r) async for r in cursor]


async def get_queue_msg(qid: int):
    query = f"select * from queue where id = ?"
    db = await get_db()
    cursor = await db.execute(query, (qid,))
    row = await cursor.fetchone()
    return None if not row else QueueMessage(row)


async def delete_queue(q: QueueMessage):
    db = await get_db()
    await db.execute("delete from queue where id = ?", (q.id,))
    await db.commit()


async def apply_queue(user_id: int, q: QueueMessage):
    db = await get_db()
    query = "update poi set {} = ?, updated = current_timestamp where id = ?".format(q.field)
    await db.execute(query, (q.new_value, q.poi_id))
    query = ("insert into poi_audit (user_id, approved_by, poi_id, field, "
             "old_value, new_value) values (?, ?, ?, ?, ?, ?)")
    if q.field == 'keywords':
        query2 = ("update poisearch set keywords = (select keywords from poi where id = ?) "
                  "where docid = ?")
        await db.execute(query2, (q.poi_id, q.poi_id))
    elif q.field == 'tag':
        tagkw = ' '.join(config.TAGS['tags'].get(q.new_value, [])) or None
        query2 = "update poisearch set tag = ? where docid = ?"
        await db.execute(query2, (tagkw, q.poi_id))
    await db.execute(query, (q.user_id, user_id, q.poi_id, q.field, q.old_value, q.new_value))
    await db.execute("delete from queue where id = ?", (q.id,))
    await db.commit()


async def get_next_unchecked():
    query = "select * from poi where needs_check order by created limit 1"
    db = await get_db()
    cursor = await db.execute(query)
    row = await cursor.fetchone()
    return None if not row else POI(row)


async def validate_poi(poi_id: int):
    query = "update poi set needs_check = 0 where id = ?"
    db = await get_db()
    await db.execute(query, (poi_id,))
    await db.commit()


async def get_last_poi(count: int = 1):
    db = await get_db()
    query = ("select * from poi where delete_reason is null "
             f"order by created desc limit {count}")
    db = await get_db()
    cursor = await db.execute(query)
    return [POI(r) async for r in cursor]


async def get_last_deleted(count: int = 1):
    db = await get_db()
    query = ("select * from poi where delete_reason is not null "
             f"order by updated desc limit {count}")
    db = await get_db()
    cursor = await db.execute(query)
    return [POI(r) async for r in cursor]


async def get_random_poi(count: int = 10):
    db = await get_db()
    query = ("select * from poi where id in (select id from poi "
             "where (tag is null or tag not in ('building', 'entrance')) "
             f"and delete_reason is null order by random() limit {count})")
    db = await get_db()
    cursor = await db.execute(query)
    return [POI(r) async for r in cursor]


async def get_stats():
    db = await get_db()
    query = """\
        select count(*) filter (where tag = 'building') as cnt_house,
            count(*) filter (where tag = 'entrance') as cnt_entrance,
            count(*) filter (where delete_reason is null and (tag is null or
                tag not in ('building', 'entrance'))) as cnt_poi
        from poi
    """
    cursor = await db.execute(query)
    row = await cursor.fetchone()
    stats = {
        'buildings': row['cnt_house'],
        'entrances': row['cnt_entrance'],
        'pois': row['cnt_poi'],
    }
    return stats