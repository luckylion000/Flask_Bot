
from blinker import signal
from celery import Celery
from flask import Blueprint, request

from settings import FACEBOOK_VERIFY_TOKEN, LOCAL_BROKER
from .extensions import csrf
from .models import Account

bp = Blueprint('facebookhandler', __name__)
app = Celery('tasks', broker=LOCAL_BROKER)

fb_message = signal('facebook-message')
fb_postback = signal('facebook-postback')


@bp.route('/facebook', methods=['GET'])
def verify():

    if request.args.get('hub.mode') == 'subscribe' and request.args.get('hub.challenge'):
        if not request.args.get('hub.verify_token') == FACEBOOK_VERIFY_TOKEN:
            return 'Verification token mismatch', 403
        return request.args['hub.challenge'], 200

    return 'Hello world', 200


@bp.route('/facebook', methods=['POST'])
@csrf.exempt
def webhook():

    data = request.get_json()
    if data['object'] == 'page':

        for entry in data['entry']:

            page_id = entry['id']
            account = Account.objects.filter(
                        botconnection_facebook_page_id=page_id).first()
            if account:
                for event in entry['messaging']:

                    if 'message' in event or 'postback' in event:
                        app.send_task('facebook.handle_event',
                                      kwargs={
                                        'account_id': account.id,
                                        'event': event})

                    if 'message' in event:
                        fb_message.send(event)
                    if 'postback' in event:
                        fb_postback.send(event)

    return 'ok', 200
