import yaml
import os

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')

# Configuration options
with open(os.path.join(CONFIG_DIR, 'config.yml'), 'r') as f:
    CONFIG = yaml.safe_load(f)
TELEGRAM_TOKEN = CONFIG.get('telegram_token')
ADMIN = CONFIG.get('admin_id')
LOGS = CONFIG.get('logs', BASE_DIR)
MAINTENANCE = CONFIG.get('maintenance', False)
BBOX = CONFIG.get('bbox')

# Common paths
DATABASE = CONFIG.get('database', os.path.join(BASE_DIR, 'raybot.sqlite'))
PHOTOS = CONFIG.get('photos', os.path.join(BASE_DIR, 'photo'))
TILES = CONFIG.get('tiles', os.path.join(BASE_DIR, 'tiles'))

# Strings and lists
with open(os.path.join(CONFIG_DIR, 'strings.yml'), 'r') as f:
    MSG = yaml.safe_load(f)
with open(os.path.join(CONFIG_DIR, 'responses.yml'), 'r') as f:
    RESP = yaml.safe_load(f)
addr_path = os.path.join(CONFIG_DIR, 'addr.yml')
if not os.path.exists(addr_path):
    ADDR = {}
else:
    with open(addr_path, 'r') as f:
        ADDR = yaml.safe_load(f)
with open(os.path.join(CONFIG_DIR, 'tags.yml'), 'r') as f:
    TAGS = yaml.safe_load(f)
