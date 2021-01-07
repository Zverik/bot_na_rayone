from raybot.model import db
from raybot.bot import dp
from raybot.cli import geojson, buildings, photos, test_map, reindex, duplicates
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
        elif cmd == 'buildings':
            buildings.run()
        elif cmd == 'photos':
            photos.run()
        elif cmd == 'map':
            test_map.run()
        elif cmd == 'index':
            reindex.run()
        elif cmd == 'dedup':
            duplicates.run()
        else:
            print('Supported commands:')
            print()
            print('export — export poi database to a geojson')
            print('import — import poi database from a geojson')
            print('buildings — print missing building photos and entrance info')
            print('photos — print missing and stray photos')
            print('map — generate a map image')
            print('index — regenerate full-text search index')
            print('dedup — deduplicate uploaded photos for POI')
