from raybot import config
from raybot.model import db, POI
from raybot.bot import bot
from raybot.util import h, get_user, get_map, pack_ids
import re
import os
import random
from typing import List
from datetime import datetime
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher.filters.state import State, StatesGroup


HTML = types.ParseMode.HTML
POI_LIST_CB = CallbackData('poi', 'id')
POI_LOCATION_CB = CallbackData('poiloc', 'id')
POI_EDIT_CB = CallbackData('poiedit', 'id')
POI_FULL_CB = CallbackData('plst', 'query', 'ids')
POI_HOUSE_CB = CallbackData('poih', 'house')


class PoiState(StatesGroup):
    poi = State()
    poi_list = State()


async def print_poi_list(user: types.User, query: str, pois: List[POI],
                         full: bool = False, shuffle: bool = True):
    def uncap(s: str) -> str:
        if not s:
            return s
        return s[0].lower() + s[1:]

    max_buttons = 9 if not full else 20
    location = (await get_user(user)).location
    if shuffle:
        if location:
            pois.sort(key=lambda p: location.distance(p.location))
        else:
            random.shuffle(pois)
        pois.sort(key=lambda p: not p.hours or p.hours.is_open())
    total_count = len(pois)
    all_ids = pack_ids([p.id for p in pois])
    if total_count > max_buttons:
        pois = pois[:max_buttons if full else max_buttons - 1]

    content = config.MSG['poi_list'].replace('%s', query) + '\n'
    for i, poi in enumerate(pois, 1):
        if poi.description:
            content += h(f'\n{i}. {poi.name} — {uncap(poi.description)}')
        else:
            content += h(f'\n{i}. {poi.name}')
    if total_count > max_buttons:
        if not full:
            content += (f'\n\nСписок неполный, нажмите последнюю кнопку '
                        'для запроса всех {total_count}.')
        else:
            content += f'\n\nСписок неполный, но все {total_count} никак не поместятся.'

    if len(pois) == 4:
        kbd_width = 2
    else:
        kbd_width = 4 if len(pois) > 9 else 3
    kbd = types.InlineKeyboardMarkup(row_width=kbd_width)
    for i, poi in enumerate(pois, 1):
        b_title = f'{i} {poi.name}'
        kbd.insert(types.InlineKeyboardButton(
            b_title, callback_data=POI_LIST_CB.new(id=poi.id)))
    if total_count > max_buttons and not full:
        try:
            callback_data = POI_FULL_CB.new(query=query[:55], ids=all_ids)
        except ValueError:
            # Too long
            callback_data = POI_FULL_CB.new(query=query[:55], ids='-')
        kbd.insert(types.InlineKeyboardButton(
            f'Все {total_count}', callback_data=callback_data))

    map_file = get_map([poi.location for poi in pois], ref=location)
    if not map_file:
        await bot.send_message(user.id, content, parse_mode=HTML, reply_markup=kbd)
    else:
        await bot.send_photo(
            user.id, types.InputFile(map_file.name),
            caption=content, parse_mode=HTML,
            reply_markup=kbd)
        map_file.close()


def relative_day(next_day):
    days = (next_day.date() - datetime.now().date()).days
    if days < 1:
        opens_day = 'утром'
    if days == 1:
        opens_day = 'завтра'
    else:
        DOW = ['в понедельник', 'во вторник', 'в среду', 'в четверг',
               'в пятницу', 'в субботу', 'в воскресенье']
        opens_day = DOW[next_day.weekday()]
    return opens_day


def describe_poi(poi: POI):
    result = [f'<b>{h(poi.name)}</b>']
    if poi.description:
        result.append(h(poi.description))

    part2 = []
    if poi.hours:
        if poi.hours.is_24_7:
            part2.append('🌞 Открыто круглосуточно.')
        elif poi.hours.is_open():
            closes = poi.hours.next_change()
            open_now = f'☀️ Открыто сегодня до {closes.strftime("%H:%M")}.'
            if (closes - datetime.now()).seconds <= 3600 * 2:
                opens = poi.hours.next_change(closes)
                open_now += (f' {relative_day(opens).capitalize()} работает '
                             f'с {opens.strftime("%H:%M").lstrip("0")}.')
            part2.append(open_now)
        else:
            opens = poi.hours.next_change()
            part2.append(f'🌒 Закрыто. Откроется {relative_day(opens)} '
                         f'в {opens.strftime("%H:%M").lstrip("0")}.')
    if poi.links and len(poi.links) > 1:
        part2.append('🌐 Ссылки: {}.'.format(', '.join(
            ['<a href="{}">{}</a>'.format(h(link[1]), h(link[0]))
             for link in poi.links]
        )))
    if poi.address:
        part2.append(f'🏠 {poi.address}.')
    if poi.has_wifi is True:
        part2.append('📶 Есть бесплатный Wi-Fi.')
    if poi.accepts_cards is True:
        part2.append('💳 Можно оплатить картой.')
    elif poi.accepts_cards is False:
        part2.append('💰 Оплата только наличными.')
    if poi.phones:
        part2.append('📞 {}.'.format(', '.join(
            [re.sub(r'[^0-9+]', '', phone) for phone in poi.phones]
        )))
    if part2:
        result.append('')
        result.extend(part2)

    if poi.comment:
        result.append('')
        result.append(poi.comment)
    return '\n'.join(result)


def make_poi_keyboard(poi: POI):
    kbd = types.InlineKeyboardMarkup(row_width=2)
    if poi.links:
        link_dict = dict(poi.links)
        if config.MSG['default_link'] in link_dict:
            link_title = 'Открыть сайт'
            link = link_dict[config.MSG['default_link']]
        else:
            link_title = poi.links[0][0]
            link = poi.links[0][1]
        kbd.insert(types.InlineKeyboardButton(link_title, url=link))
    kbd.insert(types.InlineKeyboardButton(
        '📍 Координаты', callback_data=POI_LOCATION_CB.new(id=poi.id)))
    kbd.insert(types.InlineKeyboardButton(
        '📝 Поправить', callback_data=POI_EDIT_CB.new(id=poi.id)))
    return kbd


async def make_house_keyboard(poi: POI):
    if not poi.key:
        return None
    pois = await db.get_poi_by_house(poi.key)
    if not pois:
        return None

    return types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(
            'Заведения в этом доме', callback_data=POI_HOUSE_CB.new(house=poi.key))
    )


async def print_poi(user: types.User, poi: POI, comment: str = None, buttons: bool = True):
    chat_id = user.id
    content = describe_poi(poi)
    if comment:
        content += '\n\n' + h(comment)

    # Prepare photos
    photos = []
    photo_names = []
    for photo in [poi.photo_in, poi.photo_out]:
        if photo:
            path = os.path.join(config.PHOTOS, photo + '.jpg')
            if os.path.exists(path):
                file_ids = await db.find_file_ids({photo: os.path.getsize(path)})
                if photo in file_ids:
                    photos.append(file_ids[photo])
                    photo_names.append(None)
                else:
                    photos.append(types.InputFile(path))
                    photo_names.append([photo, os.path.getsize(path)])

    # Generate a map
    location = (await get_user(user)).location
    map_file = get_map([poi.location], location)
    if map_file:
        photos.append(types.InputFile(map_file.name))
        photo_names.append(None)

    # Prepare the inline keyboard
    if poi.tag == 'building':
        kbd = await make_house_keyboard(poi)
    else:
        kbd = None if not buttons else make_poi_keyboard(poi)

    # Send the message
    if not photos:
        msg = await bot.send_message(chat_id, content, parse_mode=HTML,
                                     reply_markup=kbd, disable_web_page_preview=True)
    elif len(photos) == 1:
        msg = await bot.send_photo(chat_id, photos[0], caption=content, parse_mode=HTML,
                                   reply_markup=kbd)
    else:
        media = types.MediaGroup()
        for i, photo in enumerate(photos):
            if not kbd and i == 0:
                photo = types.input_media.InputMediaPhoto(
                    photo, caption=content, parse_mode=HTML)
            media.attach_photo(photo)
        if kbd:
            msg = await bot.send_media_group(chat_id, media=media)
            await bot.send_message(chat_id, content, parse_mode=HTML,
                                   reply_markup=kbd, disable_web_page_preview=True)
        else:
            msg = await bot.send_media_group(chat_id, media=media)
    if map_file:
        map_file.close()

    # Store file_ids for new photos
    if isinstance(msg, list):
        file_ids = [m.photo[-1].file_id for m in msg if m.photo]
    else:
        file_ids = [msg.photo[-1]] if msg.photo else []
    for i, file_id in enumerate(file_ids):
        if photo_names[i]:
            await db.store_file_id(photo_names[i][0], photo_names[i][1], file_id)


async def print_poi_by_key(user: types.User, poi_id: str, comment: str = None,
                           buttons: bool = True):
    poi = await db.get_poi_by_key(poi_id)
    if not poi:
        await bot.send_message(user.id, f'Cannot find POI with id {poi_id}')
    else:
        await print_poi(user, poi, comment=comment, buttons=buttons)
