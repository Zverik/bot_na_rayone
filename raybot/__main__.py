from raybot.model import db
from raybot.bot import dp
from raybot.cli import geojson, buildings, photos, test_map, missing, tags
import raybot.handlers  # noqa
import logging
import sys
from aiogram import executor


async def shutdown(dp):
    await db.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        logging.basicConfig(level=logging.INFO)
        executor.start_polling(dp, skip_updates=True, on_shutdown=shutdown)
    else:
        cmd = sys.argv[1].lower()
        if cmd == 'export':
            geojson.run_export()
        elif cmd == 'import':
            geojson.run_import()
        elif cmd == 'export_tags':
            tags.run_export()
        elif cmd == 'import_tags':
            tags.run_import()
        elif cmd == 'buildings':
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
            print('export — export poi database to a geojson')
            print('import — import poi database from a geojson')
            print('export_tags — export poi and their tags to a CSV file')
            print('import_tags — import poi tags from a CSV file')
            print('buildings — print missing building photos and entrance info')
            print('photos — print missing and stray photos')
            print('missing — print pois with missing important keys')
            print('map — generate a map image')
