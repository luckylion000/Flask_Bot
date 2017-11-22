
from celery import Celery
from flask import Blueprint, request
from .models import Account
from settings import LOCAL_BROKER

bp = Blueprint('telegramhandler', __name__)
app = Celery('tasks', broker=LOCAL_BROKER)

@bp.route('/telegram/<string:token>', methods=['POST'])
def handler(token):
    # post to celery

    account = Account.objects.filter(botconnection_telegram_token=token).first()
    if account is not None:
        print(account.id)
        app.send_task('telegram.handle_event', kwargs={'account_id': account.id, 'token': token, 'event': request.json})
        #handle_event.delay(account.id, token, request.json)
    return 'OK'
