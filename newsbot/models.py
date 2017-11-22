from datetime import datetime, timedelta
from pytz import timezone, utc
from operator import attrgetter

import mongoengine
from mongoengine import signals

from flask_login import UserMixin
from flask import render_template

from .extensions import db
from .timezones import TIMEZONES


# - Bulletin
# - Id (object_id)
# - Published (datetime)
# - Breaking (boolean)
# - Content (array of stories)
#
# - Story
# - id (object_id)
# - Lead (text)
# - Priority (integer) (default 0)
# - Bulletin_id
# - Content (array of fragments)
#
# - Fragment
# - Type (string) can be: (paragraph, answer, image)
# - Text (string) stores main text for this fragment:(paragraph or answer)
# - URL (url) (link or image)
# - Story_id

class PollQuestions(db.Document):
    text = db.StringField(required=True)
    fragment = db.ReferenceField('Fragment', required=True)
    users = db.ListField(db.IntField())
    order = db.IntField(required=True, default=0)

    meta = {
        'ordering': ['order'],
        'strict': False
    }


class BaseFragment(db.Document):
    TYPE_PARAGRAPH = 'p'
    TYPE_ANSWER = 'a'
    TYPE_VIDEO = 'v'
    TYPE_DOCUMENT = 'd'
    TYPE_AUDIO = 'm'
    TYPE_IMAGE = 'i'
    TYPE_POLL = 'l'
    TYPE_QUESTION = 'q'
    TYPE_CHOICES = (
        (TYPE_PARAGRAPH, 'Paragraph'),
        (TYPE_ANSWER, 'Answer'),
        (TYPE_VIDEO, 'Video'),
        (TYPE_DOCUMENT, 'Document'),
        (TYPE_AUDIO, 'Audio'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_POLL, 'Poll'),
        (TYPE_QUESTION, 'Question')
    )

    ACTION_NEXT = 'n'
    ACTION_CONTINUE = 'c'
    ACTION_CHOICES = (
        (ACTION_CONTINUE, 'Continue with current story'),
        (ACTION_NEXT, 'Jump to next story'),
    )

    type = db.StringField(required=True, choices=TYPE_CHOICES)
    text = db.StringField()
    url = db.URLField()
    order = db.IntField(required=True)
    action = db.StringField(required=False, choices=ACTION_CHOICES)

    num_readers = db.IntField(default=0)

    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    meta = {
        'ordering': ['order'],
        'strict': False,
        'abstract': True
    }


    @property
    def action_desc(self):
        return dict(self.ACTION_CHOICES)[self.action]

    @property
    def get_poll_questions(self):
        return [i.text for i in PollQuestions.objects(fragment=self.id)]

    def render_fragment(self):
        if self.type == self.TYPE_ANSWER:
            template_src = 'includes/story-bubble-answer.html'
            f = self.story.content_ordered_grouped[-1]
        else:
            template_src = 'includes/story-bubble.html'
            f = self

        return render_template(
            template_src, f=f, story=self.story,
            sid=self.story.id, fragment=self.__class__
        )


class Fragment(BaseFragment):
    story = db.ReferenceField('Story')


class ProfileStoryFragment(BaseFragment):
    story = db.ReferenceField('ProfileStory')
    attribute = db.ReferenceField('ChatUserAttribute', required=False)


class Story(db.Document):
    title = db.StringField(verbose_name='Title', max_length=250, required=True)
    lead = db.StringField(verbose_name='Lead', required=True)
    bulletin = db.ReferenceField('Bulletin')
    readers = db.ListField(
        db.ReferenceField('ChatUser')
    )
    order = db.IntField(required=True)
    content = db.ListField(
        db.ReferenceField(Fragment, reverse_delete_rule=mongoengine.PULL)
    )

    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    meta = {
        'ordering': ['order'],
        'strict': False
    }

    def __str__(self):
        return self.title

    @property
    def content_ordered(self):
        return sorted(self.content, key=attrgetter('order'))

    @property
    def content_ordered_grouped(self):
        ret = []
        for f in self.content_ordered:
            if f.type == Fragment.TYPE_ANSWER:
                if ret and isinstance(ret[-1], list):
                    ret[-1].append(f)
                else:
                    ret.append([f])
            else:
                ret.append(f)

        return ret


class ProfileStory(db.Document):
    title = db.StringField()
    order  = db.IntField(default=0)
    lead = db.StringField(verbose_name='Lead', required=True)
    active = db.BooleanField(default=False)
    account = db.ReferenceField('Account')

    content = db.ListField(
        db.ReferenceField(
            ProfileStoryFragment,
            reverse_delete_rule=mongoengine.PULL
        )
    )
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    meta = {
        'ordering': ['order'],
        'strict': False
    }

    @property
    def content_ordered(self):
        return sorted(self.content, key=attrgetter('order'))

    @property
    def content_ordered_grouped(self):
        ret = []
        for f in self.content_ordered:
            if f.type == Fragment.TYPE_ANSWER:
                if ret and isinstance(ret[-1], list):
                    ret[-1].append(f)
                else:
                    ret.append([f])
            else:
                ret.append(f)

        return ret


class Bulletin(db.Document):
    title = db.StringField(verbose_name='Title', max_length=255, required=True)
    publish_at = db.DateTimeField(verbose_name='Published', required=True)
    is_breaking = db.BooleanField(verbose_name='Breaking', default=False)
    is_published = db.BooleanField(verbose_name='Publish', default=False,
                                   required=True)
    expire_hours = db.IntField(verbose_name='Expire in (hours)', required=True)
    content = db.ListField(
        db.ReferenceField(Story, reverse_delete_rule=mongoengine.PULL)
    )

    account = db.ReferenceField('Account')
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()
    pending = db.BooleanField(default=True)

    meta = {
        'ordering': ['publish_at'],
        'strict': False
    }

    @property
    def content_ordered(self):
        return sorted(self.content, key=attrgetter('order'))

    def __str__(self):
        return self.title

    @staticmethod
    def get_default_scheduled_date(datetime=datetime):
        """ Calculate default bulletin publish_at date """
        MIN_TO_NEXT_HOUR = 15

        curr_date = datetime.now(utc)
        new_date = curr_date + timedelta(hours=1, minutes=MIN_TO_NEXT_HOUR)

        return utc.localize(datetime(
            new_date.year, new_date.month, new_date.day, new_date.hour, 0, 0
        ))


class OptionsItem(db.EmbeddedDocument):
    text = db.StringField(required=False)
    value = db.StringField(required=False)


class AccountFacebookPage(db.EmbeddedDocument):
    id = db.StringField(required=True)
    access_token = db.StringField(required=True)
    name = db.StringField(required=True)


class ChatUserAttribute(db.Document):
    TYPE_INT = 'int'
    TYPE_FLOAT = 'float'
    TYPE_TEXT = 'text'
    TYPE_CHOICES = (
        (TYPE_INT, 'int'),
        (TYPE_FLOAT, 'float'),
        (TYPE_TEXT, 'text')
    )

    CHART_BAR = 'bars'
    CHART_PIE = 'pie'
    CHART_CHOICES = (
        (CHART_BAR, 'bars'),
        (CHART_PIE, 'pie'),
    )

    type = db.StringField(required=True, choices=TYPE_CHOICES)
    attribute = db.StringField()
    options = db.ListField(
        db.EmbeddedDocumentField(OptionsItem)
    )
    chart = db.StringField(required=True, choices=CHART_CHOICES, default=CHART_BAR)

    @staticmethod
    def is_numeric(text):
        try:
            float(text)
            return True
        except ValueError:
            return False

    def is_valid_answer(self, answer):
        if self.type == 'int':
            return True if answer.isdigit() else False
        elif self.type == 'float':
            return ChatUserAttribute.is_numeric(answer)
        else:
            return not ChatUserAttribute.is_numeric(answer)


class ChatUserAnswer(db.Document):
    answer = db.StringField()
    question = db.ReferenceField(
        ProfileStoryFragment, reverse_delete_rule=mongoengine.CASCADE
    )

    def clean(self):
        """Ensures that answer exist in question options and types are equal"""
        options = self.question.attribute.options
        if options:
            option = next(
                (o for o in options if o.text == self.answer),
                None
            )

            if option is None:
                raise mongoengine.ValidationError("Option not availible")
            else:
                self.answer = option.value

        if not self.question.attribute.is_valid_answer(self.answer):
            raise mongoengine.ValidationError("Not valid answer type")


class ChatUser(db.Document):
    STATE_INITIAL = 'initial'
    STATE_INITIAL_STAGE2 = 'initial_stage2'
    STATE_WAITING_READY = 'waiting_ready'
    STATE_READY_RECEIVED = 'ready_received'
    STATE_WAITING_ANSWER = 'waiting_answer'
    STATE_WAITING_POLL = 'waiting_poll'

    STATE_WAITING_PROFILE_ANSWER = 'waiting_profile_answer'
    STATE_WAITING_PROFILE_QUESTION = 'waiting_question'

    STATE_NORMAL = 'normal'
    ANSWER_READY = 'Yes!'


    name = db.StringField(required=True)
    chat_id = db.IntField(required=True)
    account_id = db.ReferenceField('Account', required=True, unique_with='chat_id')
    state = db.StringField()
    current_bulletin = db.ReferenceField(Bulletin)
    current_story_order = db.IntField(default=0)
    current_fragment_order = db.IntField(default=0)
    waiting = db.IntField(default=0)
    disable_no_content = db.IntField(default=0)
    onboarding = db.BooleanField(default=False)
    platform = db.StringField(required=True, choices=('telegram', 'facebook'), default='telegram')

    current_profile_story = db.ReferenceField(ProfileStory)
    current_profile_fragment_order = db.IntField(default=0)
    read_profile_stories = db.ListField(
        db.ReferenceField(
            ProfileStory,
            reverse_delete_rule=mongoengine.PULL
        ), default=list
    )
    question_answers = db.ListField(
        db.ReferenceField(
            ChatUserAnswer,
            reverse_delete_rule=mongoengine.PULL
        ), default=list
    )

    disabled = db.IntField()

    read_content = db.ListField(
        db.ReferenceField(Fragment, reverse_delete_rule=mongoengine.PULL)
    )

    read_bulletins = db.ListField(
        db.ReferenceField(Bulletin, reverse_delete_rule=mongoengine.PULL)
    )

    up_to_date_counter = db.IntField(default=0)

    last_message = db.DateTimeField(default=datetime.utcnow)
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    meta = {'strict': False}

    @staticmethod
    def get_enabled_users():
        """ Return amount of users with disabled=0 grouped by account """
        return ChatUser.objects.aggregate(*[
            {
                '$match': {'disabled': 0}
            },
            {
                '$group': { '_id': '$account_id', 'enabled_users': { '$sum': 1 }}
            }
        ])

    @staticmethod
    def on_user_disables_event(prev_user, new_user):
        if not prev_user and new_user.disabled == 1:
            AccountStats.update_dropped_users(new_user.account_id)
        elif not prev_user and new_user.disabled == 0:
            pass
        elif prev_user.disabled == 0 and new_user.disabled == 1:
            AccountStats.update_dropped_users(new_user.account_id)

    @staticmethod
    def on_user_active_event(prev_user, new_user):
        today = datetime.utcnow().date()
        if not prev_user:
            AccountStats.update_active_users(new_user.account_id)
        elif prev_user.last_message.date() != new_user.last_message.date():
            AccountStats.update_active_users(new_user.account_id)
        else:
            pass

    @staticmethod
    def on_new_user_event(prev_user, new_user):
        if not prev_user:
            AccountStats.update_new_users(new_user.account_id)
        else:
            pass

    @classmethod
    def pre_save(cls, sender, document, **kwargs):
        # Called within save() after validation
        # has taken place but before saving.
        if not document.id:
            prev_document = None
        else:
            prev_document = ChatUser.objects(id=document.id).first()

        ChatUser.on_user_disables_event(prev_document, document)
        ChatUser.on_user_active_event(prev_document, document)
        ChatUser.on_new_user_event(prev_document, document)

signals.pre_save_post_validation.connect(ChatUser.pre_save, sender=ChatUser)


class InformationMessage(db.Document):
    TYPE_INFORMATION = 'im'
    TYPE_QUESTION = 'qm'
    TYPE_CHOICES = (
        (TYPE_INFORMATION, 'Information'),
        (TYPE_QUESTION, 'Question')
    )
    type = db.StringField(required=True, choices=TYPE_CHOICES)
    text = db.StringField()
    options = db.ListField(
        db.StringField()
    )
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()


class BulletinChatUser(db.Document):
    # ADD DATE
    bulletin = db.ReferenceField('Bulletin')
    chat_user = db.ReferenceField('ChatUser')
    timestamp = db.DateTimeField(default=datetime.utcnow)
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()


class InformationMessageChatUser(db.Document):
    # ADD DATE
    information_message = db.ReferenceField('InformationMessage')
    chat_user = db.ReferenceField('ChatUser')
    timestamp = db.DateTimeField(default=datetime.utcnow)
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()


class AccountStats(db.Document):
    # users with disabled = False
    enabled_users = db.IntField(required=True)
    # user that send a mesage for a given day
    active_users = db.IntField(required=True, default=0)
    # users that where disabled for a given day
    dropped_users = db.IntField(required=True, default=0)
    # users that signed for a given day
    new_users = db.IntField(required=True, default=0)
    messages_received = db.IntField(required=True, default=0)

    date = db.DateTimeField(required=True, default=datetime.utcnow().date,
        unique_with='account')
    account = db.ReferenceField('Account')

    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    @staticmethod
    def get_today_stats(account):
        return AccountStats.objects(
            account=account,
            date=datetime.now().date()
        )

    @staticmethod
    def update_enabled_users(accounts):
        # bulk update with single query
        from pymongo import UpdateOne

        enabled_users = list(ChatUser.get_enabled_users())
        today = datetime.now()
        today = datetime(today.year, today.month, today.day)

        bulk_operations = []
        for _account in accounts:
            acc_enabled_users = next(
                (u['enabled_users'] for u in enabled_users if u['_id']==_account.id),
                0
            )
            print(str(_account.name) + " " + str(acc_enabled_users))
            bulk_operations.append(
                UpdateOne(
                    {'account': _account.id, 'date': today},
                    {'$set': {
                        'enabled_users': acc_enabled_users
                    }}, upsert=True
                )
            )

        if bulk_operations:
            return AccountStats._get_collection().\
                bulk_write(bulk_operations, ordered=False)
        else:
            return None

    @staticmethod
    def update_active_users(account):
        return AccountStats.get_today_stats(account).\
            update_one(inc__active_users=1, upsert=True)

    @staticmethod
    def update_dropped_users(account):
        return AccountStats.get_today_stats(account).\
            update_one(inc__dropped_users=1, upsert=True)

    @staticmethod
    def update_new_users(account):
        return AccountStats.get_today_stats(account).\
            update_one(inc__new_users=1, upsert=True)

    @staticmethod
    def update_messages_received(account):
        return AccountStats.get_today_stats(account).\
            update_one(inc__messages_received=1, upsert=True)


class Account(db.Document):
    UPTODATE_MESSAGE = 'You are up to date! We will send you more news shortly'
    AUDIENCE_CHOICES = (
        (100, 'About 100'),
        (1000, 'About 1000'),
        (10000, 'About 10000'),
    )
    TIMEZONES_CHOICES = TIMEZONES
    timezone = db.StringField(verbose_name='Timezone',choices=TIMEZONES_CHOICES,default='Europe/Amsterdam')
    name = db.StringField(verbose_name='Company', max_length=255,
                          required=True)
    audience = db.IntField(required=True, choices=AUDIENCE_CHOICES)
    botconnection_telegram_name = db.StringField(
        verbose_name='Telegram bot name', max_length=255, required=False)
    botconnection_telegram_token = db.StringField(
        verbose_name='Telegram token', max_length=255, required=False)
    botconnection_facebook_token = db.StringField(
        verbose_name='Facebook token', max_length=255, required=False)
    botconnection_facebook_page_id = db.StringField(
        verbose_name='Facebook Page ID', max_length=32, required=False)
    up_to_date_message = db.StringField(verbose_name='Up to date message',
                                        default=UPTODATE_MESSAGE,
                                        required=False)
    unknown_answer_message = db.StringField(verbose_name='Unknown answer message',
                                        default="¿?",
                                        required=False)

    welcome_message_1 = db.StringField(verbose_name='Welcome message 1', required=False, default="Hello! I am a bot!")
    welcome_message_2 = db.StringField(verbose_name='Welcome message 2', required=False, default="I will tell you about amazing things! you just need to click on the buttons below!")
    welcome_answer_1 = db.StringField(verbose_name="Answer 1", default="This one?")
    welcome_message_3 = db.StringField(verbose_name="Welcome message 3", default="Yeah! That one! Some times you will have two options, ready to start?")
    welcome_answer_2_option_1 = db.StringField(verbose_name="Answer 2 (option 1)", default="Hell yes!")
    welcome_answer_2_option_2 = db.StringField(verbose_name="Answer 2 (option 2)", default="Go go go!")
    skip_poll_message = db.StringField(default="No idea")

    bulletins = db.ListField(
        db.ReferenceField(Bulletin, reverse_delete_rule=mongoengine.PULL)
    )    
    chat_user_attributes = db.ListField(
        db.ReferenceField(ChatUserAttribute, reverse_delete_rule=mongoengine.PULL)
    )
    users = db.ListField(
        db.ReferenceField('User')
    )
    owner =  db.ReferenceField('User',required=False)
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    facebook_username  = db.StringField(max_length=64, required=False)
    facebook_pages = db.ListField(db.EmbeddedDocumentField(AccountFacebookPage))

    meta = {
        'strict': False,
        'indexes': [
            {
                'fields': ['botconnection_facebook_page_id'],
                'unique': True,
                'partialFilterExpression': {'botconnection_facebook_page_id': {'$gt': ''}}
            }
        ]
    }

    def __str__(self):
        return self.name


class User(UserMixin, db.Document):
    name = db.StringField(verbose_name='Name',required=True)
    email = db.StringField(verbose_name='Email',required=True, unique=True)
    password = db.StringField(required=True)
    role = db.StringField(required=True, default='admin')
    accounts = db.ListField(
        db.ReferenceField('Account')
    )
    created_at = db.DateTimeField()
    updated_at = db.DateTimeField()

    def get_id(self):
        """We use email as an unique User identifier in Flask-Login"""
        return self.email

    def __str__(self):
        return self.email


class Invitation(db.Document):
    code = db.StringField(verbose_name='Code', required=True, unique=True)
    text = db.StringField(verbose_name='Text', required=True)


Account.register_delete_rule(Bulletin, 'account', mongoengine.CASCADE)
Bulletin.register_delete_rule(Story, 'bulletin', mongoengine.CASCADE)
Story.register_delete_rule(Fragment, 'story', mongoengine.CASCADE)

User.register_delete_rule(Account, 'users', mongoengine.PULL)
Account.register_delete_rule(User, 'accounts', mongoengine.PULL)

Fragment.register_delete_rule(PollQuestions, 'fragment', mongoengine.CASCADE)
Account.register_delete_rule(AccountStats, 'account', mongoengine.CASCADE)
