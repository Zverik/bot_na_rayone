from raybot import config
from raybot.model import db, POI, Location
from raybot.bot import bot, dp
from raybot.util import h, HTML, split_tokens, get_buttons, get_map, get_user
from raybot.actions.poi import POI_EDIT_CB
from raybot.action.messages import broadcast_str
import re
import os
import random
import humanized_opening_hours as hoh
from aiosqlite import DatabaseError
from string import ascii_lowercase
from datetime import datetime
from typing import Dict
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup


HOUSE_CB = CallbackData('ehouse', 'hid')
BOOL_CB = CallbackData('boolattr', 'attr', 'value')
PHOTO_CB = CallbackData('ephoto', 'name', 'which')
TAG_CB = CallbackData('etag', 'tag')


class EditState(StatesGroup):
    name = State()
    location = State()
    keywords = State()
    confirm = State()
    attr = State()
    comment = State()


def cancel_keyboard():
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(config.MSG['cancel'], callback_data='cancel')
    )


def location_keyboard():
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(
            'Взять lat,lon с сайта',
            url='https://zverik.github.io/latlon/#16/53.9312/27.6525'),
        types.InlineKeyboardButton(config.MSG['cancel'], callback_data='cancel'),
    )


@dp.callback_query_handler(state=EditState.all_states, text='cancel')
async def new_cancel(query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.send_message(
        query.from_user.id,
        config.MSG['new_poi']['cancel'],
        reply_markup=get_buttons()
    )


@dp.callback_query_handler(state='*', text='new')
async def new_poi(query: types.CallbackQuery):
    await EditState.name.set()
    await bot.send_message(
        query.from_user.id,
        config.MSG['new_poi']['name'],
        reply_markup=cancel_keyboard()
    )


@dp.callback_query_handler(POI_EDIT_CB.filter(), state='*')
async def edit_poi(query: types.CallbackQuery, callback_data: Dict[str, str],
                   state: FSMContext):
    poi = await db.get_poi_by_id(int(callback_data['id']))
    await state.set_data({'poi': poi})
    await EditState.confirm.set()
    await print_edit_options(query.from_user, state)


@dp.message_handler(state=EditState.name)
async def new_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer(config.MSG['new_poi']['name_too_short'])
        return
    await state.set_data({'name': name})
    await EditState.location.set()
    await message.answer(config.MSG['new_poi']['location'], reply_markup=location_keyboard())


def parse_location(message: types.Message):
    ll = re.match(r'^\s*(-?\d+\.\d+),\s*(-?\d+\.\d+)\s*$', message.text or '')
    if message.location:
        return Location(lon=message.location.longitude, lat=message.location.latitude)
    elif ll:
        return Location(lat=float(ll.group(1)), lon=float(ll.group(2)))
    return None


@dp.message_handler(state=EditState.location,
                    content_types=[types.ContentType.TEXT, types.ContentType.LOCATION])
async def new_location(message: types.Message, state: FSMContext):
    loc = parse_location(message)
    if not loc:
        await message.answer(config.MSG['new_poi']['no_location'], reply_markup=location_keyboard())
        return
    await state.update_data(lon=loc.lon, lat=loc.lat)
    await EditState.keywords.set()
    await message.answer(config.MSG['new_poi']['keywords'], reply_markup=cancel_keyboard())


@dp.message_handler(state=EditState.keywords)
async def new_keywords(message: types.Message, state: FSMContext):
    keywords = split_tokens(message.text)
    if not keywords:
        await message.answer(config.MSG['new_poi']['no_keywords'])
        return
    # Create a POI
    data = await state.get_data()
    poi = POI(
        name=data['name'],
        location=Location(lat=data['lat'], lon=data['lon']),
        keywords=' '.join(keywords)
    )
    await state.set_data({'poi': poi})
    await EditState.confirm.set()
    await print_edit_options(message.from_user, state, config.MSG['new_poi']['confirm'])


def format(v, yes='да', no='нет', null='неизвестно'):
    if v is None or v == '':
        return f'<i>{null}</i>'
    if isinstance(v, str):
        return h(v)
    if isinstance(v, bool):
        return yes if v else no
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, hoh.OHParser):
        return h(v.field)
    if isinstance(v, Location):
        return f'v.lat, v.lon'
    return str(v)


def new_keyboard():
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(config.MSG['save'], callback_data='save'),
        types.InlineKeyboardButton(config.MSG['cancel'], callback_data='cancel')
    )


async def print_edit_options(user: types.User, state: FSMContext, comment=None):
    poi = (await state.get_data())['poi']
    lines = []
    lines.append(f'<b>{format(poi.name)}</b>')
    lines.append('')
    lines.append(f'/edesc <b>Описание:</b> {format(poi.description, null="нет")}')
    lines.append(f'/ekey <b>Ключевые слова:</b> {format(poi.keywords)}')
    lines.append(f'/etag <b>OSM-тег:</b> {format(poi.tag)}')
    lines.append(f'/ehouse <b>Адрес:</b> {format(poi.house_name)}')
    lines.append(f'/eaddr <b>Местонахождение:</b> {format(poi.address_part)}')
    lines.append(f'/ehour <b>Часы работы:</b> {format(poi.hours_src)}')
    lines.append('/eloc <b>Координаты:</b> '
                 '<a href="https://zverik.github.io/latlon/#18/'
                 f'{poi.location.lat}/{poi.location.lon}">'
                 'смотреть</a>')
    lines.append(f'/ephone <b>Телефоны:</b> {format("; ".join(poi.phones))}')
    lines.append(f'/ewifi <b>Есть ли Wi-Fi:</b> {format(poi.has_wifi)}')
    lines.append(f'/ecard <b>Оплата картой:</b> {format(poi.accepts_cards)}')
    if poi.links:
        links = ', '.join([f'<a href="{l[1]}">{h(l[0])}</a>' for l in poi.links])
    else:
        links = '<i>нет</i>'
    lines.append(f'/elink <b>Ссылки:</b> {links}')
    lines.append(f'/ecom <b>Комментарий:</b> {format(poi.comment, null="нет")}')
    if poi.photo_out and poi.photo_in:
        photos = 'обе'
    elif poi.photo_out:
        photos = 'только вход'
    elif poi.photo_in:
        photos = 'только внутри'
    else:
        photos = 'нет'
    lines.append(f'<b>Фотографии:</b> {photos} (залейте замену или /ephoto для просмотра)')
    lines.append('🗑️ Удалить: /delete')

    content = '\n'.join(lines)
    if comment is None:
        comment = config.MSG['new_poi']['confirm2']
    if comment:
        content += '\n\n' + h(comment)
    await bot.send_message(user.id, content, parse_mode=HTML, reply_markup=new_keyboard(),
                           disable_web_page_preview=True)


def cancel_attr_kbd():
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(config.MSG['editor']['cancel'], callback_data='cancel_attr')
    )


def edit_loc_kbd(poi):
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(
            'Взять lat,lon с сайта',
            url='https://zverik.github.io/latlon/#18/'
                f'{poi.location.lat}/{poi.location.lon}"'),
        types.InlineKeyboardButton(config.MSG['editor']['cancel'], callback_data='cancel_attr')
    )


def boolean_kbd(attr: str):
    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton('Есть', callback_data=BOOL_CB.new(attr=attr, value='true')),
        types.InlineKeyboardButton('Нет', callback_data=BOOL_CB.new(attr=attr, value='false')),
        types.InlineKeyboardButton('ХЗ', callback_data=BOOL_CB.new(attr=attr, value='null')),
        types.InlineKeyboardButton(config.MSG['editor']['cancel'], callback_data='cancel_attr')
    )


def tag_kbd():
    kbd = types.InlineKeyboardMarkup(row_width=3)
    for tag in config.MSG['suggest_tags']:
        kbd.insert(types.InlineKeyboardButton(config.MSG['tags'].get(tag, [tag])[0],
                                              callback_data=TAG_CB.new(tag=tag)))
    kbd.add(types.InlineKeyboardButton(config.MSG['editor']['cancel'], callback_data='cancel_attr'))
    return kbd


@dp.message_handler(commands='ephoto', state=EditState.confirm)
async def show_photos(message: types.Message, state: FSMContext):
    poi = (await state.get_data())['poi']
    for photo, where in [(poi.photo_out, 'снаружи'), (poi.photo_in, 'внутри')]:
        if photo:
            path = os.path.join(config.PHOTOS, photo + '.jpg')
            if os.path.exists(path):
                kbd = types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton('🗑️ Удалить', callback_data=PHOTO_CB.new(
                        name=photo, which='unlink')),
                    types.InlineKeyboardButton(config.MSG['editor']['cancel'],
                                               callback_data='cancel_attr')
                )
                await message.answer_photo(types.InputFile(path), caption=where,
                                           reply_markup=kbd)


@dp.message_handler(state=EditState.confirm, content_types=types.ContentType.PHOTO)
async def upload_photo(message: types.Message, state: FSMContext):
    f = await bot.get_file(message.photo[-1].file_id)
    name = ''.join(random.sample(ascii_lowercase, 4)) + datetime.now().strftime('%y%m%d%H%M%S')
    path = os.path.join(config.PHOTOS, name + '.jpg')
    await f.download(path)
    if not os.path.exists(path):
        await message.answer(config.MSG['editor']['upload_fail'])
        return

    kbd = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton('Снаружи', callback_data=PHOTO_CB.new(
            name=name, which='out')),
        types.InlineKeyboardButton('Изнутри', callback_data=PHOTO_CB.new(
            name=name, which='in')),
        types.InlineKeyboardButton('🗑️ Ой, удали', callback_data=PHOTO_CB.new(
            name=name, which='del'))
    )
    await message.answer(config.MSG['editor']['photo'], reply_markup=kbd)


@dp.callback_query_handler(PHOTO_CB.filter(), state=EditState.confirm)
async def store_photo(query: types.CallbackQuery, callback_data: Dict[str, str],
                      state: FSMContext):
    poi = (await state.get_data())['poi']
    name = callback_data['name']
    which = callback_data['which']
    if which == 'out':
        poi.photo_out = name
    elif which == 'in':
        poi.photo_in = name
    elif which == 'unlink':
        if poi.photo_out == name:
            poi.photo_out = None
        elif poi.photo_in == name:
            poi.photo_in = None
    else:
        path = os.path.join(config.PHOTOS, name + '.jpg')
        os.remove(path)
        await query.answer('Хорошо, фоточку удалил.')
    await state.set_data({'poi': poi})
    await print_edit_options(query.from_user, state)


@dp.message_handler(commands='edesc', state=EditState.confirm)
async def edit_desc(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['desc'] + ' ' + config.MSG['editor']['dash'],
                         reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='desc')


@dp.message_handler(commands='etag', state=EditState.confirm)
async def edit_tag(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['tag'] + ' ' + config.MSG['editor']['dash'],
                         reply_markup=tag_kbd())
    await EditState.attr.set()
    await state.update_data(attr='tag')


@dp.message_handler(commands='ecom', state=EditState.confirm)
async def edit_comment(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['comment'] + ' ' + config.MSG['editor']['dash'],
                         reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='comment')


@dp.message_handler(commands='ekey', state=EditState.confirm)
async def edit_keywords(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['keywords'], reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='keywords')


@dp.message_handler(commands='eaddr', state=EditState.confirm)
async def edit_address(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['address'] + ' ' + config.MSG['editor']['dash'],
                         reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='address')


@dp.message_handler(commands='eloc', state=EditState.confirm)
async def edit_location(message: types.Message, state: FSMContext):
    poi = (await state.get_data())['poi']
    await message.answer(config.MSG['editor']['location'], reply_markup=edit_loc_kbd(poi))
    await EditState.attr.set()
    await state.update_data(attr='location')


@dp.message_handler(commands='ehouse', state=EditState.confirm)
async def edit_house(message: types.Message, state: FSMContext):
    poi = (await state.get_data())['poi']
    houses = await db.get_houses()
    houses.sort(key=lambda h: poi.location.distance(h.location))
    houses = houses[:3]
    # Prepare the map
    map_file = get_map([h.location for h in houses], ref=poi.location)
    # Prepare the keyboard
    kbd = types.InlineKeyboardMarkup(row_width=1)
    for i, house in enumerate(houses, 1):
        prefix = '✅ ' if house == poi.house else ''
        kbd.add(types.InlineKeyboardButton(
            f'{prefix} {i} {house.name}', callback_data=HOUSE_CB.new(hid=house.key)))
    kbd.add(types.InlineKeyboardButton(
        'Оставить как есть', callback_data='cancel_attr'))
    # Finally send the reply
    if map_file:
        await message.answer_photo(types.InputFile(map_file.name),
                                   caption=config.MSG['editor']['house'], reply_markup=kbd)
        map_file.close()
    else:
        await message.answer(config.MSG['editor']['house'], reply_markup=kbd)


@dp.callback_query_handler(HOUSE_CB.filter(), state=EditState.confirm)
async def update_house(query: types.CallbackQuery, callback_data: Dict[str, str],
                       state: FSMContext):
    poi = (await state.get_data())['poi']
    hid = callback_data['hid']
    poi.house = hid
    h_data = await db.get_poi_by_key(hid)
    if h_data:
        poi.house_name = h_data.name
    await state.set_data({'poi': poi})
    await print_edit_options(query.from_user, state)


@dp.message_handler(commands='ewifi', state=EditState.confirm)
async def edit_wifi(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['wifi'], reply_markup=boolean_kbd('wifi'))


@dp.message_handler(commands='ecard', state=EditState.confirm)
async def edit_cards(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['cards'], reply_markup=boolean_kbd('cards'))


@dp.callback_query_handler(BOOL_CB.filter(), state=EditState.confirm)
async def update_boolean(query: types.CallbackQuery, callback_data: Dict[str, str],
                         state: FSMContext):
    poi = (await state.get_data())['poi']
    attr = callback_data['attr']
    svalue = callback_data['value']
    if svalue == 'null':
        value = None
    else:
        value = svalue == 'true'
    if attr == 'wifi':
        poi.has_wifi = value
    elif attr == 'cards':
        poi.accepts_cards = value
    else:
        query.answer(f'Неизвестное поле {attr}')
    await state.set_data({'poi': poi})
    await EditState.confirm.set()
    await print_edit_options(query.from_user, state)


@dp.callback_query_handler(TAG_CB.filter(), state=EditState.attr)
async def update_tag(query: types.CallbackQuery, callback_data: Dict[str, str],
                     state: FSMContext):
    poi = (await state.get_data())['poi']
    poi.tag = callback_data['tag']
    await state.set_data({'poi': poi})
    await EditState.confirm.set()
    await print_edit_options(query.from_user, state)


@dp.message_handler(commands='elink', state=EditState.confirm)
async def edit_links(message: types.Message, state: FSMContext):
    poi = (await state.get_data())['poi']
    if poi.links:
        content = 'Ссылки, которые есть:\n\n'
        content += '\n'.join([f'🔗 {h(l[0])}: {h(l[1])}' for l in poi.links])
    else:
        content = 'Пока нет ни одной ссылки.'
    content += '\n\n' + config.MSG['editor']['links']
    await message.answer(content, disable_web_page_preview=True, reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='links')


@dp.message_handler(commands='ephone', state=EditState.confirm)
async def edit_phones(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['phones'] + ' ' + config.MSG['editor']['dash'],
                         reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='phones')


@dp.message_handler(commands='ehour', state=EditState.confirm)
async def edit_hours(message: types.Message, state: FSMContext):
    await message.answer(config.MSG['editor']['hours'] + ' ' + config.MSG['editor']['dash'],
                         reply_markup=cancel_attr_kbd())
    await EditState.attr.set()
    await state.update_data(attr='hours')


@dp.callback_query_handler(text='cancel_attr', state=EditState.attr)
async def cancel_attr(query: types.CallbackQuery, state: FSMContext):
    await EditState.confirm.set()
    await print_edit_options(query.from_user, state)


@dp.message_handler(content_types=types.ContentType.LOCATION, state=EditState.attr)
async def store_location(message: types.Message, state: FSMContext):
    data = await state.get_data()
    poi = data['poi']
    attr = data['attr']
    if attr != 'location':
        return
    loc = parse_location(message)
    if not loc:
        await message.answer(config.MSG['new_poi']['no_location'], reply_markup=edit_loc_kbd(poi))
        return
    poi.location = loc
    await state.set_data({'poi': poi})
    await EditState.confirm.set()
    await print_edit_options(message.from_user, state)


RE_URL = re.compile(r'^https?://')
RE_HOURS = re.compile(r'^(?:(пн|вт|ср|чт|пт|сб|вс)(?:\s*-\s*(пн|вт|ср|чт|пт|сб|вс))?\s+)?'
                      r'(\d\d?(?:[:.]\d\d)?)\s*-\s*(\d\d(?:[:.]\d\d)?)'
                      r'(?:\s+об?е?д?\s+(\d\d?(?:[:.]\d\d)?)\s*-\s*(\d\d(?:[:.]\d\d)?))?$')
HOURS_WEEK = {'пн': 'Mo', 'вт': 'Tu', 'ср': 'We', 'чт': 'Th',
              'пт': 'Fr', 'сб': 'Sa', 'вс': 'Su'}


def parse_hours(s):
    def norm_hour(h):
        if not h:
            return None
        if len(h) < 4:
            h += ':00'
        return h.rjust(5, '0')

    parts = []
    for part in s.split(','):
        m = RE_HOURS.match(part.strip().lower())
        if not m:
            raise ValueError(part)
        wd = 'Mo-Su' if not m.group(1) else HOURS_WEEK[m.group(1)]
        if m.group(2):
            wd += '-' + HOURS_WEEK[m.group(2)]
        h1 = norm_hour(m.group(3))
        h2 = norm_hour(m.group(4))
        l1 = norm_hour(m.group(5))
        l2 = norm_hour(m.group(6))
        if l1:
            wd += f' {h1}-{l1},{l2}-{h2}'
        else:
            wd += f' {h1}-{h2}'
        parts.append(wd)
    return '; '.join(parts)


@dp.message_handler(state=EditState.attr)
async def store_attr(message: types.Message, state: FSMContext):
    data = await state.get_data()
    poi = data['poi']
    attr = data['attr']
    value = message.text.strip()

    if attr == 'desc':
        poi.description = None if value == '-' else value
    elif attr == 'comment':
        poi.comment = None if value == '-' else value
    elif attr == 'tag':
        if value == '-':
            poi.tag = None
        else:
            parts = [p.strip().lower() for p in value.split('=')]
            if len(parts) != 2 or not re.match(r'^[a-z]+$', parts[0] + parts[1]):
                await message.answer(f'Тег должен быть в виде ключ=значение, а не {value}.',
                                     reply_markup=cancel_attr_kbd())
                return
            poi.tag = '='.join(parts)
    elif attr == 'keywords':
        new_kw = split_tokens(value)
        if new_kw:
            old_kw = poi.keywords.split()
            poi.keywords = ' '.join(old_kw + new_kw)
    elif attr == 'address':
        poi.address_part = None if value == '-' else value
    elif attr == 'location':
        loc = parse_location(message)
        if not loc:
            await message.answer(config.MSG['new_poi']['no_location'],
                                 reply_markup=edit_loc_kbd(poi))
            return
        poi.location = loc
    elif attr == 'hours':
        if value == '-':
            poi.hours = None
            poi.hours_src = None
        else:
            try:
                hours = parse_hours(value)
            except ValueError as e:
                await message.answer(f'Непонятный формат: "{e}".', reply_markup=cancel_attr_kbd())
                return
            poi.hours_src = hours
            poi.hours = hoh.OHParser(hours)
    elif attr == 'phones':
        if not value or value == '-':
            poi.phones = []
        else:
            poi.phones = [p.strip() for p in value.split(';')]
    elif attr == 'links':
        if value:
            parts = value.split(None, 1)
            parts[0] = parts[0].lower()
            if len(parts) == 1 and RE_URL.match(parts[0]):
                parts = [config.MSG['default_link'], parts[0]]
            if len(parts) == 1:
                poi.links = [l for l in poi.links if l[0] != parts[0]]
            else:
                if not RE_URL.match(parts[1]):
                    await message.answer(f'Можно только ссылки на http и https.',
                                         reply_markup=cancel_attr_kbd())
                    return
                found = False
                for i, l in enumerate(poi.links):
                    if l[0] == parts[0]:
                        found = True
                        l[1] = parts[1]
                if not found:
                    poi.links.append(parts)
    else:
        await message.answer(f'Атрибут {attr} пока не редактируем.')

    await state.set_data({'poi': poi})
    await EditState.confirm.set()
    await print_edit_options(message.from_user, state)


@dp.message_handler(commands='delete', state=EditState.confirm)
async def delete_poi(message: types.Message, state: FSMContext):
    info = await get_user(message.from_user)
    if not info.is_moderator():
        await message.answer(config.MSG['editor']['cant_delete'])
        return

    poi = (await state.get_data())['poi']
    await state.finish()
    await db.delete_poi(message.from_user.id, poi)
    await message.answer(config.MSG['editor']['deleted'], reply_markup=get_buttons())


@dp.message_handler(state=EditState.confirm)
async def print_edit_again(message: types.Message, state: FSMContext):
    poi = (await state.get_data())['poi']
    user = await get_user(message.from_user)
    await db.add_to_queue(user, poi, message.text)
    await state.finish()
    await message.answer(config.MSG['editor']['sent'])


@dp.callback_query_handler(state=EditState.confirm, text='save')
async def new_save(query: types.CallbackQuery, state: FSMContext):
    poi = (await state.get_data())['poi']

    # If not a moderator, mark this as needs check
    user = await get_user(query.from_user)
    if not user.is_moderator() and poi.id is None:
        poi.needs_check = True

    # Send the POI to the database
    try:
        if user.is_moderator() or poi.id is None:
            await db.insert_poi(query.from_user.id, poi)
            saved = 'saved'
        else:
            await db.add_to_queue(user, poi)
            await broadcast_str(config.MSG['queue']['added'])
            saved = 'sent'
    except DatabaseError as e:
        await bot.send_message(
            query.from_user.id,
            f'Ошибка при сохранении данных: {e}. Попробуйте ещё раз или отмените.',
            reply_markup=new_keyboard())
        return

    # Reset state and thank the user
    await state.finish()
    await bot.send_message(
        query.from_user.id,
        config.MSG['editor'][saved],
        reply_markup=get_buttons()
    )
