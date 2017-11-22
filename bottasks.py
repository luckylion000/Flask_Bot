#celery -A bottasks beat -l info

import time

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, eventlet_pool_started
from celery.utils.log import get_task_logger
from raven import Client
from raven.contrib.celery import register_logger_signal, register_signal
from telegrambot import TelegramBot
from facebookbot import FacebookBot
from mongoengine.queryset.visitor import Q

from newsbot.models import Account, AccountStats, ChatUser, Bulletin
from newsbot.server import create_app
from settings import (
    BULLETIN_SEND_INTERVAL, LOCAL_BROKER, SENTRY_DSN,
    CHECK_ACTIVE_USERS, PENDING_BULLETIN_INACTIVE_INTERVAL)

from datetime import datetime, timedelta
import pymongo
import time

'''
register_connection(
    name=MONGODB_SETTINGS['db'],
    host=MONGODB_SETTINGS['host'],
    port=MONGODB_SETTINGS['port'],
    username=MONGODB_SETTINGS['username'],
    password=MONGODB_SETTINGS['password'],
    alias="default-mongodb-connection"
)
'''

bottasks = Celery('tasks', broker=LOCAL_BROKER)
bottasks.conf.CELERYBEAT_SCHEDULE = {
    #'send_published_messages': {
    #    'task': 'base.send_published_bulletins',
    #    'schedule': crontab(minute=BULLETIN_SEND_INTERVAL)
    #},
    'setup_account_stats': {
        'task': 'base.setup_account_stats',
        'schedule': crontab(minute='0', hour='0')
    },
    'check_pending_bulletins': {
        'task': 'base.check_pending_bulletins',
        'schedule': crontab(minute=BULLETIN_SEND_INTERVAL)
    }
}

bottasks.conf.CELERY_ROUTES = {
        'base.send_published_bulletins': {
            'queue': 'batch_tasks',
        },
        'telegram.send_published_bulletins_user': {
            'queue': 'batch_tasks'
        },
        'base.setup_account_stats': {
            'queue': 'batch_tasks',
        },
        'base.send_bulletin': {
            'queue': 'batch_tasks',
        },
        'base.check_user_bulletin': {
            'queue': 'batch_tasks'
        },
        'base.send_user_bulletin': {
            'queue': 'batch_tasks'
        },
        'base.check_pending_bulletins': {
            'queue': 'batch_tasks'
        },
        'base.send_user_bulletin' : {
            'queue': 'batch_tasks'
        }
}

logger = get_task_logger(__name__)

raven_client = Client(SENTRY_DSN)
register_logger_signal(raven_client)
# register_logger_signal(client, loglevel=logging.INFO)
register_signal(raven_client)


@worker_process_init.connect
def init_worker(**kwargs):
    create_app()


@eventlet_pool_started.connect
def init_eventlet_pool(**kwargs):
    """ Execute when Eventlet pool is enabled """
    import eventlet
    eventlet.monkey_patch()
    create_app()


@bottasks.task(name="telegram.handle_event")
def telegram_handle_event(account_id, token, event):
    print(account_id)
    print(token)
    print(event)

    b = TelegramBot(account_id)

    if 'message' in event:
        b.handle_message(event['message'])
    elif 'callback_query' in event:
        b.handle_callback_query(event['callback_query'])
    else:
        logger.debug('event not supported')

    return 'OK'


@bottasks.task(name="facebook.handle_event")
def facebook_handle_event(account_id, event):

    b = FacebookBot(account_id)

    if 'message' in event:
        b.handle_message(event)
    elif 'postback' in event:
        b.handle_callback_query(event)
    else:
        logger.debug('event not supported')

    return 'OK'


@bottasks.task(name="base.send_published_bulletins")
def send_published_bulletins():

    accounts = Account.objects()

    for a in accounts:
        try:
            logger.info('publishing bulletins for {account} {token}'.format(account=a.name, token=a.botconnection_telegram_token))
            if a.botconnection_telegram_token is not None:
                chat_users = ChatUser.objects.filter(account_id=a.id, disabled=0)

                for user in chat_users:
                    send_published_bulletins_user.delay(a.id, user.id)

                time.sleep(1)
            else:
                logger.info('account {account} has no token'.format(account=a.name))
        except Exception as error:
            raven_client.captureException()
            logger.error('error with acount {account} {error_message}'.format(account=a.name, error_message=str(error)))
    return 'OK'


@bottasks.task(name="telegram.send_published_bulletins_user", bind=True, rate_limit="30/s")
def send_published_bulletins_user(self, account_id, user_id):
    # fetch all users subscribed to account
    try:
        TelegramBot(account_id).sending_published_bulletins_user(user_id)
    except pymongo.errors.AutoReconnect as e:
        logger.warning('Could\'t connect to MongoDb, retry in in 10 seconds: ' + str(e))
        time.sleep(10)

        try:
            TelegramBot(account_id).sending_published_bulletins_user(user_id)
        except pymongo.errors.AutoReconnect as e:
            logger.error('Could\'t connect to MongoDb: ' + str(e))


@bottasks.task(name="base.setup_account_stats")
def setup_account_stats():
    # init stats object for each account
    AccountStats.update_enabled_users(Account.objects())

@bottasks.task(name="base.check_pending_bulletins")
def check_pending_bulletins():
    utcnow = datetime.utcnow()

    """ check for pending bulletins with publish date bigger than now """
    print('checking pending bulletins YESSS!!!')
    pending_bulletins = Bulletin.objects(is_published=True, pending=True, publish_at__lte=datetime.utcnow())
    #pending_bulletins = Bulletin.objects(is_published=True, pending=True)
    #pending_bulletins = Bulletin.objects
    print(len(pending_bulletins))
    #Bulletin.objects(id__in=[b.id for b in pending_bulletins]).\
    #    update(pending=False, full_result=True, multi=True)

    def get_expire_time(bulletin):
        return bulletin.publish_at + timedelta(hours=bulletin.expire_hours)

    for b in pending_bulletins:
        # check expiring
        print(b.title)

        if utcnow < get_expire_time(b):
            print(b)

            send_bulletin.delay(b.id, b.account.id)
            b.pending = False
            b.save()


@bottasks.task(name="base.send_bulletin")
def send_bulletin(bulletin_id, account_id):
    inactive_from = datetime.utcnow() -\
        timedelta(minutes=PENDING_BULLETIN_INACTIVE_INTERVAL)

    inactive_users = ChatUser.objects(
        (
            Q(state=ChatUser.STATE_READY_RECEIVED) &
            Q(account_id=account_id) &
            Q(disabled=0)
        ) | (
            Q(state=ChatUser.STATE_WAITING_ANSWER) &
            Q(last_message__lte=inactive_from) &
            Q(account_id=account_id) &
            Q(disabled=0)
        )
    )

    active_users = ChatUser.objects(
        account_id=account_id, disabled=0,
        last_message__gt=inactive_from,
        state=ChatUser.STATE_WAITING_ANSWER
    )

    # handle inactive users
    for u in inactive_users:
        send_user_bulletin.delay(u, account_id, bulletin_id)

    # handle active users
    for u in active_users:
        check_user_bulletin.apply_async(
            (u.chat_id, account_id, bulletin_id), countdown=CHECK_ACTIVE_USERS*60)


@bottasks.task(name="base.check_user_bulletin")
def check_user_bulletin(chat_id, account_id, bulletin_id):
    def is_user_inactive_or_ready(user):
        if user.state == ChatUser.STATE_READY_RECEIVED:
            return True

        inactive_from = datetime.utcnow() -\
            timedelta(minutes=PENDING_BULLETIN_INACTIVE_INTERVAL)

        if user.state == ChatUser.STATE_WAITING_ANSWER and\
            user.last_message <= inactive_from:
            return True

        return False

    try:
        user = ChatUser.objects.get(chat_id=chat_id, account_id=account_id)
        if bulletin_id not in [b.id for b in user.read_bulletins]:
            if is_user_inactive_or_ready(user):
                # send bulletin to the user
                send_user_bulletin.delay(user, account_id, bulletin_id)
            else:
                # retry in CHECK_ACTIVE_USERS minutes
                check_user_bulletin.apply_async(
                    (chat_id, account_id, bulletin_id), countdown=CHECK_ACTIVE_USERS*60)

    except ChatUser.DoesNotExist:
         logger.warning('User with chat_id=%s, account_id=%s doesn\'t exists' % (
             chat_id, account_id
         ))


@bottasks.task(name="base.send_user_bulletin")
def send_user_bulletin(user, account_id, bulletin_id):
    if user.platform == 'telegram':
        TelegramBot(account_id).start_bulletin_reading(
            user, user.chat_id,
            disable_no_content=True,
            bulletin_id=bulletin_id
        )
    elif user.platform == 'facebook':
        FacebookBot(account_id).start_bulletin_reading(
            user, user.chat_id,
            disable_no_content=True,
            bulletin_id=bulletin_id
        )
