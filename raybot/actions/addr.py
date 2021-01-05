from raybot import config
from raybot.model import db
from raybot.actions.poi import print_poi_by_key
from raybot.bot import bot
from raybot.util import has_keyword
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from typing import List


HOUSE_CB = CallbackData('house', 'id')


class AddrState(StatesGroup):
    street = State()
    house = State()


async def test_address(message: types.Message, tokens: List[str], state: FSMContext) -> bool:
    for street in config.ADDR['streets']:
        if has_keyword(tokens[:1], street['keywords']):
            if len(tokens) == 1:
                await AddrState.street.set()
                await state.set_data({'street': street['name']})
                await print_street(message, street)
            else:
                await handle_building(message.from_user, street, tokens[1:], state)
            return True

        # Check buildings like "mst6"
        for house in street['buildings']:
            if has_keyword(tokens, street['keywords'], str(house)):
                await handle_building(message.from_user, street, [house] + tokens[1:], state)
                return True
    return False


async def print_street(message, street):
    buildings = street['buildings']
    kbd = types.InlineKeyboardMarkup(row_width=5 if 1 <= len(buildings) % 6 <= 2 else 6)
    for house, hid in buildings.items():
        kbd.insert(types.InlineKeyboardButton(house, callback_data=HOUSE_CB.new(id=hid)))
    await message.answer(f"Выберите дом по {street['name']}:", reply_markup=kbd)


async def handle_building(user: types.User, street, tokens, state, hid=None):
    if not hid:
        hid = street['buildings'].get(tokens[0])
    if hid:
        await AddrState.house.set()
        await state.set_data({'house': hid})
        if len(tokens) > 1:
            await print_apartment(user, hid, tokens[1])
        else:
            await print_poi_by_key(user, hid, buttons=False,
                                   comment='Пришлите номер квартиры, если хотите.')
    else:
        await AddrState.street.set()
        await state.set_data({'street': street['name']})
        await bot.send_message(user.id, f'Нет дома {tokens[-1]} по {street["name"]}')
    return hid


async def print_apartment(user: types.User, building: str, apartment):
    try:
        apartment = int(apartment)
    except ValueError:
        await bot.send_message(
            user.id,
            f'Номер квартиры f{apartment} должен быть числом. Вот карточка для дома:')
        await print_poi_by_key(user, building, buttons=False)
        return

    possible_entrances = [e for e in config.ADDR['apartments'] if e.startswith(building)]
    entrances = [building] + await db.get_entrances(building, possible_entrances)
    floor = None
    entrance = None
    entrance_first = None
    for e in entrances:
        e_apts = config.ADDR['apartments'].get(e)
        if e_apts is None:
            continue
        elif isinstance(e_apts, list):
            if apartment >= e_apts[0]:
                if entrance is None or entrance_first < e_apts[0]:
                    entrance = e
                    entrance_first = e_apts[0]
                    floor = len([a for a in e_apts if a <= apartment])
        elif apartment >= e_apts:
            if entrance is None or entrance_first < e_apts:
                entrance = e
                entrance_first = e_apts
                floor = None

    if entrance is None:
        await print_poi_by_key(user, building, buttons=False)
    elif floor is None:
        await print_poi_by_key(user, entrance, f'Квартира {apartment}.', buttons=False)
    else:
        comment = f'Квартира {apartment} на {floor} этаже.'
        await print_poi_by_key(user, entrance, comment, buttons=False)
