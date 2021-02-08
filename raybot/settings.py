import yaml
import os
import sys
import logging


class Config:
    def __init__(self, path: str = None):
        BASE_DIR = os.path.dirname(__file__)
        CONFIG_DIR = os.path.join(BASE_DIR, 'config')
        ALT_CONFIG_DIR = path or os.path.join(BASE_DIR, '..', 'config')

        # Configuration options
        CONFIG = self.merge_yamls('config.yml', ALT_CONFIG_DIR)
        self.TELEGRAM_TOKEN = CONFIG.get('telegram_token')
        self.ADMIN = CONFIG.get('admin_id')
        self.LOGS = self.rel_expand(CONFIG.get('logs', BASE_DIR), ALT_CONFIG_DIR)
        self.MAINTENANCE = CONFIG.get('maintenance', False)
        self.BBOX = CONFIG.get('bbox')
        self.PRUNE_TIMEOUT = int(CONFIG.get('prune_timeout', 10))
        language = CONFIG.get('language', 'ru')

        # Common paths
        self.DATABASE = self.rel_expand(
            CONFIG.get('database', 'raybot.sqlite'), ALT_CONFIG_DIR)
        self.PHOTOS = self.rel_expand(CONFIG.get('photos', 'photo'), ALT_CONFIG_DIR)
        self.TILES = self.rel_expand(CONFIG.get('tiles', 'tiles'), ALT_CONFIG_DIR)
        logging.debug(f'Photos: {self.PHOTOS}, tiles: {self.TILES}')

        # Strings and lists
        self.MSG = self.merge_yamls(['strings.yml', f'strings.{language}.yml'],
                                    os.path.join(CONFIG_DIR, 'strings'), ALT_CONFIG_DIR)
        self.TAGS = self.merge_yamls(['tags.yml', f'tags.{language}.yml'],
                                     os.path.join(CONFIG_DIR, 'tags'), ALT_CONFIG_DIR)
        self.RESP = self.merge_yamls('responses.yml', ALT_CONFIG_DIR)
        self.ADDR = self.merge_yamls('addr.yml', ALT_CONFIG_DIR)

    @staticmethod
    def check_paths(names, *paths):
        for path in paths:
            if path:
                if isinstance(names, str):
                    names = [names]
                for name in names:
                    p = os.path.join(path, name)
                    if os.path.exists(p):
                        yield p

    @staticmethod
    def merge_dict(target, other):
        for k, v in other.items():
            if isinstance(v, dict):
                node = target.setdefault(k, {})
                Config.merge_dict(node, v)
            else:
                target[k] = v

    @staticmethod
    def merge_yamls(names, *paths):
        result = {}
        for p in Config.check_paths(names, *paths):
            logging.debug('Reading %s', p)
            with open(p, 'r') as f:
                Config.merge_dict(result, yaml.safe_load(f))
        return result

    @staticmethod
    def rel_expand(path, base_path):
        if not path or not base_path or os.path.isabs(path):
            return path
        if not os.path.isdir(base_path):
            base_path = os.path.dirname(base_path)
        return os.path.join(base_path, path)


if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
    config = Config(sys.argv[1])
else:
    config = Config()
