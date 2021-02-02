from raybot.bot import bot, dp
from raybot.util import get_user, tr
from raybot.actions.messages import broadcast, process_reply
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.handler import SkipHandler


class MsgState(StatesGroup):
    sending = State()


@dp.message_handler(commands='msg', state='*')
async def message_info(message: types.Message):
    info = await get_user(message.from_user)
    if info.is_moderator():
        await message.answer(tr('message_self'))
        return
    await message.answer(tr('message'))
    await MsgState.sending.set()


@dp.callback_query_handler(text='missing_mod', state='*')
async def message_info_callback(query: types.CallbackQuery):
    info = await get_user(query.from_user)
    if info.is_moderator():
        await query.answer(tr('message_self'))
        return
    await bot.send_message(query.from_user.id, tr('message'))
    await MsgState.sending.set()


@dp.message_handler(state=MsgState.sending)
async def send_message(message: types.Message, state: FSMContext):
    await broadcast(message)
    await state.finish()


@dp.message_handler(content_types=[
    types.ContentType.STICKER, types.ContentType.PHOTO,
    types.ContentType.VIDEO, types.ContentType.VIDEO_NOTE,
    types.ContentType.VOICE, types.ContentType.LOCATION,
    types.ContentType.CONTACT, types.ContentType.TEXT
], state='*')
async def process_reply_type(message: types.Message, state: FSMContext):
    if message.reply_to_message and message.reply_to_message.is_forward():
        await process_reply(message)
    else:
        raise SkipHandler
