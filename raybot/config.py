import yaml
import os

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
with open(os.path.join(CONFIG_DIR, 'responses.yml'), 'r') as f:
    MSG = yaml.safe_load(f)
with open(os.path.join(CONFIG_DIR, 'addr.yml'), 'r') as f:
    ADDR = yaml.safe_load(f)
with open(os.path.join(CONFIG_DIR, 'tags.yml'), 'r') as f:
    TAGS = yaml.safe_load(f)
DATABASE = os.path.join(BASE_DIR, 'raybot.sqlite')
PHOTOS = os.path.join(BASE_DIR, 'photo')
TILES = os.path.join(BASE_DIR, 'tiles')

with open(os.path.join(CONFIG_DIR, 'config.yml'), 'r') as f:
    CONFIG = yaml.safe_load(f)
TELEGRAM_TOKEN = CONFIG.get('telegram_token')
ADMIN = CONFIG.get('admin_id')
LOGS = CONFIG.get('logs')
MAINTENANCE = CONFIG.get('maintenance')