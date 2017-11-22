import time
from abc import ABCMeta, abstractmethod
from urllib.request import urlopen
import datetime

import click
import telepot
from emojipy import Emoji

from newsbot.models import (
    Account,
    Bulletin,
    ChatUser,
    Fragment,
    Story
)
#from newsbot.server import create_app

from mongoengine import connect, register_connection
from settings import MONGODB_SETTINGS
register_connection(
    name=MONGODB_SETTINGS['db'],
    host=MONGODB_SETTINGS['host'],
    port=MONGODB_SETTINGS['port'],
    username=MONGODB_SETTINGS['username'],
    password=MONGODB_SETTINGS['password'],
    alias="default-mongodb-connection"
)


class BotBase(metaclass=ABCMeta):
    WELCOME_MESSAGES = [
        'Welcome to bulletins.chat!',
        ('We will show you a set of news, all you need to tell me if you need '
         'to continue with the story I am telling you or go to next story!')
    ]

    @abstractmethod
    def extract_username(self, msg):
        pass

    @abstractmethod
    def send_welcome(self, chat_id):
        pass

    @abstractmethod
    def validate_msg(self, msg):
        pass

    @abstractmethod
    def send_lead_answers(self, chat_id, lead, fragments):
        pass

    @abstractmethod
    def is_ready_message(self, msg):
        pass

    @abstractmethod
    def send_image_fragment(self, chat_id, f):
        pass

    @abstractmethod
    def send_text_fragment(self, chat_id, f):
        pass

    @abstractmethod
    def action_from_answer(self, user, msg):
        pass

    @abstractmethod
    def start(self):
        pass

    def get_or_create_user(self, name, chat_id):
        try:
            u = ChatUser.objects.get(chat_id=chat_id, account_id=self.account.id)
        except ChatUser.DoesNotExist:
            u = ChatUser(chat_id=chat_id, name=name,
                         state=ChatUser.STATE_INITIAL, account_id=self.account.id)
            u.save()

        return u

    @abstractmethod
    def validate_account(self, account_id):
        a = Account.objects.get(id=account_id)
        assert a.up_to_date_message, 'Please fill Account.up_to_date_message'

        return a

    @abstractmethod
    def process_no_content(self, user, chat_id):
        pass

    def get_unread_bulletins(self, user):
        return Bulletin.objects.filter(
            account=self.account,
            id__nin=[x.id for x in user.read_bulletins],
            is_published=True,
            publish_at__lte=datetime.datetime.now()
        )

    def start_bulletin_reading(self, user, chat_id, disable_no_content=False):
        bulletins = self.get_unread_bulletins(user)

        try:
            if not bulletins and disable_no_content:
                pass
            elif not bulletins:
                self.process_no_content(user, chat_id)
            else:
                b = bulletins[0]
                story = Story.objects.filter(
                    bulletin=b, order__gt=0).first()

                lead, answers = self.get_next_answers(story=story,
                                                      fragment_order=0)

                if lead is None or not answers:
                    self.process_no_content(user, chat_id)
                else:
                    user.current_bulletin = b
                    user.current_story_order = story.order
                    user.current_fragment_order = answers[-1].order
                    user.save()

                    self.send_lead_answers(chat_id, lead, answers)

                    user.current_fragment_order = answers[-1].order
                    user.state = ChatUser.STATE_WAITING_ANSWER
                    user.save()
        except telepot.exception.TelegramError:
            # chat_id not found
            pass

    def switch_next_bulletin(self, user, chat_id):
        if user.current_bulletin:
            user.read_bulletins.append(user.current_bulletin)
            user.current_bulletin = None
            user.save()

        self.start_bulletin_reading(user, chat_id)

    def switch_next_story(self, user, chat_id):
        b = user.current_bulletin
        order = user.current_story_order
        story = Story.objects.filter(bulletin=b, order__gt=order).first()

        if story is None:
            self.process_no_content(user, chat_id)
            return

        user.current_story_order = story.order
        user.current_fragment_order = 0
        user.save()

        lead, answers = self.get_next_answers(story=story,
                                              fragment_order=0)
        if lead is None or not answers:
            self.process_no_content(user, chat_id)
        else:
            self.send_lead_answers(chat_id, lead, answers)
            user.current_fragment_order = answers[-1].order
            user.save()

    def process_user(self, chat_id, msg):
        return self.get_or_create_user(self.extract_username(msg), chat_id)

    def is_last_story(self, bulletin, order):
        return Story.objects.filter(bulletin=bulletin,
                                    order__gt=order).count() == 0

    def get_next_answers(self, story, fragment_order):
        if story is None or not story.content:
            return None, []

        answers = []
        for f in Fragment.objects.filter(story=story,
                                         order__gt=fragment_order):

            if f.type == Fragment.TYPE_ANSWER:
                answers.append(f)
            else:
                break

        return story.lead, answers

    def send_rest_fragments(self, user, chat_id):
        answers = []
        others = []

        story = Story.objects.get(bulletin=user.current_bulletin,
                                  order=user.current_story_order)
        for f in Fragment.objects.filter(
                story=story,
                order__gt=user.current_fragment_order):

            if f.type != Fragment.TYPE_ANSWER and answers:
                break

            if f.type == Fragment.TYPE_ANSWER:
                answers.append(f)
            else:
                others.append(f)

        # Here we assume that we cannot get to this function and have answers
        # as first unread fragments
        for f in others:
            if f.type == Fragment.TYPE_IMAGE:
                self.send_image_fragment(chat_id, f)
            else:
                self.send_text_fragment(chat_id, f)

            user.current_fragment_order = f.order
            user.save()

        if answers:
            self.send_lead_answers(chat_id, story.lead, answers)
            user.current_fragment_order = answers[-1].order
            user.save()

        return len(answers)

    def handle_message(self, msg):
        if not self.validate_msg(msg):
            return

        content_type, chat_type, chat_id = telepot.glance(msg)

        user = self.process_user(chat_id, msg)

        if user.state == ChatUser.STATE_INITIAL:
            self.send_welcome(chat_id)
            user.state = ChatUser.STATE_INITIAL_STAGE2
            user.save()

        elif user.state == ChatUser.STATE_INITIAL_STAGE2:
            self.send_welcome_stage2(chat_id)
            user.state = ChatUser.STATE_WAITING_READY
            user.save()

        elif (user.state == ChatUser.STATE_WAITING_READY and
                self.is_ready_message(msg)):
            user.state = ChatUser.STATE_READY_RECEIVED
            user.save()

            if user.current_bulletin is None:
                self.start_bulletin_reading(user, chat_id)
            else:
                # What to do in this case ???
                pass

        elif user.state == ChatUser.STATE_READY_RECEIVED:
            self.start_bulletin_reading(user, chat_id)

        elif user.state == ChatUser.STATE_WAITING_ANSWER:
            action = self.action_from_answer(user, msg)

            # Switch to the next fragment with Continue response
            if action == Fragment.ACTION_CONTINUE:
                answers_sent = self.send_rest_fragments(user, chat_id)
                if not answers_sent:
                    if self.is_last_story(user.current_bulletin,
                                          user.current_story_order):
                        self.switch_next_bulletin(user, chat_id)
                    else:
                        self.switch_next_story(user, chat_id)

            else:
                if self.is_last_story(user.current_bulletin,
                                      user.current_story_order):
                    self.switch_next_bulletin(user, chat_id)
                else:
                    self.switch_next_story(user, chat_id)


class TelegramBot(BotBase):
    TYPING_TIME = 0.5
    CHECK_NEW_BULLETINS_INTERVAL = 60

    def __init__(self, account_id):
        self.account = self.validate_account(account_id)
        self.bot = telepot.Bot(self.account.botconnection_telegram_token)

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
        self.bot.sendChatAction(chat_id, 'typing')
        time.sleep(self.TYPING_TIME)
        self.account = Account.objects.get(id=self.account.id)
        self.bot.sendMessage(chat_id, self.account.welcome_message_1)

        self.bot.sendChatAction(chat_id, 'typing')
        time.sleep(self.TYPING_TIME)
        self.bot.sendMessage(
            chat_id,
            self.account.welcome_message_2,
            reply_markup={'keyboard': [[self.account.welcome_answer_1]],
                          'one_time_keyboard': True,
                          'resize_keyboard': True},
            disable_web_page_preview=True
        )

    def send_welcome_stage2(self, chat_id):
        self.bot.sendChatAction(chat_id, 'typing')
        time.sleep(self.TYPING_TIME)
        self.account = Account.objects.get(id=self.account.id)
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

    def sending_published_bulletins(self):
        # fetch all users subscribed to account
        users = ChatUser.objects.filter(
            account_id=self.account.id
        )

        for user in users:
            self.start_bulletin_reading(user, user.chat_id, True)


    def process_no_content(self, user, chat_id):
        super(TelegramBot, self).process_no_content(user, chat_id)

        self.bot.sendChatAction(chat_id, 'typing')
        time.sleep(self.TYPING_TIME)
        up_to_date_message = Account.objects.get(id=self.account.id).\
            up_to_date_message

        self.bot.sendMessage(chat_id, up_to_date_message)

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

        self.bot.sendChatAction(chat_id, 'typing')
        time.sleep(self.TYPING_TIME)

        self.bot.sendMessage(chat_id, lead,
                             reply_markup=show_keyboard,
                             disable_web_page_preview=True)

    def send_image_fragment(self, chat_id, f):
        self.bot.sendPhoto(chat_id, (u'image.jpg', urlopen(f.url)))

    def send_text_fragment(self, chat_id, f):
        self.bot.sendMessage(
            chat_id,
            Emoji.shortcode_to_unicode(f.text),
            disable_web_page_preview=True
        )

    def is_ready_message(self, msg):
        return msg['text'] in [
            self.account.welcome_answer_2_option_1,
            self.account.welcome_answer_2_option_2
        ]

    def action_from_answer(self, user, msg):
        s = Story.objects.filter(bulletin=user.current_bulletin,
                                 order=user.current_story_order).first()
        if s is None:
            return

        f = Fragment.objects.filter(
            story=s, text=Emoji.unicode_to_shortcode(msg['text'])).first()

        if f is None:
            return

        return f.action

    def start(self):
        self.bot.message_loop(self.handle_message)

        while 1:
            time.sleep(self.CHECK_NEW_BULLETINS_INTERVAL)
            self.sending_published_bulletins()


@click.command()
@click.argument('account_id')
def main(account_id):
    app = create_app()

    with app.app_context():
        b = TelegramBot(account_id)
        b.start()


if __name__ == '__main__':
    main()
