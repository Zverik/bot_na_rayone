from raybot import config
from raybot.model import db, UserInfo, Location
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import TelegramAPIError, MessageToDeleteNotFound
from typing import List, Union, Dict
import re
import time
import base64
import struct


userdata = {}
SKIP_TOKENS = set(config.RESP['skip'])
# Markdown requires too much escaping, so we're using HTML
HTML = types.ParseMode.HTML
PRUNE_TIMEOUT = 10  # minutes


def reverse_synonims():
    result = {}
    for k, v in config.RESP['synonims'].items():
        for s in v:
            result[s] = k
    # Add emoji from tags
    for k, v in config.TAGS['emoji'].items():
        if k != 'default' and v not in result:
            kw = config.TAGS['tags'].get(k)
            if kw:
                result[v] = kw[0]
    return result


SYNONIMS = reverse_synonims()


def has_keyword(token, keywords, kwsuffix=''):
    for k in keywords:
        if token == k + kwsuffix:
            return True
    return False


async def get_user(user: types.User):
    info = userdata.get(user.id)
    if not info:
        info = UserInfo(user)
        info.roles = await db.get_roles(user.id)
        userdata[user.id] = info
    info.last_access = time.time()
    return info


async def save_location(message: types.Message):
    location = Location(message.location.longitude, message.location.latitude)
    info = await get_user(message.from_user)
    info.location = location


def prune_users(except_id: int) -> List[int]:
    pruned = []
    for user_id in list(userdata.keys()):
        if user_id != except_id:
            data = userdata.get(user_id)
            if data and time.time() - data.last_access > PRUNE_TIMEOUT * 60:
                pruned.append(user_id)
                del userdata[user_id]
    return pruned


def forget_user(user_id: int):
    if user_id in userdata:
        del userdata[user_id]


def split_tokens(message, process=True):
    s = message.strip().lower().replace('ё', 'е')
    tokens = re.split(r'[\s,.+=!@#$%^&*()\'"«»<>/?`~|_-]+', s)
    if process:
        tokens = [SYNONIMS.get(t, t) for t in tokens
                  if len(t) > 0 and t not in SKIP_TOKENS]
    else:
        tokens = [t for t in tokens if len(t) > 0]
    return tokens


def h(s: str) -> str:
    if not s:
        return s
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def trn(opts: Dict[str, str], n: int) -> str:
    if not n:
        k = '5'
    elif n % 100 == 1 and n != 11:
        k = '1'
    elif n % 100 in (2, 3, 4) and n not in (12, 13, 14):
        k = '2'
    else:
        k = '5'
    return opts.get(k, opts['5'])


def get_buttons(rows=None):
    buttons = []
    for row in rows or config.RESP['buttons']:
        buttons.append([types.KeyboardButton(text=btn) for btn in row])
    kbd = types.ReplyKeyboardMarkup(buttons, resize_keyboard=True, one_time_keyboard=True)
    return kbd


def pack_ids(ids: List[int]) -> str:
    return base64.a85encode(struct.pack('h' * len(ids), *ids)).decode()


def unpack_ids(s: str) -> List[int]:
    b = base64.a85decode(s.encode())
    return list(struct.unpack('h' * (len(b) // 2), b))


def uncap(s: str) -> str:
    if not s:
        return s
    return s[0].lower() + s[1:]


async def delete_msg(bot, source: Union[types.Message, types.CallbackQuery],
                     message_id: Union[int, FSMContext] = None):
    user_id = source.from_user.id
    if isinstance(message_id, FSMContext):
        message_id = (await message_id.get_data()).get('reply')
    if isinstance(source, types.CallbackQuery):
        if isinstance(message_id, list):
            message_id.append(source.message.message_id)
        else:
            message_id = source.message.message_id

    if message_id:
        if not isinstance(message_id, list):
            message_id = [message_id]
        for msg_id in message_id:
            if msg_id:
                try:
                    await bot.delete_message(user_id, msg_id)
                except MessageToDeleteNotFound:
                    pass
                except TelegramAPIError:
                    pass
