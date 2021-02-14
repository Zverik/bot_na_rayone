import os
import hashlib
from collections import defaultdict
from io import StringIO
from datetime import datetime
from tempfile import TemporaryDirectory
from PIL import Image
from raybot import config
from raybot.model import db
from raybot.bot import bot, dp
from raybot.util import h, HTML, get_user, forget_user, tr
from raybot.actions import transfer
from raybot.actions.poi import print_poi, POI_EDIT_CB, print_poi_list, PoiState
from typing import Dict
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.exceptions import TelegramAPIError
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import SkipHandler
from aiogram.dispatcher.filters.state import State, StatesGroup


MSG_CB = CallbackData('qmsg', 'action', 'id')
POI_VALIDATE_CB = CallbackData('qpoi', 'id')
MOD_REMOVE_CB = CallbackData('modrm', 'id')
ADMIN_CB = CallbackData('admin', 'action')


class ModState(StatesGroup):
    mod = State()
    admin_upload = State()


@dp.message_handler(commands='queue', state='*')
async def print_queue(message: types.Message, state: FSMContext):
    allowed = await print_next_queued(message.from_user)
    if not allowed:
        raise SkipHandler


async def print_next_added(user: types.User):
    info = await get_user(user)
    if not info.is_moderator():
        return False
    poi = await db.get_next_unchecked()
    if not poi:
        await bot.send_message(user.id, tr(('queue', 'empty')))
        return True
    await print_poi(user, poi)

    content = tr(('queue', 'new_poi'))
    kbd = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(
            '✔️ ' + tr(('queue', 'validated')),
            callback_data=POI_VALIDATE_CB.new(id=str(poi.id))
        )
    )
    await bot.send_message(user.id, content, reply_markup=kbd)


@dp.callback_query_handler(POI_VALIDATE_CB.filter(), state='*')
async def validate_poi(query: types.CallbackQuery, callback_data: Dict[str, str]):
    poi = await db.get_poi_by_id(int(callback_data['id']))
    if not poi:
        await query.answer(tr(('queue', 'poi_lost')))
        return
    await db.validate_poi(poi.id)
    await query.answer(tr(('queue', 'validated_ok')))
    await print_next_queued(query.from_user)


async def print_next_queued(user: types.User):
    info = await get_user(user)
    if not info.is_moderator():
        return False

    queue = await db.get_queue(1)
    if not queue:
        # This is done inside print_next_added()
        # await bot.send_message(user.id, tr(('queue', 'empty')))
        await print_next_added(user)
        return True

    q = queue[0]
    poi = await db.get_poi_by_id(q.poi_id)
    if not poi:
        await bot.send_message(user.id, tr(('queue', 'poi_lost_del')))
        await db.delete_queue(q)
        return True

    photo = None
    if q.field == 'message':
        content = tr(('queue', 'message'), user=h(q.user_name), name=h(poi.name))
        content += f'\n\n{h(q.new_value)}'
    else:
        content = tr(('queue', 'field'), user=h(q.user_name), name=h(poi.name), field=q.field)
        content += '\n'
        nothing = '<i>' + tr(('queue', 'nothing')) + '</i>'
        vold = nothing if q.old_value is None else h(q.old_value)
        vnew = nothing if q.new_value is None else h(q.new_value)
        content += f'\n<b>{tr(("queue", "old"))}:</b> {vold}'
        content += f'\n<b>{tr(("queue", "new"))}:</b> {vnew}'
        if q.field in ('photo_in', 'photo_out') and q.new_value:
            photo = os.path.join(config.PHOTOS, q.new_value + '.jpg')
            if not os.path.exists(photo):
                photo = None

    kbd = types.InlineKeyboardMarkup(row_width=3)
    if q.field != 'message':
        kbd.insert(types.InlineKeyboardButton(
            '🔍 ' + tr(('queue', 'look')),
            callback_data=MSG_CB.new(action='look', id=str(q.id)))
        )
        kbd.insert(types.InlineKeyboardButton(
            '✅ ' + tr(('queue', 'apply')),
            callback_data=MSG_CB.new(action='apply', id=str(q.id)))
        )
    else:
        kbd.insert(types.InlineKeyboardButton(
            '📝 ' + tr('edit_poi'), callback_data=POI_EDIT_CB.new(id=q.poi_id, d='0')))
    kbd.insert(types.InlineKeyboardButton(
        '❌ ' + tr(('queue', 'delete')),
        callback_data=MSG_CB.new(action='del', id=str(q.id)))
    )

    if not photo:
        await bot.send_message(user.id, content, parse_mode=HTML, reply_markup=kbd)
    else:
        await bot.send_photo(user.id, types.InputFile(photo), caption=content,
                             parse_mode=HTML, reply_markup=kbd)
    return True


@dp.callback_query_handler(MSG_CB.filter(), state='*')
async def process_queue(query: types.CallbackQuery, callback_data: Dict[str, str]):
    action = callback_data['action']
    q = await db.get_queue_msg(int(callback_data['id']))
    if not q:
        await query.answer(tr(('queue', 'missing')))
        return

    if action == 'del':
        await db.delete_queue(q)
        await query.answer(tr(('queue', 'deleted')))
    elif action == 'apply':
        await db.apply_queue(query.from_user.id, q)
        await query.answer(tr(('queue', 'applied')))
    elif action == 'look':
        poi = await db.get_poi_by_id(q.poi_id)
        if not poi:
            await query.answer(tr(('queue', 'poi_lost_del')))
            await db.delete_queue(q)
        else:
            await print_poi(query.from_user, poi, buttons=False)
            return
    else:
        await query.answer(f'Wrong queue action: "{action}"')

    await print_next_queued(query.from_user)


@dp.message_handler(content_types=types.ContentType.ANY, state=ModState.mod)
async def add_mod(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN:
        raise SkipHandler
    if not message.is_forward():
        await message.answer(tr(('admin', 'forward')))
        return
    await state.finish()
    me = await get_user(message.from_user)
    new_user = await get_user(message.forward_from)
    if new_user.is_moderator():
        await message.answer(tr(('admin', 'mod_already')))
        return
    await db.add_user_to_role(new_user, 'moderator', me)
    forget_user(new_user.id)
    await message.answer(tr(('admin', 'mod_added'), new_user.name))
    await bot.send_message(new_user.id, tr(('admin', 'mod_you')))


@dp.callback_query_handler(MOD_REMOVE_CB.filter(), state=ModState.mod)
async def remove_mod(query: types.CallbackQuery, callback_data: Dict[str, str],
                     state: FSMContext):
    if query.from_user.id != config.ADMIN:
        return
    await state.finish()
    user_id = callback_data['id']
    if user_id != '-':
        await db.remove_user_from_role(int(user_id), 'moderator')
        forget_user(int(user_id))
        await bot.send_message(query.from_user.id, tr(('admin', 'mod_removed')))
    else:
        await query.answer('Ok')


async def manage_mods(user: types.User, state: FSMContext):
    await state.finish()
    mods = await db.get_role_users('moderator')
    kbd = types.InlineKeyboardMarkup()
    if not mods:
        content = tr(('admin', 'no_mods'))
    else:
        content = tr(('admin', 'mod_list')) + ':\n\n'
        for i, mod in enumerate(mods, 1):
            content += f'{i}. {mod.name}\n'
            kbd.insert(types.InlineKeyboardButton(
                f'❌ {i} {mod.name}', callback_data=MOD_REMOVE_CB.new(id=str(mod.id))))
        content += '\n' + tr(('admin', 'mod_help'))
    kbd.insert(types.InlineKeyboardButton(
        tr(('edit', 'cancel')), callback_data=MOD_REMOVE_CB.new(id='-')))
    await bot.send_message(user.id, content, reply_markup=kbd)
    await ModState.mod.set()


@dp.message_handler(commands='deleted', state='*')
async def print_deleted(message: types.Message, state: FSMContext):
    pois = await db.get_last_deleted(6)
    if not pois:
        await message.answer(tr(('admin', 'no_deleted')))
        return
    await PoiState.poi_list.set()
    await state.set_data({'query': 'deleted', 'poi': [p.id for p in pois]})
    await print_poi_list(message.from_user, 'deleted', pois, shuffle=False)


async def print_missing_value(user: types.User, k: str, state: FSMContext):
    pois = await db.poi_with_empty_value(k, buildings=k != 'house',
                                         entrances=k not in ('flor', 'keywords'))
    if not pois:
        await bot.send_message(user.id, tr(('admin', 'no_such')))
        return
    await PoiState.poi_list.set()
    await state.set_data({'query': f'empty {k}', 'poi': [p.id for p in pois]})
    await print_poi_list(user, f'empty {k}', pois, shuffle=False)


async def print_audit(user: types.User):
    content = tr(('admin', 'audit')) + ':'
    last_audit = await db.get_last_audit(15)
    for a in last_audit:
        user_name = a.user_name if a.user_id == a.approved_by else str(a.user_id)
        if user_name is None:
            user_name = tr(('admin', 'admin'))
        line = f'{a.ts.strftime("%Y-%m-%d %H:%S")} {user_name}'
        if a.approved_by != a.user_id:
            line += ' (' + tr(('admin', 'confirmed_by'), a.user_name) + ')'
        if a.field == 'poi':
            line += ' ' + tr(('admin', 'created' if not a.old_value else 'deleted'))
            line += f' «{a.poi_name}» /poi{a.poi_id}'
        else:
            line += (' ' + tr(('admin', 'modified')) + f' «{a.poi_name}» /poi{a.poi_id} ' +
                     tr(('admin', 'field')) + f' {a.field}: "{a.old_value}" → "{a.new_value}"')
        content += '\n\n' + h(line) + '.'
    await bot.send_message(user.id, content, disable_web_page_preview=True)


async def dedup_photos():
    def hashall(photos):
        result = defaultdict(list)
        for photo in photos:
            path = os.path.join(config.PHOTOS, photo + '.jpg')
            image = Image.open(path)
            h = hashlib.md5()
            h.update(image.tobytes())
            result[h.digest()].append(photo)
        return result

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
        path = os.path.join(config.PHOTOS, photo + '.jpg')
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
                path = os.path.join(config.PHOTOS, photo + '.jpg')
                os.remove(path)
                removed += 1
    await conn.commit()
    return removed


async def delete_unused_photos():
    photos = set()
    for name in os.listdir(config.PHOTOS):
        if name.endswith('.jpg'):
            photos.add(name.rsplit('.', 1)[0])
    for predef in config.RESP['responses']:
        if 'photo' in predef:
            photos.discard(predef['photo'].rsplit('.', 1)[0])

    conn = await db.get_db()
    cursor = await conn.execute(
        "select name, photo_out, photo_in from poi where photo_out is not null "
        "or photo_in is not null")
    async for row in cursor:
        for c in (1, 2):
            if row[c]:
                photos.discard(row[c])
    for name in photos:
        path = os.path.join(config.PHOTOS, name + '.jpg')
        os.remove(path)
    return len(photos)


@dp.message_handler(state=ModState.admin_upload, content_types=types.ContentType.DOCUMENT)
async def upload_document(message: types.Message, state: FSMContext):
    tmp_dir = TemporaryDirectory(prefix='raybot')
    file_id = message.document.file_id
    try:
        f = await bot.get_file(file_id)
        path = os.path.join(tmp_dir.name, 'telegram_file')
        await f.download(path)
    except TelegramAPIError:
        tmp_dir.cleanup()
        await message.answer(tr(('editor', 'upload_fail')))
        return
    if not os.path.exists(path):
        tmp_dir.cleanup()
        await message.answer(tr(('editor', 'upload_fail')))
        return

    file_type = transfer.get_file_type(path)
    try:
        if file_type == 'geojson':
            with open(path, 'r') as f:
                await transfer.import_geojson(f)
            await message.answer(
                tr(('admin', 'up_json')) + ' ' + tr(('admin', 'no_maintenance')))
        elif file_type == 'tags':
            with open(path, 'r') as f:
                yaml = await transfer.import_tags(f)
            if yaml:
                doc = types.InputFile(yaml, filename='new_tags.yml')
                await message.answer_document(
                    doc, caption=tr(('admin', 'tags_caption')))
                yaml.close()
            await message.answer(
                tr(('admin', 'up_csv')) + ' ' + tr(('admin', 'no_maintenance')))
        else:
            raise ValueError(tr(('admin', 'unknown_file')))
    except Exception as e:
        await message.answer(tr(('admin', 'error'), e))
        return
    finally:
        tmp_dir.cleanup()
    config.MAINTENANCE = False
    await state.finish()


@dp.message_handler(commands='admin', state='*')
async def admin_info(message: types.Message):
    info = await get_user(message.from_user)
    if not info.is_moderator():
        raise SkipHandler
    kbd = types.InlineKeyboardMarkup(row_width=2)
    if info.id == config.ADMIN:
        kbd.insert(types.InlineKeyboardButton(tr(('admin_menu', 'mods')),
                                              callback_data=ADMIN_CB.new(action='mod')))
        kbd.insert(types.InlineKeyboardButton(tr(('admin_menu', 'dedup')),
                                              callback_data=ADMIN_CB.new(action='dedup')))
        kbd.insert(types.InlineKeyboardButton(tr(('admin_menu', 'unused')),
                                              callback_data=ADMIN_CB.new(action='unused')))
        kbd.insert(types.InlineKeyboardButton(tr(('admin_menu', 'base')),
                                              callback_data=ADMIN_CB.new(action='base')))
    kbd.insert(types.InlineKeyboardButton(tr(('admin_menu', 'audit')),
                                          callback_data=ADMIN_CB.new(action='audit')))
    kbd.insert(types.InlineKeyboardButton(tr(('admin_menu', 'reindex')),
                                          callback_data=ADMIN_CB.new(action='reindex')))
    kbd.row(
        types.InlineKeyboardButton(tr(('admin_menu', 'no_house')),
                                   callback_data=ADMIN_CB.new(action='mis-house')),
        types.InlineKeyboardButton(tr(('admin_menu', 'no_floor')),
                                   callback_data=ADMIN_CB.new(action='mis-floor')),
        types.InlineKeyboardButton(tr(('admin_menu', 'no_photo')),
                                   callback_data=ADMIN_CB.new(action='mis-photo')),
    )
    kbd.row(
        types.InlineKeyboardButton(tr(('admin_menu', 'no_tag')),
                                   callback_data=ADMIN_CB.new(action='mis-tag')),
        types.InlineKeyboardButton(tr(('admin_menu', 'no_keywords')),
                                   callback_data=ADMIN_CB.new(action='mis-keywords')),
    )
    await message.answer(tr(('admin_menu', 'msg')), reply_markup=kbd)


@dp.callback_query_handler(ADMIN_CB.filter(), state='*')
async def admin_command(query: types.CallbackQuery, callback_data: Dict[str, str],
                        state: FSMContext):
    user = query.from_user
    info = await get_user(user)
    if not info.is_moderator():
        raise SkipHandler
    action = callback_data['action']
    if action == 'mod' and user.id == config.ADMIN:
        await manage_mods(user, state)
        return
    elif action == 'reindex':
        await db.reindex()
        await bot.send_message(user.id, tr(('admin_menu', 'reindexed')))
    elif action == 'dedup' and user.id == config.ADMIN:
        cnt = await dedup_photos()
        await bot.send_message(query.from_user.id, tr(('admin_menu', 'deduped'), cnt))
    elif action == 'unused' and user.id == config.ADMIN:
        cnt = await delete_unused_photos()
        await bot.send_message(query.from_user.id, tr(('admin_menu', 'del_unused'), cnt))
    elif action == 'audit':
        await print_audit(user)
    elif action == 'mis-house':
        await print_missing_value(user, 'house', state)
    elif action == 'mis-photo':
        await print_missing_value(user, 'photo_out', state)
    elif action == 'mis-floor':
        await print_missing_value(user, 'flor', state)
    elif action == 'mis-keywords':
        await print_missing_value(user, 'keywords', state)
    elif action == 'mis-tag':
        await print_missing_value(user, 'tag', state)
    elif action == 'base':
        # Print a submenu
        kbd = types.InlineKeyboardMarkup(row_width=2)
        kbd.insert(types.InlineKeyboardButton(tr(('admin_base', 'down_json')),
                                              callback_data=ADMIN_CB.new(action='down-json')))
        kbd.insert(types.InlineKeyboardButton(tr(('admin_base', 'down_tags')),
                                              callback_data=ADMIN_CB.new(action='down-tags')))
        kbd.insert(types.InlineKeyboardButton(tr(('admin_base', 'upload')),
                                              callback_data=ADMIN_CB.new(action='upload')))
        kbd.insert(types.InlineKeyboardButton(
            tr(('admin_base', 'freeze' if not config.MAINTENANCE else 'unfreeze')),
            callback_data=ADMIN_CB.new(action='maintenance')))
        await bot.edit_message_reply_markup(
            query.from_user.id, query.message.message_id, reply_markup=kbd)
    elif action == 'upload' and user.id == config.ADMIN:
        await bot.send_message(query.from_user.id, tr(('admin_base', 'send_file')))
        await ModState.admin_upload.set()
    elif action == 'down-json' and user.id == config.ADMIN:
        f = StringIO()
        await transfer.export_geojson(f)
        f.seek(0)
        date = datetime.now().strftime('%y%m%d')
        doc = types.InputFile(f, filename=f'poi-{date}.geojson')
        caption = tr(('admin_base', 'down_json')) + ' ' + tr(('admin_base', 'maintenance'))
        await bot.send_document(query.from_user.id, doc, caption=caption)
        config.MAINTENANCE = True
        f.close()
    elif action == 'down-tags' and user.id == config.ADMIN:
        f = StringIO()
        await transfer.export_tags(f)
        f.seek(0)
        date = datetime.now().strftime('%y%m%d')
        doc = types.InputFile(f, filename=f'tags-{date}.csv')
        caption = tr(('admin_base', 'down_tags')) + ' ' + tr(('admin_base', 'maintenance'))
        await bot.send_document(query.from_user.id, doc, caption=caption)
        config.MAINTENANCE = True
        f.close()
    elif action == 'maintenance' and user.id == config.ADMIN:
        config.MAINTENANCE = not config.MAINTENANCE
        if config.MAINTENANCE:
            await query.answer(tr(('admin_base', 'maintenance')))
        else:
            await query.answer(tr(('admin_base', 'no_maintenance')))
    else:
        await query.answer(tr(('admin_menu', 'wrong_action'), action))
