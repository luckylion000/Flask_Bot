from celery import Celery
import telepot
from telegramcelerybot import TelegramBot
from flask import Flask

LOCAL_BROKER = 'amqp://guest:guest@localhost/celerybot'

bottasks = Celery('tasks', broker=LOCAL_BROKER)

from newsbot.server import create_app

flask_app = create_app()


@bottasks.task(name="telegram.handle_event")
def handle_event(account_id, token, event):
    print(account_id)
    print(token)
    print(event)


    b = TelegramBot(account_id)
    b.handle_message(event['message'])

    return 'OK'