
import time
from urllib.request import urlopen

import click
import telepot
from celery.utils.log import get_task_logger
from emojipy import Emoji
from mongoengine import Document
from telepot.namedtuple import InlineKeyboardButton, InlineKeyboardMarkup

from newsbot.models import (
    Account,
    ChatUser,
    PollQuestions,
)

from botbase import BotBase, raven_client
from newsbot.server import create_app

from settings import TELEGRAM_ENDPOINT
import settings

logger = get_task_logger(__name__)


class TelegramBot(BotBase):

    PLATFORM = 'telegram'

    TYPING_TIME = 0.5
    CHECK_NEW_BULLETINS_INTERVAL = 60
    CHARS_SECOND = 5
    MIN_TIME = 3
    MAX_TIME = 15

    def __init__(self, account_id):
        self.account = self.validate_account(account_id)
        self.bot = telepot.Bot(self.account.botconnection_telegram_token, endpoint=TELEGRAM_ENDPOINT)

    def typing(self, chat_id, message):

        '''
        sleep_time = min(len(message) / self.CHARS_SECOND, self.MAX_TIME)

        print("{size} in {secs}".format(size=len(message), secs=sleep_time))


        while sleep_time > 0:
            self.bot.sendChatAction(chat_id, 'typing')
            time.sleep(self.MIN_TIME)
            sleep_time -= self.MIN_TIME
        '''
        self.bot.sendChatAction(chat_id, 'typing')
        time.sleep(2)

    def validate_account(self, account_id):
        a = super(TelegramBot, self).validate_account(account_id)
        assert len(a.botconnection_telegram_token)

        return a

    def extract_username(self, msg):
        if 'username' in msg['chat']:
            user = msg['chat']['username']
        elif {'first_name', 'last_name'}.issubset(msg['chat'].keys()):
            user = msg['chat']['first_name'] + " " + msg['chat']['last_name']
        elif 'first_name' in msg['chat']:
            user = msg['chat']['first_name']
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
            reply_markup={'keyboard': [[self.account.welcome_answer_1]],
                          'one_time_keyboard': True,
                          'resize_keyboard': True},
            disable_web_page_preview=True
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
            reply_markup={
                'keyboard': [
                    [
                        self.account.welcome_answer_2_option_1,
                        self.account.welcome_answer_2_option_2
                    ]
                ],
                'one_time_keyboard': True,
                'resize_keyboard': True
            },
            disable_web_page_preview=True
            )

    def process_no_content(self, user, chat_id):
        if user.up_to_date_counter == settings.QUESTION_INTERVAL:
            user.up_to_date_counter = 0
            # send profile story
            self.switch_next_profile_story(user, chat_id, disable_no_content=False)
            return

        if user.disable_no_content == 1:
            return

        user.disable_no_content = 1
        user.state = ChatUser.STATE_READY_RECEIVED
        user.up_to_date_counter += 1
        user.save()
        super(TelegramBot, self).process_no_content(user, chat_id)

        up_to_date_message = Account.objects.get(id=self.account.id).\
            up_to_date_message

        self.typing(chat_id, up_to_date_message)
        self.bot.sendMessage(chat_id, up_to_date_message, reply_markup={'hide_keyboard': True})

    def start_bulletin_reading(self, user, chat_id, disable_no_content=False, bulletin_id=None):

        try:
            super(TelegramBot, self).start_bulletin_reading(
                user, chat_id, disable_no_content=disable_no_content, bulletin_id=bulletin_id)
        except telepot.exception.TelegramError as error:
            # chat_id not found
            raven_client.captureException()
            logger.warning('chat id not found. Disabling: for user: {user}, error: {error_message}'.format(user=user.name, error_message=str(error)))
            user.disabled = 1
            user.save()

    def validate_msg(self, msg):
        content_type, _, _ = telepot.glance(msg)

        return content_type == 'text'

    def send_lead_answers(self, chat_id, lead, fragments):
        show_keyboard = {
            'keyboard': [
                [Emoji.shortcode_to_unicode(f.text)] for f in fragments
            ],
            'one_time_keyboard': True,
            'resize_keyboard': True
        }

        self.typing(chat_id, lead)
        self.bot.sendMessage(chat_id, lead,
                             reply_markup=show_keyboard,
                             disable_web_page_preview=True)

    def send_image_fragment(self, chat_id, f, show_keyboard=None):

        #if show_keyboard:
        #    show_keyboard = {
        #        'keyboard': [[b] for b in show_keyboard],
        #        'one_time_keyboard': True,
        #        'resize_keyboard': True
        #    }

        if f.url.split('.')[-1].lower() == 'gif':
            self.bot.sendDocument(chat_id, (f.url.split('/')[-1], urlopen(f.url)), caption=f.text, reply_markup=show_keyboard)
        else:
            self.bot.sendPhoto(chat_id, ('image.'+f.url.split('.')[-1], urlopen(f.url)), caption=f.text, reply_markup=show_keyboard)

    def send_audio_fragment(self, chat_id, f, show_keyboard=None):

        #if show_keyboard:
        #    show_keyboard = {
        #        'keyboard': [[b] for b in show_keyboard],
        #        'one_time_keyboard': True,
        #        'resize_keyboard': True
        #    }

        if type(f.text) == str:
            if len(f.text) > 0:
                doc_name = f.text
            else:
                doc_name = f.url.split('/')[-1]
            self.bot.sendAudio(chat_id, ('file.'+f.url.split('.')[-1], urlopen(f.url)), caption=f.text, performer=doc_name, title=f.url.split('.')[-1], reply_markup=show_keyboard)
        else:
            self.bot.sendAudio(chat_id, ('file.'+f.url.split('.')[-1], urlopen(f.url)), reply_markup=show_keyboard)

    def send_document_fragment(self, chat_id, f, show_keyboard=None):

        #if show_keyboard:
        #    show_keyboard = {
        #        'keyboard': [[b] for b in show_keyboard],
        #        'one_time_keyboard': True,
        #        'resize_keyboard': True
        #    }

        if type(f.text) == str:
            if len(f.text) > 0:
                doc_name = f.text+'.' + f.url.split('.')[-1]
            else:
                doc_name = f.url.split('/')[-1]
            self.bot.sendDocument(chat_id, (doc_name, urlopen(f.url)), caption=f.text, reply_markup=show_keyboard)
        else:
            self.bot.sendDocument(chat_id, (f.url.split('/')[-1], urlopen(f.url)), reply_markup=show_keyboard)

    def send_video_fragment(self, chat_id, f, show_keyboard=None):

        #if show_keyboard:
        #    show_keyboard = {
        #        'keyboard': [[b] for b in show_keyboard],
        #        'one_time_keyboard': True,
        #        'resize_keyboard': True
        #    }

        if type(f.text) == str:
            if len(f.text) > 0:
                doc_name = f.text
            else:
                doc_name = f.url.split('/')[-1]
            self.bot.sendVideo(chat_id, ('file.'+f.url.split('.')[-1], urlopen(f.url)), caption=doc_name, reply_markup=show_keyboard)
        else:
            self.bot.sendVideo(chat_id, ('file.'+f.url.split('.')[-1], urlopen(f.url)), reply_markup=show_keyboard)

    def send_text_fragment(self, chat_id, f, show_keyboard=None):
        self.typing(chat_id, f.text)
        self.bot.sendMessage(
            chat_id,
            Emoji.shortcode_to_unicode(f.text),
            disable_web_page_preview=True,
            reply_markup=show_keyboard
        )

    def send_poll_fragment(self, chat_id, f):

        self.typing(chat_id, f.text)
        self.bot.sendMessage(
            chat_id,
            Emoji.shortcode_to_unicode(f.text),
            disable_web_page_preview=True,
            reply_markup=self.get_poll_keyboard(f)
        )

    def get_poll_keyboard(self, fragment, question_id=None):

        def get_callback_data(fragment, question):

            if isinstance(fragment, Document):
                fragment = fragment.id
            if isinstance(question, Document):
                question = question.id

            return '{fragment},{question}'.format(fragment=fragment, question=question)

        buttons = []

        for q in PollQuestions.objects(fragment=fragment):

            text = q.text
            if question_id and str(q.id) == question_id:
                text = q.text + Emoji.shortcode_to_unicode(' :white_check_mark:')

            buttons.append(
                [InlineKeyboardButton(text=text, callback_data=get_callback_data(fragment, q))]
            )

        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def send_question_fragment(self, user, chat_id, q):
        self.typing(chat_id, q.text)
        if not q.attribute:
            logger.error('Question Fragment:{fragment} should have attribute'.\
                format(fragment=q.id))
            return

        if q.attribute.options:
            # show each option in separate row
            keyboard = [[option.text] for option in q.attribute.options]
            show_keyboard = {
                'keyboard': keyboard,
                'one_time_keyboard': True,
                'resize_keyboard': True
            }
        else:
            show_keyboard = None

        logger.info('sending next question to {user}'.format(user=user.name))
        self.bot.sendMessage(
            chat_id, q.text,
            disable_web_page_preview=True,
            reply_markup=show_keyboard
        )

    def read_user_message(self, msg):
        return msg['text']

    def get_chat_id(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        return chat_id

    def get_chat_id_inline(self, msg):
        _, chat_id, _ = telepot.glance(msg, flavor='callback_query')
        return chat_id

    def get_payload(self, msg):
        _, _, payload = telepot.glance(msg, flavor='callback_query')
        return payload

    def vote_done(self, msg, fragment_id, question_id):
        query_id, chat_id, _ = telepot.glance(msg, flavor='callback_query')
        self.bot.answerCallbackQuery(query_id, text='Got it')
        inline_message_id = (chat_id, msg['message']['message_id'])
        self.bot.editMessageReplyMarkup(
            inline_message_id,
            self.get_poll_keyboard(fragment_id, question_id))

    def vote_skip(self, msg):
        query_id, _, _ = telepot.glance(msg, flavor='callback_query')
        self.bot.answerCallbackQuery(query_id, text='you already voted')

    def get_answers_keyboard(self, answers):
        show_keyboard = {
            'keyboard': [
                [Emoji.shortcode_to_unicode(f.text)] for f in answers
            ],
            'one_time_keyboard': True,
            'resize_keyboard': True
        }
        return show_keyboard

    def handle_message(self, msg):
        """ handle telegram specific errors """
        try:
            super(TelegramBot, self).handle_message(msg)
        except telepot.exception.BotWasBlockedError:
            _, _, chat_id = telepot.glance(msg)
            user = self.process_user(chat_id, msg)
            user.disabled = 1
            user.save()

            logger.info('User block account.id=%s' % str(self.account.pk))

    def start(self):
        self.bot.message_loop({'chat': self.handle_message,
                               'callback_query': self.handle_callback_query})

        while 1:
            time.sleep(self.CHECK_NEW_BULLETINS_INTERVAL)
            self.sending_published_bulletins()


@click.command()
@click.argument('account_id')
def main(account_id):
    app = create_app()

    with app.app_context():
        b = TelegramBot(account_id)
        b.bot.setWebhook('')
        b.start()


if __name__ == '__main__':
    main()
