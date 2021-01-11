import os
from raybot import config
from raybot.model import db
from raybot.bot import bot, dp
from raybot.util import h, HTML, get_user, forget_user
from raybot.actions.poi import print_poi, POI_EDIT_CB, print_poi_list, PoiState
from typing import Dict
from aiogram import types
from aiogram.utils.callback_data import CallbackData
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.handler import SkipHandler
from aiogram.dispatcher.filters.state import State, StatesGroup


MSG_CB = CallbackData('qmsg', 'action', 'id')
POI_VALIDATE_CB = CallbackData('qpoi', 'id')
MOD_REMOVE_CB = CallbackData('modrm', 'id')


class ModState(StatesGroup):
    mod = State()


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
        await bot.send_message(user.id, config.MSG['queue']['empty'])
        return True
    await print_poi(user, poi)

    content = config.MSG['queue']['new_poi']
    kbd = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton(
            config.MSG['queue']['apply'],
            callback_data=POI_VALIDATE_CB.new(id=str(poi.id))
        )
    )
    await bot.send_message(user.id, content, reply_markup=kbd)


@dp.callback_query_handler(POI_VALIDATE_CB.filter(), state='*')
async def validate_poi(query: types.CallbackQuery, callback_data: Dict[str, str]):
    poi = await db.get_poi_by_id(int(callback_data['id']))
    if not poi:
        await query.answer('POI пропал, странно.')
        return
    await db.validate_poi(poi.id)
    await query.answer('Заведение проверено.')
    await print_next_queued(query.from_user)


async def print_next_queued(user: types.User):
    info = await get_user(user)
    if not info.is_moderator():
        return False

    queue = await db.get_queue(1)
    if not queue:
        # await bot.send_message(user.id, config.MSG['queue']['empty'])
        return await print_next_added(user)
        return True

    q = queue[0]
    poi = await db.get_poi_by_id(q.poi_id)
    if not poi:
        await bot.send_message(user.id, 'POI пропал, странно. Удаляю запись.')
        await db.delete_queue(q)
        return True

    photo = None
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
        if q.field in ('photo_in', 'photo_out') and q.new_value:
            photo = os.path.join(config.PHOTOS, q.new_value + '.jpg')
            if not os.path.exists(photo):
                photo = None

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


@dp.message_handler(content_types=types.ContentType.ANY, state=ModState.mod)
async def add_mod(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN:
        raise SkipHandler
    if not message.is_forward():
        await message.answer('Форвардните пост от человека, чтобы сделать его модератором.')
        return
    await state.finish()
    me = await get_user(message.from_user)
    new_user = await get_user(message.forward_from)
    if new_user.is_moderator():
        await message.answer('Он/она уже модератор.')
        return
    await db.add_user_to_role(new_user, 'moderator', me)
    forget_user(new_user.id)
    await message.answer(f'Пользователь {new_user.name} теперь модератор.')
    await bot.send_message(new_user.id, 'Вы теперь модератор. Попробуйте /queue')


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
        await bot.send_message(query.from_user.id, 'Пользователь больше не модератор.')
    else:
        await query.answer('Ок')


@dp.message_handler(commands='mod', state='*')
async def manage_mods(message: types.Message, state: FSMContext):
    if message.from_user.id != config.ADMIN:
        raise SkipHandler
    await state.finish()
    mods = await db.get_role_users('moderator')
    kbd = types.InlineKeyboardMarkup()
    if not mods:
        content = ('Нет ни одного модератора. Форвардните пост от человека, '
                   'чтобы сделать её/его модератором.')
    else:
        content = 'Список модераторов:\n\n'
        for i, mod in enumerate(mods, 1):
            content += f'{i}. {mod.name}\n'
            kbd.insert(types.InlineKeyboardButton(
                f'❌ {i} {mod.name}', callback_data=MOD_REMOVE_CB.new(id=str(mod.id))))
        content += ('\nНажмите кнопку, чтобы удалить человека из модераторов, либо '
                    'форвардните пост от нового человека, чтобы сделать её/его модератором.')
    kbd.insert(types.InlineKeyboardButton(
        'Оставить как есть', callback_data=MOD_REMOVE_CB.new(id='-')))
    await message.answer(content, reply_markup=kbd)
    await ModState.mod.set()


@dp.message_handler(commands='deleted', state='*')
async def print_deleted(message: types.Message, state: FSMContext):
    pois = await db.get_last_deleted(6)
    if not pois:
        await message.answer('Ничего не удалено.')
        return
    await PoiState.poi_list.set()
    await state.set_data({'query': 'deleted', 'poi': [p.id for p in pois]})
    await print_poi_list(message.from_user, 'last', pois, shuffle=False)
