import yaml
import os
import sys


class Config:
    def __init__(self, path: str = None):
        FILE_DIR = os.path.join(os.path.dirname(__file__), '..')
        CONFIG_DIR = os.path.join(FILE_DIR, 'config') if not path else path
        BASE_DIR = os.path.join(CONFIG_DIR, '..')

        # Configuration options
        with open(os.path.join(CONFIG_DIR, 'config.yml'), 'r') as f:
            CONFIG = yaml.safe_load(f)
        self.TELEGRAM_TOKEN = CONFIG.get('telegram_token')
        self.ADMIN = CONFIG.get('admin_id')
        self.LOGS = CONFIG.get('logs', BASE_DIR)
        self.MAINTENANCE = CONFIG.get('maintenance', False)
        self.BBOX = CONFIG.get('bbox')
        self.PRUNE_TIMEOUT = int(CONFIG.get('prune_timeout', 10))

        # Common paths
        self.DATABASE = CONFIG.get('database', os.path.join(BASE_DIR, 'raybot.sqlite'))
        self.PHOTOS = CONFIG.get('photos', os.path.join(BASE_DIR, 'photo'))
        self.TILES = CONFIG.get('tiles', os.path.join(BASE_DIR, 'tiles'))

        # Strings and lists
        with open(os.path.join(CONFIG_DIR, 'strings.yml'), 'r') as f:
            self.MSG = yaml.safe_load(f)
        with open(os.path.join(CONFIG_DIR, 'responses.yml'), 'r') as f:
            self.RESP = yaml.safe_load(f)
        addr_path = os.path.join(CONFIG_DIR, 'addr.yml')
        if not os.path.exists(addr_path):
            self.ADDR = {}
        else:
            with open(addr_path, 'r') as f:
                self.ADDR = yaml.safe_load(f)
        with open(os.path.join(CONFIG_DIR, 'tags.yml'), 'r') as f:
            self.TAGS = yaml.safe_load(f)


if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
    config = Config(sys.argv[1])
else:
    config = Config()
