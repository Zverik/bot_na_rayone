import yaml
import os

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')

# Common paths
DATABASE = os.path.join(BASE_DIR, 'raybot.sqlite')
PHOTOS = os.path.join(BASE_DIR, 'photo')
TILES = os.path.join(BASE_DIR, 'tiles')

# Configuration options
with open(os.path.join(CONFIG_DIR, 'config.yml'), 'r') as f:
    CONFIG = yaml.safe_load(f)
TELEGRAM_TOKEN = CONFIG.get('telegram_token')
ADMIN = CONFIG.get('admin_id')
LOGS = CONFIG.get('logs')
MAINTENANCE = CONFIG.get('maintenance')
BBOX = CONFIG.get('bbox')

# Strings and lists
with open(os.path.join(CONFIG_DIR, 'responses.yml'), 'r') as f:
    MSG = yaml.safe_load(f)
addr_path = os.path.join(CONFIG_DIR, 'addr.yml')
if not os.path.exists(addr_path):
    ADDR = {}
else:
    with open(addr_path, 'r') as f:
        ADDR = yaml.safe_load(f)
with open(os.path.join(CONFIG_DIR, 'tags.yml'), 'r') as f:
    TAGS = yaml.safe_load(f)
