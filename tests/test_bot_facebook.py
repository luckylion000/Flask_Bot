#!/usr/bin/env python

from unittest.mock import call, Mock

from facebookbot import FacebookBot
from helpers import TestBase
from newsbot.models import ChatUser, PollQuestions


class TestBotFacebook(TestBase):

    def test_bot_init_conversation(self, client):

        (_, account) = self.create_user_account()

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        chat_id = 1234
        bot.handle_message(self.get_facebook_message(chat_id=chat_id))
        sendMessage_args = bot.bot.sendMessage.call_args_list
        assert sendMessage_args[0] == call(chat_id, account.welcome_message_1)
        assert sendMessage_args[1] == call(chat_id, account.welcome_message_2, buttons=['Answer 1'])

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(chat_id=chat_id))
        sendMessage_args = bot.bot.sendMessage.call_args
        assert sendMessage_args == call(chat_id,
                                        account.welcome_message_3,
                                        buttons=[account.welcome_answer_2_option_1,
                                                 account.welcome_answer_2_option_2])

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='wrong', chat_id=chat_id))
        assert bot.bot.method_calls == [call.get_user(chat_id)]

        bot.bot.reset_mock()
        msg = self.get_facebook_message(account.welcome_answer_2_option_1, chat_id=chat_id)
        bot.handle_message(msg)
        assert bot.bot.sendMessage.call_args == call(chat_id, account.up_to_date_message)

    def test_bot_process_user(self, client):

        (_, account) = self.create_user_account()

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        chat_id = 1234
        bot.handle_message(self.get_facebook_message(chat_id=chat_id))

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

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        self.create_chat_user(account, platform='facebook')

        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args == call(self.default_chat_id, 'IT', buttons=['ok'])

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='ok'))

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

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        self.create_chat_user(account, platform='facebook')

        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'lead1'

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='continue'))

        call = bot.bot.sendMessage.call_args_list[0]
        assert call[0][1] == 'chapter1'
        assert call[1] == {'buttons': ['continue2', 'next2']}

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='continue'))
        call = bot.bot.sendMessage.call_args_list[0]
        assert call[0][1] == account.unknown_answer_message
        assert call[1] == {'buttons': ['continue2', 'next2']}

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next'))
        call = bot.bot.sendMessage.call_args_list[0]
        assert call[0][1] == account.unknown_answer_message
        assert call[1] == {'buttons': ['continue2', 'next2']}

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='continue2'))

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

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        self.create_chat_user(account, platform='facebook')

        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'story1'

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next'))
        assert bot.bot.sendMessage.call_args[0][1] == account.unknown_answer_message

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next1'))
        assert bot.bot.sendMessage.call_args[0][1] == 'story2'

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next'))
        assert bot.bot.sendMessage.call_args[0][1] == account.unknown_answer_message

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next2'))
        assert bot.bot.sendMessage.call_args[0][1] == 'story3'

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next'))
        assert bot.bot.sendMessage.call_args[0][1] == account.unknown_answer_message

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='next3'))
        assert bot.bot.sendMessage.call_args[0][1] == account.up_to_date_message

    def test_bot_sending_published_bulletins(self, client):
        " sending_published_bulletins -> start_bulletin_reading "

        (_, account) = self.create_user_account()
        chat_user = self.create_chat_user(account, platform='facebook')

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})
        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == account.up_to_date_message

        bulletin = self.create_bulletin(account, is_published=True)
        story = self.create_story(bulletin, lead='start-story')
        self.create_fragment_answer(story, action='c', text='read it')

        bot.bot.reset_mock()
        bot.sending_published_bulletins()

        assert bot.bot.sendMessage.call_args[0][1] == 'start-story'
        assert bot.bot.sendMessage.call_args[1] == {'buttons': ['read it']}

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

        self.create_chat_user(account, platform='facebook')

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})
        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
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

        chat_user = self.create_chat_user(account, platform='facebook')
        last_message = chat_user.last_message
        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        def __check():
            nonlocal last_message
            chat_user.reload()
            assert chat_user.last_message > last_message
            last_message = chat_user.last_message

        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
        __check()

        bot.handle_message(self.get_facebook_message(text='continue'))
        __check()

        bot.handle_message(self.get_facebook_message(text='next'))
        __check()

        bot.handle_message(self.get_facebook_message(text='continue'))
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

        bot = FacebookBot(account.id)
        bot.bot = Mock()
        bot.bot.get_user = Mock(return_value={'first_name': 'John', 'last_name': 'Smith'})

        self.create_chat_user(account, platform='facebook')

        bot.handle_message(self.get_facebook_message(text=account.welcome_answer_2_option_1))
        assert bot.bot.sendMessage.call_args[0][1] == 'lead1'
        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='continue'))

        assert bot.bot.sendMessagePostback.call_args_list[0][0][1] == 'poll1'
        assert bot.bot.sendMessagePostback.call_args_list[0][1]['buttons'][0][0] == 'answer1'
        assert bot.bot.sendMessagePostback.call_args_list[0][1]['buttons'][1][0] == 'answer2'

        answer1_poll1 = PollQuestions.objects.get(fragment=poll_1, text='answer1')

        # user sent custom message, poll must be resent
        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='say something'))
        print(bot.bot.sendMessagePostback.call_args_list)
        assert bot.bot.sendMessagePostback.call_args_list[0][0][1] == 'poll1'
        assert bot.bot.sendMessagePostback.call_args_list[0][1]['buttons'][0][0] == 'answer1'
        assert bot.bot.sendMessagePostback.call_args_list[0][1]['buttons'][1][0] == 'answer2'

        data = str(poll_1.id) + ',' + str(answer1_poll1.id)
        bot.bot.reset_mock()
        bot.handle_callback_query(self.get_facebook_callback_query(data=data))

        answer1_poll1.reload()
        assert self.default_chat_id in answer1_poll1.users
        assert self.default_chat_id not in PollQuestions.objects.get(fragment=poll_1, text='answer2').users

        # send paragraph#1 and poll#2 after poll was answered
        answer2_poll2 = PollQuestions.objects.get(fragment=poll_2, text='answer2')
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'paragraph1'
        assert bot.bot.sendMessagePostback.call_args_list[0][0][1] == 'poll2'
        assert bot.bot.sendMessagePostback.call_args_list[0][1]['buttons'][0][0] == 'answer1'
        assert bot.bot.sendMessagePostback.call_args_list[0][1]['buttons'][1][0] == 'answer2'

        data = str(poll_2.id) + ',' + str(answer2_poll2.id)
        bot.bot.reset_mock()
        bot.handle_callback_query(self.get_facebook_callback_query(data=data))

        # send paragraph2 and answer after poll
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'paragraph2'
        assert 'finish answer' in bot.bot.sendMessage.call_args[1]['buttons']

        bot.bot.reset_mock()
        bot.handle_message(self.get_facebook_message(text='finish answer'))
        assert bot.bot.sendMessage.call_args_list[0][0][1] == 'You are up to date!'

        answer2_poll2.reload()
        assert self.default_chat_id in answer2_poll2.users
        assert self.default_chat_id not in PollQuestions.objects.get(fragment=poll_2, text='answer1').users
