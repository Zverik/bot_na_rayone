from raybot.model import db
from raybot.bot import dp
from raybot.cli import buildings, photos, test_map, missing
import raybot.handlers  # noqa
import logging
import sys
import os
from aiogram import executor


async def shutdown(dp):
    await db.close()


def main():
    if len(sys.argv) < 2 or os.path.isdir(sys.argv[1]):
        logging.basicConfig(level=logging.INFO)
        executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)
    else:
        cmd = sys.argv[1].lower()
        if cmd == 'buildings':
            buildings.run()
        elif cmd == 'photos':
            photos.run()
        elif cmd == 'map':
            test_map.run()
        elif cmd == 'missing':
            missing.run()
        else:
            print('Supported commands:')
            print()
            print('buildings — print missing building photos and entrance info')
            print('photos — print missing and stray photos')
            print('missing — print pois with missing important keys')
            print('map — generate a map image')


if __name__ == '__main__':
    main()
