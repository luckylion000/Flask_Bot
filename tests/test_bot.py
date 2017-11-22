#!/usr/bin/env python

from datetime import datetime
from unittest.mock import Mock
from newsbot.models import ChatUser, PollQuestions, Account, AccountStats

from telegrambot import TelegramBot
from helpers import TestBase

from settings import QUESTION_INTERVAL

from telepot.exception import BotWasBlockedError

class TestBot(TestBase):

    def test_bot_init_conversation(self, client):

        (_, account) = self.create_user_account()

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        chat_id = 1234
        bot.handle_message(self.get_telegram_message(chat_id=chat_id))
        sendMessage_args = bot.bot.sendMessage.call_args_list
        assert sendMessage_args[0][0] == (chat_id, account.welcome_message_1)
        assert sendMessage_args[1][0][1] == account.welcome_message_2
        assert sendMessage_args[1][1]['reply_markup']['keyboard'] == [['Answer 1']]

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(chat_id=chat_id))
        sendMessage_args = bot.bot.sendMessage.call_args
        assert sendMessage_args[0][1] == account.welcome_message_3
        assert sendMessage_args[1]['reply_markup']['keyboard'][0][0] == account.welcome_answer_2_option_1
        assert sendMessage_args[1]['reply_markup']['keyboard'][0][1] == account.welcome_answer_2_option_2

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='wrong', chat_id=chat_id))
        assert bot.bot.method_calls == []

        bot.bot.reset_mock()
        msg = self.get_telegram_message(account.welcome_answer_2_option_1, chat_id=chat_id)
        bot.handle_message(msg)
        assert bot.bot.sendMessage.call_args[0][1] == account.up_to_date_message
        assert bot.bot.sendMessage.call_args[1]['reply_markup']['hide_keyboard'] == True

    def test_bot_process_user(self, client):

        (_, account) = self.create_user_account()

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        chat_id = 1234
        bot.handle_message(self.get_telegram_message(chat_id=chat_id))

        assert ChatUser.objects.count() == 1
        chat_user = ChatUser.objects.get(chat_id=chat_id, account_id=account.id)
        assert chat_user.name == 'John Smith'
        assert chat_user.state == ChatUser.STATE_INITIAL_STAGE2
        assert chat_user.account_id == account

    def test_bot_conversation(self, client):

        (_, account) = self.create_user_account()
        bulletin = self.create_bulletin(account, is_published=True)
        story = self.create_story(bulletin, lead='IT')
        self.create_fragment_answer(story, text='ok')
        self.create_fragment_paragraph(story, text='ML is cool!!!')

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        self.create_chat_user(account)

        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'IT'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='ok'))

        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'ML is cool!!!'
        assert bot.bot.sendMessage.call_args_list[1][0][1] == account.up_to_date_message

    def test_bot_answers_continue(self, client):

        (_, account) = self.create_user_account()
        story = self.create_story(self.create_bulletin(account, is_published=True))
        self.create_fragment_answer(story, action='c', text='continue')
        self.create_fragment_answer(story, action='n', text='next')
        self.create_fragment_paragraph(story, text='chapter1')
        self.create_fragment_answer(story, action='c', text='continue2')
        self.create_fragment_answer(story, action='n', text='next2')
        self.create_fragment_paragraph(story, text='chapter2')

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        self.create_chat_user(account)

        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'lead1'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='continue'))

        call = bot.bot.sendMessage.call_args_list[0]
        assert call[0][1] == 'chapter1'
        assert call[1]['reply_markup']['keyboard'] == [['continue2'], ['next2']]

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='continue'))
        call = bot.bot.sendMessage.call_args_list[0]
        assert call[0][1] == account.unknown_answer_message
        assert call[1]['reply_markup']['keyboard'] == [['continue2'], ['next2']]
        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next'))
        call = bot.bot.sendMessage.call_args_list[0]
        assert call[0][1] == account.unknown_answer_message
        assert call[1]['reply_markup']['keyboard'] == [['continue2'], ['next2']]

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='continue2'))

        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'chapter2'
        assert bot.bot.sendMessage.call_args_list[1][0][1] == account.up_to_date_message

    def test_bot_answers_next(self, client):

        (_, account) = self.create_user_account()
        bulletin1 = self.create_bulletin(account, is_published=True)

        story1 = self.create_story(bulletin1, lead='story1')
        self.create_fragment_answer(story1, action='n', text='next1')
        self.create_fragment_paragraph(story1, text='paragraph1')

        story2 = self.create_story(bulletin1, lead='story2')
        self.create_fragment_answer(story2, action='n', text='next2')
        self.create_fragment_paragraph(story2, text='paragraph2')

        story3 = self.create_story(self.create_bulletin(account, is_published=True), lead='story3')
        self.create_fragment_answer(story3, action='n', text='next3')
        self.create_fragment_paragraph(story3, text='paragraph3')

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        self.create_chat_user(account)

        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'story1'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next'))
        assert bot.bot.sendMessage.call_args[0][1] == account.unknown_answer_message

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next1'))
        assert bot.bot.sendMessage.call_args[0][1] == 'story2'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next'))
        assert bot.bot.sendMessage.call_args[0][1] == account.unknown_answer_message

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next2'))
        assert bot.bot.sendMessage.call_args[0][1] == 'story3'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next'))
        assert bot.bot.sendMessage.call_args[0][1] == account.unknown_answer_message

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='next3'))
        assert bot.bot.sendMessage.call_args[0][1] == account.up_to_date_message

    def test_bot_sending_published_bulletins(self, client):
        " sending_published_bulletins -> start_bulletin_reading "

        (_, account) = self.create_user_account()
        chat_user = self.create_chat_user(account)

        bot = TelegramBot(account.id)
        bot.bot = Mock()
        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == account.up_to_date_message

        bulletin = self.create_bulletin(account, is_published=True)
        story = self.create_story(bulletin, lead='start-story')
        self.create_fragment_answer(story, action='c', text='read it')

        bot.bot.reset_mock()
        bot.sending_published_bulletins()

        assert bot.bot.sendMessage.call_args[0][1] == 'start-story'
        assert bot.bot.sendMessage.call_args[1]['reply_markup']['keyboard'] == [['read it']]

        chat_user.reload()
        chat_user.state == ChatUser.STATE_WAITING_ANSWER

    def test_bot_sending_published_bulletins2(self, client):
        " sending_published_bulletins -> switch_next_bulletin "

        (_, account) = self.create_user_account()

        bulletin1 = self.create_bulletin(account, title='bulletin1', is_published=True)
        story1 = self.create_story(bulletin1, lead='story1')
        self.create_fragment_answer(story1, action='n', text='next')
        self.create_fragment_paragraph(story1, text='paragraph1')
        story2 = self.create_story(bulletin1, lead='story2')
        self.create_fragment_answer(story2, action='n', text='next')
        self.create_fragment_paragraph(story2, text='paragraph2')

        bulletin2 = self.create_bulletin(account, title='bulletin2', is_published=True)
        story3 = self.create_story(bulletin2, lead='story3')
        self.create_fragment_answer(story3, action='n', text='next')
        self.create_fragment_paragraph(story3, text='paragraph3')

        self.create_chat_user(account)

        bot = TelegramBot(account.id)
        bot.bot = Mock()
        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'story1'

        bot.bot.reset_mock()
        bot.sending_published_bulletins()
        assert bot.bot.sendMessage.call_args is None

        bot.sending_published_bulletins()
        assert bot.bot.sendMessage.call_args is None

        bot.sending_published_bulletins()
        assert bot.bot.sendMessage.call_args is None

        bot.sending_published_bulletins()
        assert bot.bot.sendMessage.call_args[0][1] == 'story3'

    def test_bot_last_message_increment(self, client):

        (_, account) = self.create_user_account()

        bulletin = self.create_bulletin(account, is_published=True)
        story1 = self.create_story(bulletin)
        self.create_fragment_answer(story1, action='n', text='next')
        self.create_fragment_answer(story1, action='c', text='continue')
        self.create_fragment_paragraph(story1)
        self.create_fragment_answer(story1, action='n', text='next')
        self.create_fragment_answer(story1, action='c', text='continue')
        self.create_fragment_paragraph(story1)
        story2 = self.create_story(bulletin)
        self.create_fragment_answer(story2, action='n', text='next')
        self.create_fragment_answer(story2, action='c', text='continue')

        chat_user = self.create_chat_user(account)
        last_message = chat_user.last_message
        bot = TelegramBot(account.id)
        bot.bot = Mock()

        def __check():
            nonlocal last_message
            chat_user.reload()
            assert chat_user.last_message > last_message
            last_message = chat_user.last_message

        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        __check()

        bot.handle_message(self.get_telegram_message(text='continue'))
        __check()

        bot.handle_message(self.get_telegram_message(text='next'))
        __check()

        bot.handle_message(self.get_telegram_message(text='continue'))
        __check()

    def test_bot_poll(self, client):

        (_, account) = self.create_user_account()
        bulletin = self.create_bulletin(account, is_published=True)
        story = self.create_story(bulletin)
        self.create_fragment_answer(story)

        poll_1 = self.create_fragment_poll(story, text='poll1')
        paragraph_1 = self.create_fragment_paragraph(story, text='paragraph1')

        poll_2 = self.create_fragment_poll(story, text='poll2')
        paragraph_2 = self.create_fragment_paragraph(story, text='paragraph2')
        self.create_fragment_answer(story, text='finish answer')

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        self.create_chat_user(account)

        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'lead1'
        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='continue'))

        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'poll1'
        assert bot.bot.sendMessage.call_args_list[0][1]['reply_markup'][0][0][0][0] == 'answer1'
        assert bot.bot.sendMessage.call_args_list[0][1]['reply_markup'][0][1][0][0] == 'answer2'

        answer1_poll1 = PollQuestions.objects.get(fragment=poll_1, text='answer1')

        # user sent custom message, poll must be resent
        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='say something'))
        print(bot.bot.sendMessage.call_args_list)
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'poll1'
        assert bot.bot.sendMessage.call_args_list[0][1]['reply_markup'][0][0][0][0] == 'answer1'
        assert bot.bot.sendMessage.call_args_list[0][1]['reply_markup'][0][1][0][0] == 'answer2'

        data = str(poll_1.id) + ',' + str(answer1_poll1.id)
        bot.bot.reset_mock()
        bot.handle_callback_query(self.get_telegram_callback_query(data=data))

        answer1_poll1.reload()
        assert self.default_chat_id in answer1_poll1.users
        assert self.default_chat_id not in PollQuestions.objects.get(fragment=poll_1, text='answer2').users

        # send paragraph#1 and poll#2 after poll was answered
        answer2_poll2 = PollQuestions.objects.get(fragment=poll_2, text='answer2')
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'paragraph1'
        assert bot.bot.sendMessage.call_args_list[1][0][1] == 'poll2'
        assert bot.bot.sendMessage.call_args_list[1][1]['reply_markup'][0][0][0][0] == 'answer1'
        assert bot.bot.sendMessage.call_args_list[1][1]['reply_markup'][0][1][0][0] == 'answer2'

        data = str(poll_2.id) + ',' + str(answer2_poll2.id)
        bot.bot.reset_mock()
        bot.handle_callback_query(self.get_telegram_callback_query(data=data))

        # send paragraph2 and answer after poll
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'paragraph2'
        assert 'finish answer' in bot.bot.sendMessage.call_args[1]['reply_markup']['keyboard'][0]

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='finish answer'))
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'You are up to date!'

        answer2_poll2.reload()
        assert self.default_chat_id in answer2_poll2.users
        assert self.default_chat_id not in PollQuestions.objects.get(fragment=poll_2, text='answer1').users

    def test_bot_profile_story_questions(self, client):
        (_, account) = self.create_user_account()
        attr1 = self.create_chat_user_attribute(
            account, 'attr1', 'text', 'bars',
            [
                {'text': 'opt1', 'value': 'val1'},
                {'text': 'opt2', 'value': 'val2'}
            ]
        )
        attr2 = self.create_chat_user_attribute(account, 'attr1', 'int', 'bars', [])

        story1 = self.create_profile_story('story#1', account, active=False)
        question1 = self.create_question_fragment(attr1, 'question#1', story1)
        self.add_question_fragment(story1, question1)

        story2 = self.create_profile_story('story#2', account)
        question2 = self.create_question_fragment(attr2, 'question#2', story2)
        self.add_question_fragment(story2, question2)

        story3 = self.create_profile_story('story#3', account)
        question3 = self.create_question_fragment(attr1, 'question#3', story3)
        self.add_question_fragment(story3, question3)

        story4 = self.create_profile_story('story#4', account)
        question4 = self.create_question_fragment(attr2, 'question#4', story4)
        self.add_question_fragment(story4, question4)

        bulletin = self.create_bulletin(account, is_published=True)
        story = self.create_story(bulletin)
        self.create_fragment_answer(story, action='c', text='continue')
        self.create_fragment_paragraph(story)

        chat_user = self.create_chat_user(account)
        bot = TelegramBot(account.id)
        bot.bot = Mock()

        # finishing onboarding process and send 1st question
        chat_user.state = ChatUser.STATE_WAITING_READY
        bot.handle_message(
            self.get_telegram_message(
                text=account.welcome_answer_2_option_1
            )
        )

        # story2 sended
        chat_user.reload()
        assert chat_user.onboarding == True
        assert chat_user.current_profile_story == story2
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_ANSWER
        # select continue story2
        bot.handle_message(self.get_telegram_message(text='continue'))

        chat_user.reload()
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION

        # answer question2
        bot.handle_message(self.get_telegram_message(text='val3'))
        chat_user.reload()
        # answer not int type, send current question again
        assert chat_user.current_profile_story == story2
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION
        assert len(chat_user.question_answers) == 0

        # answer question2, and story2 sended
        bot.handle_message(self.get_telegram_message(text='10'))
        # select continue story3
        bot.handle_message(self.get_telegram_message(text='continue'))
        chat_user.reload()

        assert chat_user.onboarding == True
        assert chat_user.current_profile_story == story3
        assert chat_user.current_profile_fragment_order == 3
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION
        assert question2 in [answer.question for answer in chat_user.question_answers]
        assert len(chat_user.question_answers) == 1

        # answer question3
        bot.handle_message(self.get_telegram_message(text='opt3'))
        chat_user.reload()
        # answer not in options, send current question again
        assert chat_user.current_profile_story == story3
        assert chat_user.current_profile_fragment_order == 3
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION
        assert len(chat_user.question_answers) == 1

        # answer question3, and story4 sended
        bot.handle_message(self.get_telegram_message(text='opt2'))
        # select continue story4
        bot.handle_message(self.get_telegram_message(text='continue'))
        chat_user.reload()

        assert chat_user.current_profile_story == story4
        assert chat_user.current_profile_fragment_order == 3
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION
        assert question3 in [answer.question for answer in chat_user.question_answers]
        assert len(chat_user.question_answers) == 2

        # answer question4
        # bulletin sended after onboarding questions
        bot.handle_message(self.get_telegram_message(text='20'))
        chat_user.reload()

        assert chat_user.onboarding == False
        assert chat_user.current_bulletin == bulletin
        assert not chat_user.current_profile_story
        assert chat_user.state == ChatUser.STATE_WAITING_ANSWER
        assert question4 in [answer.question for answer in chat_user.question_answers]
        assert len(chat_user.question_answers) == 3

        bot.handle_message(self.get_telegram_message(text='continue'))
        chat_user.reload()

        assert not chat_user.current_bulletin
        assert chat_user.state == ChatUser.STATE_READY_RECEIVED

        story1.active = True
        story1.save()

        left_no_content_msgs = QUESTION_INTERVAL -\
            chat_user.up_to_date_counter

        # receive QUESTION_INTERVAL no content msgs
        for i in range(left_no_content_msgs):
            bot.handle_message(self.get_telegram_message(text='hello'))
            chat_user.reload()
            assert not chat_user.current_profile_story
            assert chat_user.state == ChatUser.STATE_READY_RECEIVED
            assert len(chat_user.question_answers) == 3

        # story1 sended
        bot.handle_message(self.get_telegram_message(text='hello'))
        bot.handle_message(self.get_telegram_message(text='continue'))
        chat_user.reload()

        # question1 sended
        assert chat_user.onboarding == False
        assert chat_user.current_profile_story == story1
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION
        assert len(chat_user.question_answers) == 3
        assert chat_user.up_to_date_counter == 0

        # answer question1
        bot.handle_message(self.get_telegram_message(text='opt1'))
        chat_user.reload()

        assert not chat_user.current_profile_story
        assert chat_user.state == ChatUser.STATE_READY_RECEIVED
        assert question1 in [answer.question for answer in chat_user.question_answers]
        assert len(chat_user.question_answers) == 4

    def test_bot_new_questions(self, client):
        (_, account) = self.create_user_account()
        chat_user = self.create_chat_user(account)
        bot = TelegramBot(account.id)
        bot.bot = Mock()

        # finishing onboarding process
        chat_user.state = ChatUser.STATE_WAITING_READY
        bot.handle_message(
            self.get_telegram_message(
                text=account.welcome_answer_2_option_1
            )
        )

        attr1 = self.create_chat_user_attribute(account, 'attr1', 'int', 'bars', [])
        story1 = self.create_profile_story('story#1', account)
        question1 = self.create_question_fragment(attr1, 'question#1', story1)
        self.add_question_fragment(story1, question1)

        # question_1 should not be sended
        # only when UP_TO_DATE reached
        bot.handle_message(
            self.get_telegram_message(text='hello')
        )
        chat_user.reload()
        assert chat_user.onboarding == False
        assert chat_user.current_profile_story == None
        assert chat_user.state == ChatUser.STATE_READY_RECEIVED

        left_no_content_msgs = QUESTION_INTERVAL -\
            chat_user.up_to_date_counter

        # receive QUESTION_INTERVAL no content msgs
        for i in range(left_no_content_msgs):
            bot.handle_message(self.get_telegram_message(text='hello'))
            chat_user.reload()
            assert chat_user.current_profile_story == None
            assert chat_user.state == ChatUser.STATE_READY_RECEIVED
            assert len(chat_user.question_answers) == 0

        bot.handle_message(self.get_telegram_message(text='hello'))
        bot.handle_message(self.get_telegram_message(text='continue'))
        chat_user.reload()
        # question_1 sended
        assert chat_user.onboarding == False
        assert chat_user.current_profile_story == story1
        assert chat_user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION

    def test_account_stats(self, client):
        def upd_enabled_users():
            AccountStats.update_enabled_users(Account.objects())

        (_, account) = self.create_user_account()
        upd_enabled_users()

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        # testing enabled_users
        stats = AccountStats.objects().first()
        assert stats.enabled_users == 0
        assert stats.date.date() == datetime.utcnow().date()
        assert stats.account == account

        # testing active_users, new_users
        chat_user = self.create_chat_user(account)
        upd_enabled_users()
        stats.reload()

        assert stats.enabled_users == 1
        assert stats.active_users == 1
        assert stats.new_users == 1
        assert stats.date.date() == datetime.utcnow().date()
        assert stats.account == account

        # testing messages_received
        bot.handle_message(self.get_telegram_message(text='hi'))
        bot.handle_message(self.get_telegram_message(text='hi'))
        bot.handle_message(self.get_telegram_message(text='hi'))
        stats.reload()

        assert stats.enabled_users == 1
        assert stats.active_users == 1
        assert stats.new_users == 1
        assert stats.messages_received == 3

        # testing dropped_users
        chat_user.disabled = 1
        chat_user.save()
        stats.reload()

        assert stats.dropped_users == 1

        # test with 2 differrent accounts
        self.register_data['email'] = 'user2@domain.com'
        (_, account2) = self.create_user_account()
        self.default_chat_id = 56789
        chat_user2 = self.create_chat_user(account2)

        upd_enabled_users()
        stats2 = AccountStats.objects.get(account=account2)
        stats.reload()

        assert stats.enabled_users == 0
        assert stats.active_users == 1
        assert stats.new_users == 1
        assert stats.messages_received == 3
        assert stats.dropped_users == 1

        assert stats2.enabled_users == 1
        assert stats2.active_users == 1
        assert stats2.new_users == 1
        assert stats2.messages_received == 0

        bot2 = TelegramBot(account2.id)
        bot2.bot = Mock()
        bot2.handle_message(self.get_telegram_message(
            text='hi', chat_id=self.default_chat_id
        ))
        stats2.reload()

        assert stats2.messages_received == 1

        # test if stats removed with account
        account.delete()
        assert AccountStats.objects(account=account).count() == 0

    def test_new_users_account_stats(self, client):
        (_, account) = self.create_user_account()
        bot = TelegramBot(account.id)
        bot.bot = Mock()

        today = datetime.utcnow().date()
        assert AccountStats.objects(date=today, account=account).count() == 0
        # new chat user created
        bot.get_or_create_user(name='test_user', chat_id='1521512')
        assert AccountStats.objects(date=today, account=account).count() == 1
        stats = AccountStats.objects.get(date=today, account=account)
        assert stats.new_users == 1

        # user already exists
        bot.get_or_create_user(name='test_user', chat_id='1521512')
        stats.reload()
        assert AccountStats.objects(date=today, account=account).count() == 1
        assert stats.new_users == 1

        # new chat user created
        bot.get_or_create_user(name='test_user2', chat_id='2142141')
        stats.reload()
        assert AccountStats.objects(date=today, account=account).count() == 1
        assert stats.new_users == 2

    def test_bot_blocked_by_user(self, client):
        (_, account) = self.create_user_account()
        chat_user = self.create_chat_user(account)

        # monkey-patch start_next_question method
        # simulate blocked msg response
        def mock_switch_next_profile_story(user, chat_id, disable_no_content=False):
            raise BotWasBlockedError('Forbidden: bot was blocked by the user', 403,
                {
                    'error_code': 403, 'ok': False,
                    'description': 'Forbidden: bot was blocked by the user'
                }
            )

        bot = TelegramBot(account.id)
        bot.bot = Mock()
        bot.switch_next_profile_story = mock_switch_next_profile_story

        today = datetime.utcnow().date()
        stats = AccountStats.objects.get(date=today, account=account)
        assert stats.new_users == 1
        assert stats.dropped_users == 0

        bot.handle_message(self.get_telegram_message(
            text=account.welcome_answer_2_option_1)
        )
        stats.reload()
        chat_user.reload()

        assert stats.new_users == 1
        assert stats.dropped_users == 1
        assert chat_user.disabled == 1

    def test_start_bulletin_reading_with_bulletin_id(self, client):
        (_, account) = self.create_user_account()

        bulletin1 = self.create_bulletin(account, is_published=True)
        story1 = self.create_story(bulletin1, lead='story1')
        self.create_fragment_answer(story1, action='n', text='next1')
        self.create_fragment_paragraph(story1, text='paragraph1')

        bulletin2 = self.create_bulletin(account, title='bulletin2', is_published=True)
        story2 = self.create_story(bulletin2, lead='story2')
        self.create_fragment_answer(story2, action='n', text='next2')
        self.create_fragment_paragraph(story2, text='paragraph2')

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        chat_user = self.create_chat_user(account)
        bot.start_bulletin_reading(
            chat_user, chat_user.chat_id,
            disable_no_content=True,
            bulletin_id=bulletin2.id
        )

        chat_user.reload()
        assert chat_user.current_bulletin == bulletin2
        assert chat_user.state == ChatUser.STATE_WAITING_ANSWER

    def test_bot_conversation2(self, client):

        (_, account) = self.create_user_account()
        bulletin = self.create_bulletin(account, is_published=True)

        story1 = self.create_story(bulletin, lead='story1')
        self.create_fragment_answer(story1, action='c', text='continue')
        self.create_fragment_answer(story1, action='n', text='next')
        poll = self.create_fragment_poll(story1, text='poll')
        self.create_fragment_paragraph(story1, text='paragraph1')

        story2 = self.create_story(bulletin, lead='story2')
        self.create_fragment_answer(story2, action='c', text='continue')
        self.create_fragment_answer(story2, action='n', text='next')
        self.create_fragment_paragraph(story2, text='paragraph2')
        self.create_fragment_answer(story2, action='c', text='continue')
        self.create_fragment_answer(story2, action='n', text='next')

        bot = TelegramBot(account.id)
        bot.bot = Mock()

        self.create_chat_user(account)

        bot.handle_message(self.get_telegram_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'story1'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='continue'))
        assert bot.bot.sendMessage.call_args[0][1] == 'poll'

        answer1_poll = PollQuestions.objects.get(fragment=poll, text='answer1')
        data = str(poll.id) + ',' + str(answer1_poll.id)
        bot.bot.reset_mock()
        bot.handle_callback_query(self.get_telegram_callback_query(data=data))

        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'paragraph1'
        assert bot.bot.sendMessage.call_args_list[1][0][1] == 'story2'

        bot.bot.reset_mock()
        bot.handle_message(self.get_telegram_message(text='continue'))

        assert bot.bot.sendMessage.call_args[0][1] == 'paragraph2'
