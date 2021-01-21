from raybot.actions.poi import (
    PoiState,
    print_poi, print_poi_list, make_poi_keyboard,
    POI_LIST_CB, POI_FULL_CB, POI_LOCATION_CB,
    POI_HOUSE_CB, POI_SIMILAR_CB, POI_STAR_CB
)
from raybot.model import db
from raybot.bot import dp, bot
from raybot.util import split_tokens, unpack_ids, save_location
from raybot import config
from typing import Dict
from aiogram import types
from aiogram.dispatcher import FSMContext, filters


@dp.callback_query_handler(POI_FULL_CB.filter(), state='*')
async def all_pois(query: types.CallbackQuery, callback_data: Dict[str, str],
                   state: FSMContext):
    cur_state = None if not state else await state.get_state()
    if cur_state == PoiState.poi_list.state:
        data = await state.get_data()
        txt = data['query']
        pois = await db.get_poi_by_ids(data['poi'])
    else:
        txt = callback_data['query']
        ids = callback_data['ids']
        if len(ids) < 2:
            tokens = split_tokens(txt)
            pois = await db.find_poi(' '.join(tokens))
        else:
            pois = await db.get_poi_by_ids(unpack_ids(ids))
    await print_poi_list(query.from_user, txt, pois, True)


@dp.callback_query_handler(POI_LIST_CB.filter(), state='*')
async def poi_from_list(query: types.CallbackQuery, callback_data: Dict[str, str],
                        state: FSMContext):
    poi = await db.get_poi_by_id(int(callback_data['id']))
    if not poi:
        await query.answer('Что-то пошло не так — повторите запрос, пожалуйста.')
    else:
        await PoiState.poi.set()
        await state.set_data({'poi': poi.id})
        await print_poi(query.from_user, poi)


@dp.callback_query_handler(POI_LOCATION_CB.filter(), state='*')
async def poi_location(query: types.CallbackQuery, callback_data: Dict[str, str]):
    poi = await db.get_poi_by_id(int(callback_data['id']))
    await bot.send_location(query.from_user.id, latitude=poi.location.lat,
                            longitude=poi.location.lon)


@dp.callback_query_handler(POI_STAR_CB.filter(), state='*')
async def star_poi(query: types.CallbackQuery, callback_data: Dict[str, str]):
    user = query.from_user
    poi = await db.get_poi_by_id(int(callback_data['id']))
    action = callback_data['action']
    if action == 'set':
        await db.set_star(user.id, poi.id, True)
    elif action == 'del':
        await db.set_star(user.id, poi.id, False)
    kbd = await make_poi_keyboard(user, poi)
    await bot.edit_message_reply_markup(
        user.id, query.message.message_id, reply_markup=kbd)


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['poi([0-9]+)']), state='*')
async def print_specific_poi(message: types.Message, regexp_command, state: FSMContext):
    poi = await db.get_poi_by_id(int(regexp_command.group(1)))
    if not poi:
        await message.answer('Нет заведения с таким номером.')
    else:
        await PoiState.poi.set()
        await state.set_data({'poi': poi.id})
        await print_poi(message.from_user, poi)


@dp.callback_query_handler(POI_HOUSE_CB.filter(), state='*')
async def in_house_callback(query: types.CallbackQuery, callback_data: Dict[str, str],
                            state: FSMContext):
    house = callback_data['house']
    floor = callback_data['floor']
    data = await db.get_poi_by_key(house)
    pois = await db.get_poi_by_house(house, None if floor == '-' else floor)
    if floor == '-' and len(pois) > 9:
        floors = await db.get_floors_by_house(house)
        if len(floors) >= 2 and None not in floors:
            # We have floors - add another selection
            kbd = types.InlineKeyboardMarkup(row_width=3)
            for ifloor in floors:
                kbd.insert(types.InlineKeyboardButton(
                    ifloor, callback_data=POI_HOUSE_CB.new(house=house, floor=ifloor)))
            await bot.send_message(query.from_user.id, config.MSG['choose_floor'],
                                   reply_markup=kbd)
            return

    if not pois:
        await query.answer('Заведений нет')
    elif len(pois) == 1:
        await PoiState.poi.set()
        await state.set_data({'poi': pois[0].id})
        await print_poi(query.from_user, pois[0])
    else:
        await PoiState.poi_list.set()
        await state.set_data({'query': query, 'poi': [p.id for p in pois]})
        await print_poi_list(query.from_user, data.name, pois, True)


@dp.callback_query_handler(POI_SIMILAR_CB.filter(), state='*')
async def simlar_poi(query: types.CallbackQuery, callback_data: Dict[str, str],
                     state: FSMContext):
    poi = await db.get_poi_by_id(int(callback_data['id']))
    if not poi or not poi.tag:
        await query.answer('Что-то пошло не так — повторите запрос, пожалуйста.')
    else:
        pois = await db.get_poi_by_tag(poi.tag)
        if len(pois) == 1:
            await query.answer(config.MSG['no_similar'])
        else:
            tag_names = config.TAGS['tags'].get(poi.tag)
            pquery = poi.tag if not tag_names else tag_names[0]
            await PoiState.poi_list.set()
            await state.set_data({'query': pquery, 'poi': [p.id for p in pois]})
            await print_poi_list(query.from_user, pquery, pois, relative_to=poi.location)


@dp.message_handler(commands='last', state='*')
async def print_last(message: types.Message, state: FSMContext):
    pois = await db.get_last_poi(6)
    await PoiState.poi_list.set()
    await state.set_data({'query': 'last', 'poi': [p.id for p in pois]})
    await print_poi_list(message.from_user, 'last', pois, shuffle=False)


@dp.message_handler(commands='random', state='*')
async def print_random(message: types.Message, state: FSMContext):
    pois = await db.get_random_poi(6)
    await PoiState.poi_list.set()
    await state.set_data({'query': 'random', 'poi': [p.id for p in pois]})
    await print_poi_list(message.from_user, 'random', pois, shuffle=False)


@dp.message_handler(commands='my', state='*')
async def print_starred(message: types.Message, state: FSMContext):
    pois = await db.get_starred_poi(message.from_user.id)
    if not pois:
        await message.answer(config.MSG['no_starred'])
        return
    await PoiState.poi_list.set()
    await state.set_data({'query': 'my', 'poi': [p.id for p in pois]})
    await print_poi_list(message.from_user, 'my', pois)


@dp.message_handler(commands='popular', state='*')
async def print_popular(message: types.Message, state: FSMContext):
    pois = await db.get_popular_poi(9)
    if not pois:
        await message.answer(config.MSG['no_popular'])
        return
    await PoiState.poi_list.set()
    await state.set_data({'query': 'popular', 'poi': [p.id for p in pois]})
    await print_poi_list(message.from_user, 'popular', pois)


@dp.message_handler(content_types=types.ContentType.LOCATION, state=PoiState.poi_list)
async def set_loc(message: types.Message, state: FSMContext):
    await save_location(message)
    data = await state.get_data()
    pois = await db.get_poi_by_ids(data['poi'])
    await print_poi_list(message.from_user, data['query'], pois)
