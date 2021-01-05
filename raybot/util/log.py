from raybot import config
import os
from datetime import datetime
from aiogram import types
from aiogram.dispatcher.middlewares import LifetimeControllerMiddleware


class LoggingMiddleware(LifetimeControllerMiddleware):
    async def pre_process(self, obj, data, *args):
        if isinstance(obj, types.Message):
            if obj.text and obj.text[0] == '/':
                typ = 'command'
            else:
                typ = 'message'
            user_id = obj.from_user.id
        elif isinstance(obj, types.CallbackQuery):
            typ = 'callback'
            user_id = obj.from_user.id
        else:
            # not logging updates
            return
        with open(os.path.join(config.LOGS, 'access.log'), 'a') as f:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f'{now}\t{user_id}\t{typ}\n')
