from raybot.actions.poi import (
    PoiState,
    print_poi, print_poi_list,
    POI_LIST_CB, POI_FULL_CB, POI_LOCATION_CB
)
from raybot.model import db
from raybot.bot import dp, bot
from raybot.util import split_tokens
from typing import Dict
from aiogram import types
from aiogram.dispatcher import FSMContext, filters


@dp.callback_query_handler(POI_FULL_CB.filter(), state='*')
async def all_pois(query: types.CallbackQuery, callback_data: Dict[str, str]):
    txt = callback_data['query']
    tokens = split_tokens(txt)
    pois = await db.find_poi(' '.join(tokens))
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


@dp.message_handler(filters.RegexpCommandsFilter(regexp_commands=['poi([0-9]+)']), state='*')
async def print_specific_poi(message: types.Message, regexp_command, state: FSMContext):
    poi = await db.get_poi_by_id(int(regexp_command.group(1)))
    if not poi:
        await message.answer('Нет заведения с таким номером.')
    else:
        await PoiState.poi.set()
        await state.set_data({'poi': poi.id})
        await print_poi(message.from_user, poi)
