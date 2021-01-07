from raybot import config
from raybot.model import db
from raybot.bot import bot, dp
from raybot.util import h, HTML, get_user
from raybot.actions.poi import print_poi, POI_EDIT_CB
from typing import Dict
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import SkipHandler


MSG_CB = CallbackData('qmsg', 'action', 'id')


@dp.message_handler(commands='queue', state='*')
async def print_queue(message: types.Message, state: FSMContext):
    allowed = await print_next_queued(message.from_user)
    if not allowed:
        raise SkipHandler


async def print_next_queued(user: types.User):
    info = await get_user(user)
    if info.id != config.ADMIN and 'moderator' not in info.roles:
        return False

    queue = await db.get_queue(1)
    if not queue:
        await bot.send_message(user.id, config.MSG['queue']['empty'])
        return True

    q = queue[0]
    poi = await db.get_poi_by_id(q.poi_id)
    if not poi:
        await bot.send_message('POI пропал, странно. Удаляю запись.')
        await db.delete_queue(q)
        return True

    if q.field == 'message':
        content = config.MSG['queue']['message'].format(
            user=h(q.user_name), name=h(poi.name))
        content += f'\n\n{h(q.new_value)}'
    else:
        content = config.MSG['queue']['field'].format(
            user=h(q.user_name), name=h(poi.name), field=q.field)
        content += '\n'
        vold = '<i>ничего</i>' if q.old_value is None else h(q.old_value)
        vnew = '<i>ничего</i>' if q.new_value is None else h(q.new_value)
        content += f'\n<b>Сейчас:</b> {vold}'
        content += f'\n<b>Будет:</b> {vnew}'

    kbd = types.InlineKeyboardMarkup(row_width=3)
    if q.field != 'message':
        kbd.insert(types.InlineKeyboardButton(
            config.MSG['queue']['look'],
            callback_data=MSG_CB.new(action='look', id=str(q.id)))
        )
        kbd.insert(types.InlineKeyboardButton(
            config.MSG['queue']['apply'],
            callback_data=MSG_CB.new(action='apply', id=str(q.id)))
        )
    else:
        kbd.insert(types.InlineKeyboardButton(
            '📝 Поправить', callback_data=POI_EDIT_CB.new(id=q.poi_id)))
    kbd.insert(types.InlineKeyboardButton(
        config.MSG['queue']['delete'],
        callback_data=MSG_CB.new(action='del', id=str(q.id)))
    )

    await bot.send_message(user.id, content, parse_mode=HTML, reply_markup=kbd)
    return True


@dp.callback_query_handler(MSG_CB.filter(), state='*')
async def process_queue(query: types.CallbackQuery, callback_data: Dict[str, str]):
    action = callback_data['action']
    q = await db.get_queue_msg(int(callback_data['id']))
    if not q:
        await query.answer('Пропало сообщение с таким номером')
        return

    if action == 'del':
        await db.delete_queue(q)
        await query.answer(config.MSG['queue']['deleted'])
    elif action == 'apply':
        await db.apply_queue(query.from_user.id, q)
        await query.answer(config.MSG['queue']['applied'])
    elif action == 'look':
        poi = await db.get_poi_by_id(q.poi_id)
        if not poi:
            await query.answer('POI пропал, удаляю запись')
            await db.delete_queue(q)
        else:
            await print_poi(query.from_user, poi, buttons=False)
            return
    else:
        await query.answer(f'Что за действие в queue, "{action}"?')

    await print_next_queued(query.from_user)
