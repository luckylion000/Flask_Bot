import logging
import os.path
import os
#import redis
import re

from newsbot.helpers import env_setting


PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

# Max uploaded file size
MAX_CONTENT_LENGTH = 5 * 1024 * 1024

LOG_FILE = 'app.log'
LOG_LEVEL = logging.DEBUG
LOG_REQUEST = True
LOG_FORMAT = '%(process)d [%(asctime)s] [%(levelname)s]: %(message)s '

AWS_S3_KEY = env_setting('AWS_S3_KEY', 'key')
AWS_S3_SECRET = env_setting('AWS_S3_SECRET', 'secret')
AWS_S3_BUCKET = env_setting('AWS_S3_BUCKET', 'newsbotfiles')
AWS_S3_REGION = env_setting('AWS_S3_REGION', 'eu-west-1')

PENDING_BULLETIN_INACTIVE_INTERVAL = 15
CHECK_ACTIVE_USERS = 15

BULLETIN_SEND_INTERVAL = env_setting('BULLETIN_SEND_INTERVAL', '*')
QUESTION_INTERVAL = 5
MIN_QUESTIONS = 3

#MONGODB_SETTINGS = {
#    'db': 'newsbot_test',
#    'host': 'localhost',
#    'port': 3000,
#    'username': '',
#    'password': '',
#}

MONGO_URI = env_setting(
    'MONGO_URI', 'mongodb://<dbuser>:<dbpassword>@<dbhost>:<dbport>/<dbname>'
)

MONGODB_SETTINGS = {
    'host': MONGO_URI
}

TELEGRAM_ENDPOINT = env_setting('TELEGRAM_ENDPOINT', "https://api.telegram.org/")

MAXIMUM_FILE_UPLOAD_SIZE_MB = 10
MAX_CONTENT_LENGTH = MAXIMUM_FILE_UPLOAD_SIZE_MB * 1024 * 1024

SESSION_PROTECTION = 'strong'
BULLETIN_EXPIRE_HOURS = 12
BULLETIN_NEW_TITLE_FORMAT = 'Draft for %m/%d/%Y at %H:%M'
ACTIVE_ACCOUNT_KEY = 'active_account_id'

TEMPLATES_AUTO_RELOAD = True

SENTRY_DSN = env_setting('SENTRY_DSN', '')

# redis session
#REDIS_URI = '@pub-redis-17240.eu-central-1-1.1.ec2.redislabs.com:17240'

#SESSION_TYPE = 'redis'
#m = re.search("(.*)@([a-zA-Z0-9\-\.]+\.+[a-zA-Z]{2,3}):([0-9]+)", REDIS_URI)
#REDIS_PASSWORD = m.group(1)
#REDIS_HOST = m.group(2)
#REDIS_PORT = int(m.group(3))
#SESSION_REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, password=REDIS_PASSWORD)

LOCAL_BROKER = env_setting(
    'LOCAL_BROKER', 'amqp://{user}:{password}@{host}/{vhost}'.format(
        user='guest',
        password='',
        host='127.0.0.1',
        vhost=''
    )
)

SERVER_PORT = 5000

MAIL_SERVER = env_setting('MAIL_SERVER', 'smtp.postmarkapp.com')
MAIL_USE_TLS = True
MAIL_USERNAME = env_setting('MAIL_USERNAME', '18d07a27-3886-4980-88fd-68eff0cc2592')
MAIL_PASSWORD = env_setting('MAIL_PASSWORD', '18d07a27-3886-4980-88fd-68eff0cc2592')
MAIL_DEFAULT_SENDER = env_setting('MAIL_USERNAME', 'info@bulletin.chat')

PATH_TO_AMCHART_IMAGES = '/static/dist/amcharts/images/'

FACEBOOK_APP_ID = env_setting('FACEBOOK_APP_ID', '210684419413318')
FACEBOOK_APP_SECRET = env_setting('FACEBOOK_APP_SECRET', 'aab2d5b2febbfe23f83f42d69c950af8')
FACEBOOK_VERIFY_TOKEN = 'fb_token_test'

ADMINS_EMAIL = ['xavi@bulletin.chat', 'hola@elies.org', 'info@bulletin.chat']

try:
    from settings_local import *  # NOQA
except ImportError:
    pass

