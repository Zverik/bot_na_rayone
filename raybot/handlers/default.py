from raybot import config
from raybot.model import db, Location
from raybot.bot import dp
from raybot.util import split_tokens, has_keyword, get_user, h, HTML, get_buttons, prune_users
from raybot.actions.addr import test_address
from raybot.actions.poi import PoiState, print_poi, print_poi_list
from raybot.actions.messages import process_reply
import os
import csv
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext


@dp.message_handler(commands=['start'], state='*')
async def welcome(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(config.RESP['start'].replace('\n', '\n\n'), reply_markup=get_buttons())
    payload = message.get_args()
    if payload:
        try:
            poi = await db.get_poi_by_id(int(payload))
            await PoiState.poi.set()
            await state.set_data({'poi': poi.id})
            await print_poi(message.from_user, poi)
        except ValueError:
            tokens = split_tokens(payload)
            if tokens:
                await process_query(message, state, tokens)


@dp.message_handler(commands=['help'], state='*')
async def help(message: types.Message, state: FSMContext):
    await state.finish()
    msg = config.RESP['help']
    stats = await db.get_stats()
    for k, v in stats.items():
        msg = msg.replace('{' + k + '}', h(str(v)))
    await message.answer(msg, reply_markup=get_buttons())


def write_search_log(message, tokens, result):
    row = [message.date.strftime('%Y-%m-%d'), message.text.strip(),
           None if not tokens else ' '.join(tokens), result]
    try:
        with open(os.path.join(config.LOGS, 'search.log'), 'a') as f:
            w = csv.writer(f, delimiter='\t')
            w.writerow(row)
    except IOError:
        logging.warning('Failed to write log line: %s', row)


@dp.message_handler(state='*')
async def process(message: types.Message, state: FSMContext):
    if message.from_user.is_bot:
        return
    if message.reply_to_message and message.reply_to_message.is_forward():
        await process_reply(message)
        return
    for user_id in prune_users(message.from_user.id):
        await state.storage.finish(user=user_id)
        # We used to send a message here, but "disable_notification" only
        # disables a buzz, not an unread notification.

    tokens = split_tokens(message.text)
    if not tokens:
        write_search_log(message, None, 'empty')
        return

    # Reset state
    await state.finish()

    # First check for pre-defined replies
    if await test_predefined(message, tokens):
        write_search_log(message, tokens, 'predefined')
        return

    # Now check for streets
    if await test_address(message, tokens, state):
        write_search_log(message, tokens, 'address')
        return

    # Finally check keywords
    await process_query(message, state, tokens)


async def process_query(message, state, tokens):
    query = ' '.join(tokens)
    pois = await db.find_poi(query)
    if len(pois) == 1:
        write_search_log(message, tokens, f'poi {pois[0].id}')
        await PoiState.poi.set()
        await state.set_data({'poi': pois[0].id})
        await print_poi(message.from_user, pois[0])
    elif len(pois) > 1:
        write_search_log(message, tokens, f'{len(pois)} results')
        await PoiState.poi_list.set()
        await state.set_data({'query': query, 'poi': [p.id for p in pois]})
        await print_poi_list(message.from_user, message.text, pois)
    else:
        write_search_log(message, tokens, 'not found')
        new_kbd = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton('💬 Сообщить модераторам', callback_data='missing_mod'),
            types.InlineKeyboardButton('➕ Добавить заведение', callback_data='new')
        )
        await message.answer(config.MSG['not_found'].replace('%s', message.text),
                             reply_markup=new_kbd)


async def test_predefined(message, tokens) -> bool:
    for resp in config.RESP['responses']:
        if has_keyword(tokens, resp['keywords']):
            if 'role' in resp:
                user = await get_user(message.from_user)
                if resp['role'] not in user.roles:
                    continue
            msg = resp['name']
            photo = None
            if 'photo' in resp:
                photo_path = os.path.join(config.PHOTOS, resp['photo'])
                if os.path.exists(photo_path):
                    file_ids = await db.find_file_ids(
                        {resp['photo']: os.path.getsize(photo_path)})
                    if file_ids:
                        photo = file_ids[resp['photo']]
                    else:
                        photo = types.InputFile(photo_path)
            if 'message' in resp:
                msg += '\n\n' + resp['message']

            if photo:
                msg = await message.answer_photo(
                    photo, caption=msg, parse_mode=HTML,
                    reply_markup=get_buttons())
                if not isinstance(photo, str):
                    file_id = msg.photo[0].file_id
                    await db.store_file_id(resp['photo'], os.path.getsize(photo_path), file_id)
            else:
                await message.answer(msg, parse_mode=HTML,
                                     reply_markup=get_buttons())
            return True
    return False


@dp.message_handler(content_types=types.ContentType.LOCATION, state='*')
async def set_loc(message):
    location = Location(message.location.longitude, message.location.latitude)
    info = await get_user(message.from_user)
    info.location = location
    await message.answer(config.MSG['location'])
