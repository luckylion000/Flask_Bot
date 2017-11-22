#!/usr/bin/env python

import datetime
import pytest
from flask import url_for
from pytz import timezone, utc
from newsbot.models import (
    Account, User, Bulletin, Story, PollQuestions, ChatUser,
    Fragment, ChatUserAttribute, ChatUserAnswer, AccountStats,
    Invitation, ProfileStory, ProfileStoryFragment)

from wtforms import validators
from telegrambot import TelegramBot
from helpers import objs_to_ids, TestBase


class TestWeb(TestBase):

    def test_account_create(self, client):
        " test create multiple accounts related to one user "

        self.create_user_account()
        self.login(client)

        resp = client.get(url_for('auth.account_create'))
        # check if default timezone selected
        selected = '<option selected value="{tz}">'.\
            format(tz=Account.timezone.default)
        assert selected in resp.data.decode('utf-8')

        N = 5

        for i in range(N):

            data = dict(name='ACCOUNT-%d' % i,
                        audience='100',
                        timezone='Africa/Abidjan')

            client.post(url_for('auth.account_create'), data=data)

        assert User.objects.count() == 1
        assert Account.objects.count() == N + 1

        current_user = User.objects.get()

        assert objs_to_ids(current_user.accounts) == objs_to_ids(Account.objects())

        for a in Account.objects:
            assert a.owner == current_user
            assert set([current_user.id]) == objs_to_ids(a.users)


    def test_add_bulletin(self, client, app):
        " new bulletin has to be always non-published "

        self.register_data['account-timezone'] = 'America/New_York'
        (user, account) = self.create_user_account()
        self.login(client)

        class fake_datetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return utc.localize(
                    datetime.datetime(2000, 1, 1, 4, 48, 0)
                )

        Bulletin.get_default_scheduled_date.__defaults__ = (fake_datetime,)
        client.post(url_for('index.bulletins_add'), data={})

        assert Bulletin.objects.count() == 1
        bulletin = Bulletin.objects.get()
        t = timezone(self.register_data['account-timezone'])
        # publish_at saved in utc, title saved in user timezone
        fmt = app.config['BULLETIN_NEW_TITLE_FORMAT']
        publish_at = utc.localize(bulletin.publish_at)
        assert bulletin.title == publish_at.\
            astimezone(t).strftime(fmt)
        assert bulletin.expire_hours == app.config['BULLETIN_EXPIRE_HOURS']
        assert bulletin.is_published == False
        assert bulletin.publish_at == datetime.datetime(2000, 1, 1, 6, 0, 0)
        assert len(bulletin.content) == 0
        assert bulletin.account == account

        account.reload()
        assert objs_to_ids(account.bulletins) == set([bulletin.id])


    def test_add_story(self, client, app):

        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        self.login(client)
        tz = timezone(account.timezone)

        client.post(url_for('index.stories_add', bid=str(bulletin.id)))
        assert Story.objects.count() == 1
        story = Story.objects.get()
        assert story.title == datetime.datetime.now(utc).\
            astimezone(tz).strftime(
                app.config['BULLETIN_NEW_TITLE_FORMAT']
            )
        assert story.lead == ''
        assert story.bulletin.id == bulletin.id
        assert len(story.readers) == 0
        assert story.order == 1
        assert len(story.content) == 0

        bulletin.reload()
        assert objs_to_ids(bulletin.content) == set([story.id])


    def test_add_fragments(self, client, tmpdir):

        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        story = self.create_story(bulletin)

        self.login(client)

        with pytest.raises(validators.ValidationError) as excinfo:
            data = dict(text='paragraph 1')
            client.post(url_for('index.stories_paragraph_add', sid=str(story.id)), data=data)
        # assert 'First fragment must be an Answer' ?

        data = dict(text='continue', action='c')
        client.post(url_for('index.stories_answer_add', sid=str(story.id)), data=data)

        assert Fragment.objects.count() == 1
        fragment = Fragment.objects.get()
        assert fragment.type == 'a'
        assert fragment.text == 'continue'
        assert fragment.action == 'c'
        assert fragment.story == story
        assert fragment.order == 1
        assert fragment.num_readers == 0

        data = dict(text='paragraph 1')
        client.post(url_for('index.stories_paragraph_add', sid=str(story.id)), data=data)

        assert Fragment.objects.count() == 2
        fragment = Fragment.objects[1:][0]
        assert fragment.text == 'paragraph 1'
        assert fragment.type == 'p'
        assert fragment.order == 2
        assert fragment.story == story
        assert fragment.num_readers == 0

        # testing media fragments
        client.post(
            url_for('index.stories_media_add', sid=str(story.id)),
            data={
                'text': 'my image',
                'media': self.create_test_file('image.jpg')
            }
        )
        assert Fragment.objects.count() == 3
        assert Fragment.objects(type=Fragment.TYPE_IMAGE).count() == 1

        client.post(
            url_for('index.stories_media_add', sid=str(story.id)),
            data={
                'text': 'my text',
                'media': self.create_test_file('doc.txt')
            }
        )
        assert Fragment.objects.count() == 4
        assert Fragment.objects(type=Fragment.TYPE_DOCUMENT).count() == 1

        client.post(
            url_for('index.stories_media_add', sid=str(story.id)),
            data={
                'text': 'my video',
                'media': self.create_test_file('video.mkv')
            }
        )
        assert Fragment.objects.count() == 5
        assert Fragment.objects(type=Fragment.TYPE_VIDEO).count() == 1

        client.post(
            url_for('index.stories_media_add', sid=str(story.id)),
            data={
                'text': 'my audio',
                'media': self.create_test_file('audio.mp3')
            }
        )
        assert Fragment.objects.count() == 6
        assert Fragment.objects(type=Fragment.TYPE_AUDIO).count() == 1

    def test_bulletin_edit(self, client):
        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        self.login(client)

        data = dict(title='bulletin1_edit',
            publish_at=self.utcnow.strftime('%m/%d/%Y %H:%M'),
            expire_hours='12',
        )

        resp = client.post(
            url_for('index.bulletins_edit',
            bid=str(bulletin.id)), data=data
        )

        bulletin.reload()
        t = timezone(account.timezone)

        assert utc.localize(bulletin.publish_at) ==\
            t.localize(self.utcnow).astimezone(utc)
        assert bulletin.title == 'bulletin1_edit'


    def test_bulletin_publish(self, client):
        " try to publish bulletin "

        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)

        story = self.create_story(bulletin)
        self.create_fragment_answer(story)

        t = timezone(account.timezone)
        self.login(client)

        publish_at = self.utcnow - datetime.timedelta(hours=1)

        data = dict(title='bulletin1_update',
            publish_at=publish_at.strftime('%m/%d/%Y %H:%M'),
            expire_hours='12',
        )

        client.post(url_for('index.bulletins_publish',
            bid=str(bulletin.id)), data=data
        )
        bulletin.reload()

        assert utc.localize(bulletin.publish_at) ==\
            t.localize(publish_at).astimezone(utc)
        assert bulletin.title == 'bulletin1_update'
        assert bulletin.is_published == True

        # could't edit/delete stories in published bulletin
        resp = client.post(url_for('index.stories_edit',
            sid=str(story.id)), data={'lead': 'new_lead', 'title': story.title}
        )
        story.reload()
        assert resp.status_code == 302
        assert resp.location == url_for('index.bulletins_list', _external=True)
        assert story.lead != 'new_lead'

        resp = client.post(url_for('index.stories_delete',
            sid=str(story.id)), data={}
        )
        assert resp.status_code == 302
        assert resp.location == url_for('index.bulletins_list', _external=True)
        assert Story.objects(bulletin=bulletin).count() == 1

        # unpublish bulletin
        client.post(url_for('index.bulletins_unpublish',
            bid=str(bulletin.id)), data={}
        )
        client.post(url_for('index.stories_delete',
            sid=str(story.id)), data={}
        )
        bulletin.reload()

        assert bulletin.is_published == False
        assert Story.objects(bulletin=bulletin).count() == 0

    def test_published_expired(self, client):
        """
        test bot.get_unread_bulletins return only published bulletins
        where publish_at <= now < publish_at + expire_hours
        """

        (user, account) = self.create_user_account()

        dates = (self.utcnow - datetime.timedelta(hours=4),
                 self.utcnow - datetime.timedelta(hours=1),
                 self.utcnow + datetime.timedelta(hours=2))

        for i in range(3):

            bulletin = self.create_bulletin(
                account,
                title='bulletin-%d' % i,
                publish_at=dates[i].strftime('%m/%d/%Y %H:%M'),
                is_published=True,
                expire_hours=2)

        user.read_bulletins = []
        user.save()

        bot = TelegramBot(str(account.id))
        bulletins = bot.get_unread_bulletins(user)
        assert len(bulletins) == 1
        assert bulletins[0].title == 'bulletin-1'

    def test_add_poll(self, client):

        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        story = self.create_story(bulletin)
        self.create_fragment_answer(story)

        self.login(client)

        data = {
            'text': 'Who is next president of USA ?',
            'question-0': 'Trump',
            'question-1': 'Hillary',
            'question-2': 'No idea',
        }

        client.post(url_for('index.stories_poll_add', sid=str(story.id)), data=data)

        assert Fragment.objects.count() == 2

        fragment = Fragment.objects[1]
        assert fragment.text == data['text']
        assert fragment.type == 'l'
        assert fragment.order == 2
        assert fragment.story == story

        assert PollQuestions.objects.count() == 3
        assert PollQuestions.objects[0].text == data['question-0']
        assert PollQuestions.objects[0].fragment == fragment
        assert PollQuestions.objects[0].order == 0
        assert PollQuestions.objects[1].text == data['question-1']
        assert PollQuestions.objects[1].fragment == fragment
        assert PollQuestions.objects[1].order == 1
        assert PollQuestions.objects[2].text == data['question-2']
        assert PollQuestions.objects[2].fragment == fragment
        assert PollQuestions.objects[2].order == 2

    def test_user_profiling_attribute(self, client):
        (user, account) = self.create_user_account()
        self.login(client)
        # create attribute
        data = {
            'attribute': 'attribute1',
            'chart': 'pie',
            'type': 'int',
            'options-0-text': '1',
            'options-0-value': '1',
            'options-1-text': '2',
            'options-1-value': '2',
        }
        response = client.post(url_for(
            'index.user_profiling_attribute_add',
        ), data=data)

        attr = ChatUserAttribute.objects().first()
        assert response.status_code == 302
        assert ChatUserAttribute.objects().count() == 1
        assert attr.attribute == data['attribute']

        import copy
        not_valid_data = copy.deepcopy(data)
        not_valid_data['chart'] = 'multi-line'
        not_valid_data['type'] = 'list'

        response = client.post(url_for(
            'index.user_profiling_attribute_add',
        ), data=not_valid_data)

        assert 'Not a valid choice' in response.data.decode('utf-8')
        assert ChatUserAttribute.objects().count() == 1

        # edit attribute
        data['attribute'] = 'attribute1_edited'
        data['options-2-text'] = '3'
        data['options-2-value'] = '3'

        response = client.post(url_for(
            'index.user_profiling_attribute_edit', aid=attr.id
        ), data=data)

        attr.reload()
        assert attr.attribute == data['attribute']
        assert len(attr.options) == 3
        assert ChatUserAttribute.objects().count() == 1

        # delete attribute
        response = client.post(url_for(
            'index.user_profiling_attribute_delete', aid=attr.id
        ))
        assert ChatUserAttribute.objects().count() == 0

        response = client.post(url_for(
            'index.user_profiling_attribute_delete', aid=1
        ))
        assert response.status_code == 404

    def test_user_profile_stories(self, client):
        (user, account) = self.create_user_account()
        self.login(client)

        attr = ChatUserAttribute(
            attribute='attr1',
            type='int', chart='pie',
            options=[
                {"text": "1", "value": "1" },
                {"text": "2", "value": "2" }
            ]
        ).save()

        # create draft profile story
        response = client.get(url_for(
            'index.user_profiling_stories_add',
        ))

        profile_story = ProfileStory.objects().first()
        assert ProfileStory.objects().count() == 1
        assert response.status_code == 302
        assert url_for(
            'index.user_profiling_stories_edit',
            sid=profile_story.id
        ) in response.location

        # add profile fragments
        client.post(url_for(
            'index.profile_stories_answer_add',
            sid=profile_story.id
        ), data={
            'text': 'answer#1',
            'action': ProfileStoryFragment.ACTION_CONTINUE
        })

        profile_story.reload()
        assert len(profile_story.content) == 1
        assert ProfileStoryFragment.objects(
            type=ProfileStoryFragment.TYPE_ANSWER
        ).count() == 1

        client.post(url_for(
            'index.profile_stories_question_add',
            sid=profile_story.id
        ), data={
            'text': 'question#1',
            'attribute': attr.id
        })

        profile_story.reload()
        assert len(profile_story.content) == 2
        assert ProfileStoryFragment.objects(
            type=ProfileStoryFragment.TYPE_QUESTION
        ).count() == 1

        client.post(url_for(
            'index.profile_stories_paragraph_add',
            sid=profile_story.id
        ), data={'text': 'paragraph#1'})

        profile_story.reload()
        assert len(profile_story.content) == 3
        assert ProfileStoryFragment.objects(
            type=ProfileStoryFragment.TYPE_PARAGRAPH
        ).count() == 1

    def test_user_profile_stories_edit(self, client):
        self.test_user_profile_stories(client)

        profile_story = ProfileStory.objects().first()
        attr2 = ChatUserAttribute(
            attribute='attr2',
            type='int', chart='pie',
            options=[]
        ).save()

        # update question fragment
        q = ProfileStoryFragment.objects(
            type=ProfileStoryFragment.TYPE_QUESTION).first()
        resp = client.put(url_for(
            'index.profile_stories_fragment_update', fid=q.id
        ), data={
            'text': q.text, 'attribute': attr2.id
        })

        q.reload()
        assert q.attribute == attr2

        # profile story fragments ordering
        fragments = ProfileStoryFragment.objects()
        assert fragments[0].order == 1
        assert fragments[1].order == 2
        assert fragments[2].order == 3

        data = {
            'objects-0-object_id': str(fragments[0].id),
            'objects-0-order': '2',
            'objects-1-object_id': str(fragments[1].id),
            'objects-1-order': '3',
            'objects-2-object_id': str(fragments[2].id),
            'objects-2-order': '1',
        }

        client.post(url_for(
            'index.profile_stories_order_fragments',
            sid=profile_story.id
        ), data=data)

        assert ProfileStoryFragment.objects.get(id=data['objects-2-object_id']).order == 1
        assert ProfileStoryFragment.objects.get(id=data['objects-0-object_id']).order == 2
        assert ProfileStoryFragment.objects.get(id=data['objects-1-object_id']).order == 3

    def test_user_profile_stories_list_page(self, client):
        (user, account) = self.create_user_account()
        self.login(client)

        # story #1
        client.get(url_for(
            'index.user_profiling_stories_add',
        ))
        # story #2
        client.get(url_for(
            'index.user_profiling_stories_add',
        ))
        # story #3
        client.get(url_for(
            'index.user_profiling_stories_add',
        ))

        # test profile story ordering
        stories = ProfileStory.objects()
        data = {
            'objects-0-object_id': str(stories[0].id),
            'objects-0-order': '3',
            'objects-1-object_id': str(stories[1].id),
            'objects-1-order': '2',
            'objects-2-object_id': str(stories[2].id),
            'objects-2-order': '1',
        }

        client.post(url_for(
            'index.profile_stories_order',
        ), data=data)

        assert ProfileStory.objects.get(id=data['objects-2-object_id']).order == 1
        assert ProfileStory.objects.get(id=data['objects-1-object_id']).order == 2
        assert ProfileStory.objects.get(id=data['objects-0-object_id']).order == 3

        # test activate/deactivate profile stories
        assert ProfileStory.objects(active=False).count() == 3

        client.put(
            url_for(
                'index.profile_story_activate_ajax',
                sid=stories[0].id
            ),
            data={'active': True},
            headers=[('X-Requested-With', 'XMLHttpRequest')]
        )

        assert ProfileStory.objects(active=False).count() == 2
        assert stories[0].active == True

        client.put(
            url_for(
                'index.profile_story_activate_ajax',
                sid=stories[0].id
            ),
            data={'active': False},
            headers=[('X-Requested-With', 'XMLHttpRequest')]
        )
        assert stories[0].active == True

    def test_chatuser_answers(self, client):
        (user, account) = self.create_user_account()
        self.login(client)

        chat_user = self.create_chat_user(account)

        # create question fragments
        story = ProfileStory(title='story#1', lead="lead#1").save()
        a1 = self.create_chat_user_attribute(account, 'attr1', 'int', 'pie', [])
        a2 = self.create_chat_user_attribute(account, 'attr2', 'text', 'bars', [])

        q1 = self.create_question_fragment(a1, "question#1", story)
        q2 = self.create_question_fragment(a2, "question#2", story)

        # check with no answers
        response = client.get(url_for(
            'index.chatusers_answers_list',
            chat_id=str(chat_user.chat_id)
        ), data={})

        assert response.status_code == 200

        answer_1 = self.create_answer(q2, 'answer1', chat_user)
        answer_2 = self.create_answer(q1, '512', chat_user)

        response = client.get(url_for(
            'index.chatusers_answers_list',
            chat_id=str(chat_user.chat_id)
        ), data={})

        assert response.status_code == 200
        assert q1.text in response.data.decode('utf-8')
        assert q2.text in response.data.decode('utf-8')

        assert answer_1.answer in response.data.decode('utf-8')
        assert answer_2.answer in response.data.decode('utf-8')

    def test_audience_index(self, client, app):
        (user, account) = self.create_user_account()
        self.login(client)
        chat_user = self.create_chat_user(account)

        # init stats
        AccountStats(
            enabled_users=10,
            active_users=40,
            dropped_users=5,
            new_users=20,
            messages_received=10,
            date=datetime.datetime.utcnow().date() - datetime.timedelta(days=1),
            account=account
        ).save()

        AccountStats(
            enabled_users=50,
            active_users=40,
            dropped_users=5,
            new_users=5,
            messages_received=15,
            date=datetime.datetime.utcnow().date() - datetime.timedelta(days=10),
            account=account
        ).save()

        # init question
        story = ProfileStory(title='story#1', lead="lead#1").save()
        attr = self.create_chat_user_attribute(account, 'attr1', 'int', 'bars', [])
        q = self.create_question_fragment(attr, 'How old are you?', story)

        # init answers
        self.create_answer(q, '20', chat_user)
        self.create_answer(q, '30', chat_user)
        self.create_answer(q, '30', chat_user)
        self.create_answer(q, '10', chat_user)

        with self.captured_context(app) as templates:
            response = client.get(url_for('index.audience'))
            context = templates[0]
            assert 'pathToImages' in context
            # 40(prev_day) + 1(new chat user today) = 41
            assert context['active_users_last24h'] == 41
            assert context['total_users'] == ChatUser.\
                objects(account_id=account).count()
            assert len(context['account_stats']) == AccountStats.\
                objects(account=account).count()

            # check questions
            assert len(context['questions']) == 1
            q_stats = context['questions'].get(str(q.pk))

            assert q_stats['answers'].get('30') == 2
            assert q_stats['answers'].get('20') == 1
            assert q_stats['answers'].get('10') == 1
            assert not q_stats['answers'].get('5')

    def test_audience_details(self, client, app):
        (user, account) = self.create_user_account()
        self.login(client)

        # init stats
        AccountStats(
            enabled_users=10,
            active_users=40,
            dropped_users=5,
            new_users=20,
            messages_received=10,
            date=datetime.datetime.utcnow().date() - datetime.timedelta(days=10),
            account=account
        ).save()

        AccountStats(
            enabled_users=50,
            active_users=40,
            dropped_users=5,
            new_users=5,
            messages_received=15,
            date=datetime.datetime.utcnow().date(),
            account=account
        ).save()

        AccountStats(
            enabled_users=50,
            active_users=40,
            dropped_users=5,
            new_users=5,
            messages_received=15,
            date=datetime.datetime.utcnow().date() - datetime.timedelta(days=35),
            account=account
        ).save()

        # test default date range
        with self.captured_context(app) as templates:
            response = client.get(url_for('index.audience_details'))
            context = templates[0]
            date_to = datetime.datetime.utcnow().date()
            date_from = date_to - datetime.timedelta(days=30)
            assert 'pathToImages' in context
            assert len(context['account_stats']) == AccountStats.objects(
                date__gte=date_from, date__lte=date_to).count()

        # test custom date range [today, today-50days]
        with self.captured_context(app) as templates:
            date_to = datetime.datetime.utcnow().date()
            date_from = date_to - datetime.timedelta(days=50)

            response = client.get(url_for('index.audience_details'),
                query_string={
                    'date_from': date_from.strftime('%m/%d/%Y'),
                    'date_to': date_to.strftime('%m/%d/%Y')
                }
            )

            context = templates[0]
            assert len(context['account_stats']) == 3

        # test custom date range [today, today]
        with self.captured_context(app) as templates:
            date = datetime.datetime.utcnow().date()
            response = client.get(url_for('index.audience_details'),
                query_string={
                    'date_from': date.strftime('%m/%d/%Y'),
                    'date_to': date.strftime('%m/%d/%Y')
                }
            )

            context = templates[0]
            assert len(context['account_stats']) == 1

    def test_bulletins_preview(self, client, app):
        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        self.login(client)

        story = self.create_story(bulletin)
        self.create_fragment_answer(story)

        with self.captured_context(app) as templates:
            response = client.get(url_for('index.bulletins_preview', bid=bulletin.id))
            context = templates[0]
            assert context['bulletin'] == bulletin
            assert response.status_code == 200
            # check if all stories and their content in response
            for story in bulletin.content_ordered:
                assert story.lead in response.data.decode('utf-8')

                for f in story.content_ordered_grouped:
                    if isinstance(f, list):
                        for _f in f:
                            assert _f.text in response.data.decode('utf-8')
                    else:
                        assert f.text in response.data.decode('utf-8')

        bulletin.is_published = True
        bulletin.save()

        with self.captured_context(app) as templates:
            # test published bulletin
            # published bulletins also should be available for previewing
            response = client.get(url_for('index.bulletins_preview', bid=bulletin.id))
            assert response.status_code == 200

    def test_poll_analytics(self, client, app):
        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        story = self.create_story(bulletin)
        self.create_fragment_answer(story)

        self.login(client)

        f1 = Fragment(
            text='test poll 1',
            story=story,
            type=Fragment.TYPE_POLL,
            order=len(story.content) + 1
        ).save()

        f2 = Fragment(
            text='test poll 2',
            story=story,
            type=Fragment.TYPE_POLL,
            order=len(story.content) + 2
        ).save()

        story.content.extend([f1, f2])
        story.save()

        # poll 1
        PollQuestions(text='q1', fragment=f1, users=[3,5]).save()
        PollQuestions(text='q2', fragment=f1, users=[1,2,4]).save()
        PollQuestions(text='q3', fragment=f1, users=[6]).save()
        # poll 2
        PollQuestions(text='q1', fragment=f2, users=[1,2]).save()
        PollQuestions(text='q2', fragment=f2, users=[]).save()

        with self.captured_context(app) as templates:
            response = client.get(url_for('index.polls'))
            context = templates[0]

            assert "poll_fragments" in context
            assert len(context["poll_fragments"]) == 2
            assert f1 in context["poll_fragments"]
            assert f2 in context["poll_fragments"]

            for f in context["poll_fragments"]:
                if f.id == f1.id:
                    assert f.answers == 6
                if f.id == f2.id:
                    assert f.answers == 2

        with self.captured_context(app) as templates:
            response = client.get(url_for('index.view_poll', poll_id=f1.id))
            context = templates[0]

            assert 'data' in context
            assert len(context['data']) == 4
            assert context['data'][-1]['votes'] == 6
            assert context['data'][-1]['answer'] == 'All answers'
            assert context['data'][-1]['persent'] == 100

    def test_register(self, client):
        Invitation(code='123', text='test code').save()

        # test with incorrect code
        data = {
            'account-name': 'company#1',
            'account-audience': '100',
            'account-timezone': 'Africa/Abidjan',
            'code': "111",
            'email': 'admin@admin.com',
            'password': '12345678',
            'name': 'admin'
        }

        response = client.post(
            url_for('auth.register'), data=data
        )

        assert User.objects().count() == 0
        assert 'Not valid invation code' in response.data.decode('utf-8')

        # test valid code
        data['code'] = '123'
        response = client.post(
            url_for('auth.register'), data=data
        )
        assert User.objects().count() == 1
        assert 'Not valid invation code' not in response.data.decode('utf-8')

    def test_skip_poll_option(self, client, app):
        (user, account) = self.create_user_account()
        bulletin = self.create_bulletin(account)
        story = self.create_story(bulletin)
        self.create_fragment_answer(story)
        self.login(client)

        with self.captured_context(app) as templates:
            resp = client.get(
                url_for('index.stories_edit', sid=str(story.id))
            )
            context = templates[0]

            assert 'skip_poll_message' in context
            assert context['skip_poll_message'] == account.skip_poll_message
