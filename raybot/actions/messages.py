from raybot import config
from raybot.bot import bot
from raybot.util import get_user
from raybot.model import db
from asyncio import sleep
from aiogram import types


async def broadcast(message: types.Message):
    mods = [config.ADMIN] + (await db.get_role_users('moderator'))
    for user_id in mods:
        await bot.send_message(user_id, config.MSG['do_reply'])
        await message.forward(user_id)
        await sleep(0.5)


async def broadcast_str(message: str, except_id: int = None):
    mods = [config.ADMIN] + (await db.get_role_users('moderator'))
    for user_id in mods:
        if user_id != except_id:
            await bot.send_message(user_id, message)
            await sleep(0.5)


async def process_reply(message: types.Message):
    info = await get_user(message.from_user)
    to = await get_user(message.reply_to_message.forward_from)
    if info.is_moderator():
        # Notify other moderators that it has been replied
        # TODO: can we do it just once per user?
        await broadcast_str(f'Отправлен ответ на сообщение {to.name}',
                            info.id, disable_notification=True)
    await bot.send_message(to.id, config.MSG['do_reply'])
    await message.forward(to.id)
