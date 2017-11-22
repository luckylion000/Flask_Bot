#!/usr/bin/env python3

import click
from blinker import signal
from celery.utils.log import get_task_logger
from emojipy import Emoji
from mongoengine import Document

from botbase import BotBase, raven_client
from newsbot.facebook_api import FacebookAPI, FacebookAPIError
from newsbot.models import Account, ChatUser, PollQuestions
from newsbot.server import create_app
import settings

logger = get_task_logger(__name__)


class FacebookBot(BotBase):

    PLATFORM = 'facebook'

    TYPING_TIME = 0.5
    CHECK_NEW_BULLETINS_INTERVAL = 60
    CHARS_SECOND = 5
    MIN_TIME = 3
    MAX_TIME = 15

    def __init__(self, account_id):
        self.account = self.validate_account(account_id)
        self.bot = FacebookAPI(self.account.botconnection_facebook_token)

    def typing(self, chat_id, message):
        pass

    def validate_account(self, account_id):
        a = super(FacebookBot, self).validate_account(account_id)
        assert len(a.botconnection_facebook_token)
        return a

    def extract_username(self, msg):

        sender_id = msg['sender']['id']
        data = self.bot.get_user(sender_id)

        if 'first_name' in data:
            user = data['first_name'] + ' ' + data['last_name']
        elif 'name' in data:
            user = data['name']
        else:
            user = 'anonymous'

        return user

    def send_welcome(self, chat_id):

        a = Account.objects.get(id=self.account.id)
        self.account.welcome_message_1 = a.welcome_message_1
        self.account.welcome_answer_1 = a.welcome_answer_1

        self.typing(chat_id, self.account.welcome_message_1)

        self.bot.sendMessage(chat_id, self.account.welcome_message_1)

        self.typing(chat_id, self.account.welcome_message_2)
        self.bot.sendMessage(
            chat_id,
            self.account.welcome_message_2,
            buttons=[self.account.welcome_answer_1]
        )

    def send_welcome_stage2(self, chat_id):
        a = Account.objects.get(id=self.account.id)
        self.account.welcome_message_3 = a.welcome_message_3
        self.account.welcome_answer_2_option_1 = a.welcome_answer_2_option_1
        self.account.welcome_answer_2_option_2 = a.welcome_answer_2_option_2

        self.typing(chat_id, self.account.welcome_message_3)

        self.bot.sendMessage(
            chat_id,
            self.account.welcome_message_3,
            buttons=[
                self.account.welcome_answer_2_option_1,
                self.account.welcome_answer_2_option_2
            ]
        )

    def process_no_content(self, user, chat_id):

        if user.up_to_date_counter == settings.QUESTION_INTERVAL:
            user.up_to_date_counter = 0
            # send new question
            self.switch_next_profile_story(user, chat_id)
            return

        if user.disable_no_content == 1:
            return

        user.disable_no_content = 1
        user.state = ChatUser.STATE_READY_RECEIVED
        user.up_to_date_counter += 1
        user.save()
        super(FacebookBot, self).process_no_content(user, chat_id)

        up_to_date_message = Account.objects.get(id=self.account.id).\
            up_to_date_message

        self.typing(chat_id, up_to_date_message)
        self.bot.sendMessage(chat_id, up_to_date_message)

    def start_bulletin_reading(self, user, chat_id, disable_no_content=False, bulletin_id=None):

        try:
            super(FacebookBot, self).start_bulletin_reading(
                user, chat_id, disable_no_content=disable_no_content, bulletin_id=bulletin_id)
        except FacebookAPIError as error:
            # chat_id not found
            raven_client.captureException()
            logger.warning('chat id not found. Disabling: for user: {user}, error: {error_message}'.format(user=user.name, error_message=str(error)))
            user.disabled = 1
            user.save()

    def validate_msg(self, msg):
        return True

    def send_lead_answers(self, chat_id, lead, fragments):

        buttons = [Emoji.shortcode_to_unicode(f.text) for f in fragments]
        self.typing(chat_id, lead)
        self.bot.sendMessage(chat_id, lead, buttons=buttons)

    def send_image_fragment(self, chat_id, f, show_keyboard=None):
        self.bot.sendPhoto(chat_id, f.url, buttons=show_keyboard)

    def send_audio_fragment(self, chat_id, f, show_keyboard=None):
        self.bot.sendAudio(chat_id, f.url, buttons=show_keyboard)

    def send_document_fragment(self, chat_id, f, show_keyboard=None):
        self.bot.sendDocument(chat_id, f.url, buttons=show_keyboard)

    def send_video_fragment(self, chat_id, f, show_keyboard=None):
        pass

    def send_text_fragment(self, chat_id, f, show_keyboard=None):

        self.typing(chat_id, f.text)
        self.bot.sendMessage(
            chat_id,
            Emoji.shortcode_to_unicode(f.text),
            buttons=show_keyboard
        )

    def send_poll_fragment(self, chat_id, f):

        self.typing(chat_id, f.text)
        self.bot.sendMessagePostback(
            chat_id,
            Emoji.shortcode_to_unicode(f.text),
            buttons=self.get_poll_keyboard(f)
        )

    def get_poll_keyboard(self, fragment):

        def get_callback_data(fragment, question):

            if isinstance(fragment, Document):
                fragment = fragment.id
            if isinstance(question, Document):
                question = question.id

            return '{fragment},{question}'.format(fragment=fragment, question=question)

        buttons = []
        for q in PollQuestions.objects(fragment=fragment):
            buttons.append(
                (q.text, get_callback_data(fragment, q))
            )

        return buttons

    def send_question_fragment(self, user, chat_id, q):
        self.typing(chat_id, q.text)
        if not q.attribute:
            logger.error('Question Fragment:{fragment} should have attribute'.\
                format(fragment=q.id))
            return

        buttons = None
        if q.attribute.options:
            # show each option in separate row
            buttons = [option.text for option in q.options]

        logger.info('sending next question to {user}'.format(user=user.name))
        self.bot.sendMessage(
            chat_id, q.text,
            buttons=buttons
        )

    def read_user_message(self, msg):

        if 'quick_reply' in msg['message']:
            return msg['message']['quick_reply']['payload']

        return msg['message']['text']

    def get_chat_id(self, msg):
        return msg['sender']['id']

    def get_chat_id_inline(self, msg):
        return self.get_chat_id(msg)

    def get_payload(self, msg):
        return msg['postback']['payload']

    def vote_done(self, msg, fragment_id, question_id):
        pass

    def vote_skip(self, msg):
        pass

    def get_answers_keyboard(self, answers):
        return [Emoji.shortcode_to_unicode(f.text) for f in answers]

    def handle_message(self, msg):
        super(FacebookBot, self).handle_message(msg)

    def handle_callback_query(self, msg):
        super(FacebookBot, self).handle_callback_query(msg)

    def start(self, app):

        signal('facebook-message').connect(self.handle_message)
        signal('facebook-postback').connect(self.handle_callback_query)
        app.run(debug=False, port=5001)


@click.command()
@click.argument('account_id')
def main(account_id):
    app = create_app()

    with app.app_context():
        b = FacebookBot(account_id)
        b.start(app)


if __name__ == '__main__':
    main()
