from raybot import config
from raybot.bot import dp
from raybot.util import split_tokens
from raybot.actions.addr import HOUSE_CB, handle_building, print_apartment, AddrState
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import SkipHandler
from typing import Dict


@dp.message_handler(state=AddrState.street)
async def process_building(message: types.Message, state: FSMContext):
    tokens = split_tokens(message.text, False)
    if not tokens:
        return
    street_name = (await state.get_data())['street']
    streets = [s for s in config.ADDR['streets'] if s['name'] == street_name]
    if streets:
        street = streets[0]
        hid = street['buildings'].get(tokens[0])
        if hid:
            await handle_building(message.from_user, street, tokens, state)
            return
    # If we fail, process it as without context
    raise SkipHandler


@dp.message_handler(state=AddrState.house)
async def process_house(message: types.Message, state: FSMContext):
    try:
        apartment = int(message.text.strip())
    except ValueError:
        raise SkipHandler
    await print_apartment(message.from_user, (await state.get_data())['house'], apartment)


@dp.callback_query_handler(HOUSE_CB.filter(), state='*')
async def callback_house(query: types.CallbackQuery, callback_data: Dict[str, str],
                         state: FSMContext):
    hid = callback_data['id']
    await handle_building(query.from_user, None, [query.data], state, hid=hid)
