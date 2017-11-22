#!/usr/bin/env python

import datetime
from flask import url_for
from newsbot.models import Account, User, Bulletin, Story, Fragment, ChatUser, PollQuestions
from newsbot.models import (
    Account, User, Bulletin,
    Story, Fragment, ChatUser,
    ChatUserAttribute, OptionsItem,
    ChatUserAnswer, ProfileStoryFragment,
    ProfileStory)

from newsbot.helpers import encrypt_password

from flask import template_rendered
from contextlib import contextmanager

from io import BytesIO
import uuid

def objs_to_ids(objs):
    return {o.id for o in objs}


class TestBase:

    register_data = {
        'name': 'user',
        'email': 'user@domain.com',
        'password': 'password',
        'account-name': 'ACCOUNT',
        'account-audience': 100,
        'account-timezone': 'Africa/Abidjan'
    }

    utcnow = datetime.datetime.utcnow().replace(second=0, microsecond=0)
    default_chat_id = 1234

    def create_user_account(self):
        u = User(name=self.register_data['name'],
                 email=self.register_data['email'],
                 password=encrypt_password(self.register_data['password']))

        a = Account(name=self.register_data['account-name'],
                    audience=self.register_data['account-audience'],
                    timezone=self.register_data['account-timezone'],
                    up_to_date_message='You are up to date!',
                    botconnection_telegram_name='bot',
                    botconnection_telegram_token=uuid.uuid4().hex,
                    botconnection_facebook_token=uuid.uuid4().hex,
                    botconnection_facebook_page_id=uuid.uuid4().hex,
                    welcome_message_1='Welcome message 1',
                    welcome_message_2='Welcome message 2',
                    welcome_message_3='Welcome message 3',
                    welcome_answer_1='Answer 1',
                    welcome_answer_2_option_1='Answer 2 (option 1)',
                    welcome_answer_2_option_2='Answer 2 (option 2)')
        u.save()
        a.save()

        u.accounts.append(a)
        a.owner = u
        a.users.append(u)

        u.save()
        a.save()

        return (u, a)

    def create_bulletin(self, account, *,
                              title='bulletin1',
                              publish_at=None,
                              is_published=False,
                              expire_hours=12):

        if publish_at is None:
            publish_at = self.utcnow

        bulletin = Bulletin(account=account,
                            title=title,
                            publish_at=publish_at,
                            is_published=is_published,
                            expire_hours=expire_hours)
        bulletin.save()

        account.bulletins.append(bulletin)
        account.save()

        return bulletin

    def create_story(self, bulletin, *, title='story1', lead='lead1'):

        story = Story(title=title,
                      lead=lead,
                      bulletin=bulletin,
                      order=len(bulletin.content) + 1)
        story.save()

        bulletin.content.append(story)
        bulletin.save()

        return story

    def create_fragment_answer(self, story, *, action='c', text='continue'):

        f = Fragment(action=action,
                     text=text,
                     story=story,
                     type=Fragment.TYPE_ANSWER,
                     order=len(story.content) + 1)
        f.save()

        story.content.append(f)
        story.save()

        return f

    def create_fragment_paragraph(self, story, *, text='paragraph1'):

        f = Fragment(text=text,
                     story=story,
                     type=Fragment.TYPE_PARAGRAPH,
                     order=len(story.content) + 1)
        f.save()

        story.content.append(f)
        story.save()

        return f

    def create_fragment_poll(self, story, *, text='question', answers=None):

        if not answers:
            answers = ['answer1', 'answer2']

        f = Fragment(text=text,
                     story=story,
                     type=Fragment.TYPE_POLL,
                     order=len(story.content) + 1)
        f.save()

        for a in answers:
            PollQuestions(text=a, fragment=f).save()

        story.content.append(f)
        story.save()

        return f

    def create_chat_user(self, account, platform='telegram'):
        return ChatUser(chat_id=self.default_chat_id,
                        name='Johm Smith',
                        state=ChatUser.STATE_WAITING_READY,
                        account_id=account.id,
                        disabled=0,
                        platform=platform).save()

    def create_chat_user_attribute(self, account, attribute, type, chart, options):
        attr = ChatUserAttribute(
            attribute=attribute,
            type=type, chart=chart,
            options=options
        ).save()

        account.chat_user_attributes.append(attr)
        account.save()

        return attr

    def create_question_fragment(self, attribute, text, story, order=1):
        return ProfileStoryFragment(
            type=ProfileStoryFragment.TYPE_QUESTION,
            story=story, text=text,
            attribute=attribute, order=order
        ).save()

    def create_profile_story(self, story_title, account, active=True):
        """
            Create simple profile story with answer
        """
        story = ProfileStory(
            title=story_title, lead=story_title,
            account=account, active=active,
            order=ProfileStory.objects(account=account).count() + 1
        ).save()

        answer_next = ProfileStoryFragment(
            action=ProfileStoryFragment.ACTION_NEXT,
            text='next',
            story=story,
            type=ProfileStoryFragment.TYPE_ANSWER,
            order=len(story.content) + 1
        ).save()
        story.content.append(answer_next)
        story.save()

        answer_continue = ProfileStoryFragment(
            action=ProfileStoryFragment.ACTION_CONTINUE,
            text='continue',
            story=story,
            type=ProfileStoryFragment.TYPE_ANSWER,
            order=len(story.content) + 1
        ).save()
        story.content.append(answer_continue)
        story.save()

        return story

    def add_question_fragment(self, story, question_fragment):
        """ add question fragment to the story"""
        question_fragment.order = len(story.content) + 1
        question_fragment.save()

        story.content.append(question_fragment)
        story.save()

    def create_answer(self, question, answer, chat_user):
        answer = ChatUserAnswer(
            question=question,
            answer=answer
        ).save()

        chat_user.question_answers.append(answer)
        chat_user.save()

        return answer

    def create_test_file(self, filename):
        file = BytesIO(b'simple test file')
        file.name = filename
        file.seek(0)
        return file

    def login(self, client):

        data = dict(email=self.register_data['email'],
                    password=self.register_data['password'])
        return client.post(url_for('auth.login'), data=data, follow_redirects=True)


    def get_telegram_message(self, text='/start', chat_id=default_chat_id):
        return {
            'text': text,
            'from': {'last_name': 'Smith', 'first_name': 'John', 'id': chat_id},
            'chat': {'type': 'private', 'last_name': 'Smith', 'first_name': 'John', 'id': chat_id},
            'message_id': 1, 'date': 1480434700
        }

    def get_telegram_callback_query(self, data=None):

        return {
            'chat_instance': '-2152528069103121155',
            'data': data,
            'from': {'first_name': 'John', 'id': self.default_chat_id, 'last_name': 'Smith'},
            'id': '485827301083906467',
            'message': {'chat': {'first_name': 'John',
                              'id': self.default_chat_id,
                              'last_name': 'Smith',
                              'type': 'private'},
                     'date': 1485956954,
                     'from': {'first_name': 'leadsbot_test',
                              'id': 242433175,
                              'username': 'test_leadsbot'},
                     'message_id': 1,
                     'text': 'some text'}
        }

    @contextmanager
    def captured_context(self, app):
        recorded = []
        def record(sender, template, context, **extra):
            recorded.append(context)

        # This signal is sent when a template was successfully rendered.
        # The signal is invoked with the instance of the template as
        # template and the context as dictionary (named context).
        template_rendered.connect(record, app)
        try:
            yield recorded
        finally:
            template_rendered.disconnect(record, app)

    def get_facebook_message(self, text='/start', chat_id=default_chat_id):

        return {'message': {'mid': 'mid.$cAAZ4_mwcpl5hT4IEb1bHjy8IDcUT',
                            'seq': 6945,
                            'text': text},
                'recipient': {'id': '1821882878075915'},
                'sender': {'id': chat_id},
                'timestamp': 1490860948591
        }

    def get_facebook_callback_query(self, data=None):

        return {'postback': {'payload': data},
                'recipient': {'id': '1821882878075915'},
                'sender': {'id': self.default_chat_id},
                'timestamp': 1490866780952
        }
