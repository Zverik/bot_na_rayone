from raybot import config
from raybot.model import db, POI, Location
from raybot.bot import bot, dp
from raybot.util import get_user, get_buttons, delete_msg
from raybot.actions.poi import POI_EDIT_CB, REVIEW_HOUSE_CB
from typing import Dict, List
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher.handler import SkipHandler


FLOOR_CB = CallbackData('sreview', 'house', 'floor')
REVIEW_CB = CallbackData('review_poi', 'id')
EDIT_CB = CallbackData('review_edit', 'mode')


async def check_floors(query: types.CallbackQuery, pois: List[POI], house: str = None):
    if not pois:
        kbd = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton(config.MSG['add_poi'], callback_data='new')
        )
        await bot.send_message(query.from_user.id, config.MSG['no_poi_around'], reply_markup=kbd)
        return

    floors = set([p.floor for p in pois])
    if len(floors) >= 2:
        khouse = '-' if house is None else house
        kbd = types.InlineKeyboardMarkup(row_width=3)
        for ifloor in floors:
            label = ifloor if ifloor is not None else config.MSG['review']['no_floor']
            kbd.insert(types.InlineKeyboardButton(
                label, callback_data=FLOOR_CB.new(house=khouse, floor=ifloor or '-')))
        kbd.insert(types.InlineKeyboardButton(
            config.MSG['review']['all_floors'],
            callback_data=FLOOR_CB.new(house=khouse, floor='*')))
        await bot.edit_message_reply_markup(
            query.from_user.id, query.message.message_id, reply_markup=kbd)
    else:
        # Just one floor, so doesn't matter
        await start_review(query.from_user, house)


@dp.callback_query_handler(state='*', text='start_review')
async def start_review_callback(query: types.CallbackQuery):
    # First check the floors around
    info = await get_user(query.from_user)
    if not info.location:
        await query.answer(config.MSG['review']['send_loc'])
        return
    if info.review_ctx:
        # We have an ongoing review session, continue it
        await start_review(query.from_user, *info.review_ctx)
        return
    pois = await db.get_poi_around(info.location, count=10)

    # If the nearest poi doesn't have floor, then so be it
    if pois and pois[0].floor is None:
        await start_review(query.from_user)
        return

    # Find floor options
    await check_floors(query, pois)


@dp.callback_query_handler(REVIEW_HOUSE_CB.filter(), state='*')
async def review_from_house(query: types.CallbackQuery, callback_data: Dict[str, str]):
    house = callback_data['house']
    pois = await db.get_poi_by_house(house)
    await check_floors(query, pois, house)


@dp.callback_query_handler(FLOOR_CB.filter(), state='*')
async def select_floor(query: types.CallbackQuery, callback_data: Dict[str, str]):
    house = callback_data['house']
    floor = callback_data['floor']
    if floor == '*':
        floor = None
    await start_review(query.from_user, None if house == '-' else house, floor)


@dp.callback_query_handler(state='*', text='stop_review')
async def stop_review(query: types.CallbackQuery):
    info = await get_user(query.from_user)
    info.review = None
    info.review_ctx = None
    await delete_msg(bot, query)
    await bot.send_message(query.from_user.id, config.MSG['review']['stopped'],
                           reply_markup=get_buttons())


@dp.callback_query_handler(state='*', text='continue_review')
async def continue_review(query: types.CallbackQuery):
    info = await get_user(query.from_user)
    if not info.review:
        await query.answer(config.MSG['review']['no_review'])
        return
    await print_review_message(query.from_user)


async def start_review(user: types.User, house: str = None, floor: str = None):
    """Set floor to "-" to search only absent floors."""
    info = await get_user(user)
    if house is not None:
        pois = await db.get_poi_by_house(house, floor)
        if info.location:
            ref = info.location
        else:
            if len(pois) > 14:
                info.review_ctx = (house, floor)
                await bot.send_message(user.id, config.MSG['review']['too_many'])
                return
            ref = pois[0].location
        pois.sort(key=lambda p: ref.distance(p.location))
    else:
        pois = await db.get_poi_around(info.location, count=30, floor=floor)
    # Sort by "not reviewed in the past ten hours"
    ages = await db.get_poi_ages([p.id for p in pois])
    pois.sort(key=lambda p: 0 if ages[p.id] > 10 else 1)
    # Start review and print the review panel
    info.review = [[p.id, None] for p in pois[:14]]
    info.review_ctx = (house, floor)
    await print_review_message(user)


async def make_review_keyboard(pois: List[POI], edit: bool = False):
    ages = await db.get_poi_ages([p.id for p in pois])
    width = 3 if len(pois) in (3, 4, 7) else 4
    kbd = types.InlineKeyboardMarkup(row_width=width)
    for i, poi in enumerate(pois, 1):
        if ages[poi.id] <= 50:
            fresh = '✅'
        else:
            fresh = '' if not edit else '📝'
        data = POI_EDIT_CB.new(id=poi.id, d='1') if edit else REVIEW_CB.new(id=poi.id)
        kbd.insert(types.InlineKeyboardButton(
            f'{i} {fresh}{poi.name}', callback_data=data))
    if edit:
        kbd.insert(types.InlineKeyboardButton('🗒️', callback_data=EDIT_CB.new('check')))
    else:
        kbd.insert(types.InlineKeyboardButton('📝', callback_data=EDIT_CB.new('edit')))
    kbd.insert(types.InlineKeyboardButton('✖️', callback_data='stop_review'))
    return kbd


async def print_review_message(user: types.User, pois: List[POI] = None):
    if not pois:
        info = await get_user(user)
        if not info.review:
            return
        pois = await db.get_poi_by_ids([r[0] for r in info.review])
    OH_REPL = {'Mo': 'пн', 'Tu': 'вт', 'We': 'ср', 'Th': 'чт',
               'Fr': 'пт', 'Sa': 'сб', 'Su': 'вс'}
    content = config.MSG['review']['list'] + '\n'
    if len(pois) == 14:
        content += '\n' + config.MSG['review']['incomplete'] + '\n'
    for i, poi in enumerate(pois, 1):
        p_start = f'\n{i}. «{poi.name}»'
        p_icons = ''
        p_absent = ''
        if poi.has_wifi is not None:
            p_icons += '📶' if poi.has_wifi else '📵'
        if poi.accepts_cards is not None:
            p_icons += '💳' if poi.accepts_cards else '💰'
        if not poi.phones:
            p_absent += '📞'
        if not poi.links:
            p_absent += '🌐'
        if not poi.address_part:
            p_absent += '🚪'
        if not poi.keywords:
            p_absent += '🔡'
        if not poi.photo_out:
            p_absent += '🌄'
        if not poi.photo_in:
            p_absent += '📸'
        if p_absent:
            p_absent = config.MSG['review']['absent'] + ' ' + p_absent
        if not poi.hours_src:
            p_oh = config.MSG['review']['no_hours']
        else:
            p_oh = poi.hours_src.replace(':00', '')
            for k, v in OH_REPL.items():
                p_oh = p_oh.replace(k, v)
        content += ' '.join([p for p in (p_start, p_icons, p_absent, p_oh) if p])
    kbd = await make_review_keyboard(pois)
    await bot.send_message(user.id, content, reply_markup=kbd)


@dp.callback_query_handler(REVIEW_CB.filter(), state='*')
async def update_review(query: types.CallbackQuery, callback_data: Dict[str, str]):
    info = await get_user(query.from_user)
    if not info.review:
        await query.answer(config.MSG['review']['no_review'])
        return

    poi_id = int(callback_data['id'])
    review_record = [r for r in info.review if r[0] == poi_id]
    if not review_record:
        await query.answer(config.MSG['review']['no_record'])
        return

    if review_record[0][1]:
        # We have old updated, revert to it
        await db.set_updated(poi_id, review_record[0][1])
        review_record[0][1] = None
    else:
        review_record[0][1] = await db.set_updated(poi_id)

    # Update keyboard
    pois = await db.get_poi_by_ids([r[0] for r in info.review])
    kbd = await make_review_keyboard(pois)
    await bot.edit_message_reply_markup(
        query.from_user.id, query.message.message_id, reply_markup=kbd)


@dp.callback_query_handler(EDIT_CB.filter(), state='*')
async def edit_mode(query: types.CallbackQuery, callback_data: Dict[str, str]):
    info = await get_user(query.from_user)
    if not info.review:
        await query.answer(config.MSG['review']['no_review'])
        return
    pois = await db.get_poi_by_ids([r[0] for r in info.review])
    kbd = await make_review_keyboard(pois, callback_data['mode'] == 'edit')
    await bot.edit_message_reply_markup(
        query.from_user.id, query.message.message_id, reply_markup=kbd)


@dp.message_handler(content_types=types.ContentType.LOCATION, state='*')
async def set_loc(message):
    info = await get_user(message.from_user)
    if not info.review or not info.review_ctx:
        raise SkipHandler
    # Save location and continue the review
    location = Location(message.location.longitude, message.location.latitude)
    info.location = location
    await start_review(message.from_user, *info.review_ctx)
