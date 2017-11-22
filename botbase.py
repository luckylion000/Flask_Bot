
import datetime
from abc import ABCMeta, abstractmethod
from collections import namedtuple

import mongoengine
from celery.utils.log import get_task_logger
from emojipy import Emoji
from raven import Client

import settings

from newsbot.models import (
    Account,
    AccountStats,
    Bulletin,
    ChatUser,
    ChatUserAnswer,
    Fragment,
    PollQuestions,
    ProfileStory,
    ProfileStoryFragment,
    Story
)


logger = get_task_logger(__name__)
raven_client = Client(settings.SENTRY_DSN)


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

    def is_ready_message(self, msg):
        return self.read_user_message(msg) in [
            self.account.welcome_answer_2_option_1,
            self.account.welcome_answer_2_option_2
        ]

    @abstractmethod
    def send_image_fragment(self, chat_id, f):
        pass

    @abstractmethod
    def send_text_fragment(self, chat_id, f):
        pass

    @abstractmethod
    def send_question_fragment(self, user, chat_id, q):
        pass

    def action_from_answer(self, user, msg, story_model=Story):

        answers = self.get_prev_answers(user, story_model=story_model)
        if answers:
            text = Emoji.unicode_to_shortcode(self.read_user_message(msg))
            for f in answers:
                if f.text == text:
                    return f.action
        return None

    @abstractmethod
    def read_user_message(self, msg):
        pass

    @abstractmethod
    def get_answers_keyboard(self, answers):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def get_chat_id(self):
        pass

    def get_or_create_user(self, name, chat_id):
        try:
            u = ChatUser.objects.get(chat_id=chat_id, account_id=self.account.id, platform=self.PLATFORM)
        except ChatUser.DoesNotExist:
            u = ChatUser(chat_id=chat_id, name=name, platform=self.PLATFORM,
                         state=ChatUser.STATE_INITIAL, account_id=self.account.id, disabled=0)
            u.save()

        return u

    @abstractmethod
    def validate_account(self, account_id):
        a = Account.objects.get(id=account_id)
        assert a.up_to_date_message, 'Please fill Account.up_to_date_message'

        return a

    @abstractmethod
    def process_no_content(self, user, chat_id):
        user.last_message = datetime.datetime.utcnow()
        user.save()

    def get_unread_bulletins(self, user, skip_current_bulletin=False):

        utcnow = datetime.datetime.utcnow()

        skip_bulletin_ids = [x.id for x in user.read_bulletins]
        if skip_current_bulletin and user.current_bulletin:
            skip_bulletin_ids.append(user.current_bulletin.id)

        res = Bulletin.objects.filter(
            account=self.account,
            id__nin=skip_bulletin_ids,
            is_published=True,
            publish_at__lte=utcnow
        )

        def get_expire_time(bulletin):
            return bulletin.publish_at + datetime.timedelta(hours=bulletin.expire_hours)

        return [b for b in res if utcnow < get_expire_time(b)]

    def is_new_bulletins(self, user):
        " check if new bulletins exists except read_bulletins and current_bulletin "

        return bool(self.get_unread_bulletins(user, skip_current_bulletin=True))

    def start_bulletin_reading(self, user, chat_id, disable_no_content=False, bulletin_id=None):
        if not bulletin_id:
            bulletins = self.get_unread_bulletins(user)
        else:
            bulletins = Bulletin.objects.filter(id=bulletin_id)

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
                user.disable_no_content = 0
                user.save()

                user.current_bulletin = b
                user.current_story_order = story.order
                user.current_fragment_order = answers[-1].order
                user.save()

                self.send_lead_answers(chat_id, lead, answers)
                user.last_message = datetime.datetime.utcnow()
                user.current_fragment_order = answers[-1].order
                user.state = ChatUser.STATE_WAITING_ANSWER
                user.save()

    def switch_next_bulletin(self, user, chat_id, disable_no_content=False):
        if user.current_bulletin:
            user.read_bulletins.append(user.current_bulletin)
            user.current_bulletin = None
            user.save()

        self.start_bulletin_reading(user, chat_id, disable_no_content)

    def read_current_profile_story(self, user):
        if user.current_profile_story:
            user.read_profile_stories.append(user.current_profile_story)
            user.current_profile_story = None
            user.save()

    def switch_next_profile_story(self, user, chat_id, disable_no_content=True):
        self.read_current_profile_story(user)
        story = ProfileStory.objects.filter(
            id__not__in=[s.id for s in user.read_profile_stories],
            active=True,
            account=self.account
        ).first()

        if story is None:
            if user.onboarding:
                user.onboarding = False
                user.save()

            if not disable_no_content:
                self.process_no_content(user, chat_id)

            return

        user.current_profile_story = story
        user.current_profile_fragment_order = 0
        user.save()

        lead, answers = self.get_next_answers(story=story,
                                              fragment_order=0,
                                              fragment_model=ProfileStoryFragment)
        if lead is None or not answers:
            if user.onboarding and len(user.question_answers) < settings.MIN_QUESTIONS:
                # go to the next profile story
                self.switch_next_profile_story(user, chat_id)
            else:
                self.read_current_profile_story(user)
                if not disable_no_content:
                    self.process_no_content(user, chat_id)
        else:
            user.state = ChatUser.STATE_WAITING_PROFILE_ANSWER
            self.send_lead_answers(chat_id, lead, answers)
            user.last_message = datetime.datetime.utcnow()
            user.current_profile_fragment_order = answers[-1].order
            user.save()

    def send_rest_profile_story_fragments(self, user, chat_id):
        answers, questions, others = [], [], []
        story = user.current_profile_story

        for f in ProfileStoryFragment.objects.filter(
                story=story,
                order__gt=user.current_profile_fragment_order):

            if f.type != Fragment.TYPE_ANSWER and answers:
                break

            if questions:
                break

            if f.type == ProfileStoryFragment.TYPE_ANSWER:
                answers.append(f)
            elif f.type == ProfileStoryFragment.TYPE_QUESTION:
                # if a user has already answered the question skip the question.
                if f in [answ.question for answ in user.question_answers]:
                    pass
                else:
                    questions.append(f)
            else:
                others.append(f)

        show_keyboard = None
        if answers:
            user.state = ChatUser.STATE_WAITING_PROFILE_ANSWER
            user.save()
            show_keyboard = self.get_answers_keyboard(answers)

        for f in others:
            show_answer = None
            if others[-1] == f:
                show_answer = show_keyboard

            self.send_text_fragment(chat_id, f, show_answer)

            f.num_readers += 1
            f.save()

            if answers:
                user.current_profile_fragment_order = answers[-1].order
            else:
                user.current_profile_fragment_order = f.order

            user.last_message = datetime.datetime.utcnow()
            user.save()

        if questions:
            user.state = ChatUser.STATE_WAITING_PROFILE_QUESTION
            user.current_profile_fragment_order = questions[-1].order
            self.send_question_fragment(user, chat_id, questions[0])
            user.last_message = datetime.datetime.utcnow()
            user.save()

        if not answers and not questions:
            user.state = ChatUser.STATE_READY_RECEIVED
            user.save()

        return len(answers), len(questions)


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
            user.last_message = datetime.datetime.utcnow()
            user.current_fragment_order = answers[-1].order
            user.state = ChatUser.STATE_WAITING_ANSWER
            user.save()

    def process_user(self, chat_id, msg):
        return self.get_or_create_user(self.extract_username(msg), chat_id)

    def is_last_story(self, bulletin, order):
        return Story.objects.filter(bulletin=bulletin,
                                    order__gt=order).count() == 0

    def get_next_answers(self, story, fragment_order, fragment_model=Fragment):
        if story is None or not story.content:
            return None, []

        answers = []
        for f in fragment_model.objects.filter(story=story,
                                               order__gt=fragment_order):

            if f.type == Fragment.TYPE_ANSWER:
                answers.append(f)
            else:
                break

        return story.lead, answers

    def get_prev_answers(self, user, story_model=Story):
        " return all ANSWER Fragments from current_fragment_order position in backward "

        if story_model == Story:
            story = Story.objects.get(bulletin=user.current_bulletin,
                                      order=user.current_story_order)

            fragments = Fragment.objects.filter(story=story,
                                                order__lte=user.current_fragment_order)
        elif story_model == ProfileStory:
            fragments = ProfileStoryFragment.objects.filter(
                story=user.current_profile_story,
                order__lte=user.current_profile_fragment_order
            )

        answers = []
        for f in reversed(fragments):
            if f.type != Fragment.TYPE_ANSWER:
                break
            answers.insert(0, f)
        return answers

    def send_rest_fragments(self, user, chat_id):
        answers, polls, others = [], [], []
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
                pass

        if len(others) < 1 and answers:
            t = []
            for f in Fragment.objects.filter(
                    story=story,
                    order__lt=answers[0].order):
                if f.type != Fragment.TYPE_ANSWER:
                    t.append(f)

        # Here we assume that we cannot get to this function and have answers
        # as first unread fragments

        show_keyboard = None
        if answers:
            user.state = ChatUser.STATE_WAITING_ANSWER
            user.save()
            show_keyboard = self.get_answers_keyboard(answers)

        for f in others:
            show_answer = None
            if others[-1] == f:
                show_answer = show_keyboard
            if f.type == Fragment.TYPE_IMAGE:
                self.send_image_fragment(chat_id, f, show_answer)
            elif f.type == Fragment.TYPE_AUDIO:
                self.send_audio_fragment(chat_id, f, show_answer)
            elif f.type == Fragment.TYPE_DOCUMENT:
                self.send_document_fragment(chat_id, f, show_answer)
            elif f.type == Fragment.TYPE_VIDEO:
                self.send_video_fragment(chat_id, f, show_answer)
            elif f.type == Fragment.TYPE_POLL:
                self.send_poll_fragment(chat_id, f)
            else:
                self.send_text_fragment(chat_id, f, show_answer)

            user.current_fragment_order = f.order

            # atomic update of statistics
            Fragment.objects(id=f.id).modify(inc__num_readers=1)
            Story.objects(id=story.id).modify(add_to_set__readers=user)

            user.read_content.append(f)

            if answers:
                user.current_fragment_order = answers[-1].order
            user.last_message = datetime.datetime.utcnow()
            user.save()

            if f.type == Fragment.TYPE_POLL:
                polls.append(f)
                user.state = ChatUser.STATE_WAITING_POLL
                user.current_fragment_order = f.order
                user.save()
                # stop conversation, continue only after poll is answered
                break

        if len(others) < 1 and answers:
            # self.send_lead_answers(chat_id, story.lead, answers)
            self.send_lead_answers(chat_id, t[-1].text, answers)
            user.last_message = datetime.datetime.utcnow()
            user.current_fragment_order = answers[-1].order
            user.save()

        return len(answers), len(polls)

    def handle_callback_query(self, msg):

        chat_id = self.get_chat_id_inline(msg)
        payload = self.get_payload(msg)
        fragment_id, question_id = payload.split(',')

        if not PollQuestions.objects(fragment=fragment_id, users=chat_id).first():
            PollQuestions.objects(id=question_id).update_one(add_to_set__users=chat_id)

            self.vote_done(msg, fragment_id, question_id)

            # continue conversation
            user = ChatUser.objects.get(chat_id=chat_id, account_id=self.account.id, platform=self.PLATFORM)
            user.state = ChatUser.STATE_READY_RECEIVED
            user.save()

            answers_sent, polls_sent = self.send_rest_fragments(user, chat_id)
            if not answers_sent and not polls_sent:
                if self.is_last_story(user.current_bulletin,
                                      user.current_story_order):
                    self.switch_next_bulletin(user, chat_id)
                else:
                    self.switch_next_story(user, chat_id)

        else:
            self.vote_skip(msg)

    def handle_message(self, msg):

        if not self.validate_msg(msg):
            logger.warning('Message not valid {msg}'.format(msg=msg))
            return

        chat_id = self.get_chat_id(msg)
        user = self.process_user(chat_id, msg)
        # upd messages_received stats
        AccountStats.update_messages_received(self.account)
        logger.info('user is {username} and state is {state}'.format(username=user.name, state=user.state))

        if user.state == ChatUser.STATE_INITIAL:
            self.send_welcome(chat_id)
            user.state = ChatUser.STATE_INITIAL_STAGE2
            user.save()

        elif user.state == ChatUser.STATE_INITIAL_STAGE2:
            self.send_welcome_stage2(chat_id)
            user.state = ChatUser.STATE_WAITING_READY
            user.save()

        elif (user.state == ChatUser.STATE_WAITING_READY and self.is_ready_message(msg)):
            user.state = ChatUser.STATE_READY_RECEIVED
            user.save()

            # send profile stories first
            self.switch_next_profile_story(user, chat_id)
            if not user.current_profile_story:
                # send available bulletins
                if self.get_unread_bulletins(user) and\
                   user.current_bulletin is None:
                    self.start_bulletin_reading(user, chat_id)
                else:
                    self.process_no_content(user, chat_id)
            else:
                user.onboarding = True
                user.save()

        elif user.state == ChatUser.STATE_READY_RECEIVED:
            user.disable_no_content = 0
            user.save()

            if self.get_unread_bulletins(user):
                self.start_bulletin_reading(user, chat_id)
            else:
                self.process_no_content(user, chat_id)

        elif user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION:
            # save question answer
            question_fragment = ProfileStoryFragment.objects.get(
                story=user.current_profile_story,
                order=user.current_profile_fragment_order
            )
            answer = ChatUserAnswer(
                answer=self.read_user_message(msg),
                question=question_fragment
            )

            try:
                answer.save()
            except mongoengine.ValidationError as err:
                logger.info(
                    'answer({answer}) not valid, resend question fragment {question}'.format(
                        answer=answer.answer, question=question_fragment.id
                    )
                )
                # resent question fragment
                self.send_question_fragment(user, chat_id, question_fragment)
            else:
                user.question_answers.append(answer)
                user.save()
                logger.info(
                    'receive answer to question fragment {question}'.format(
                        question=question_fragment.id
                    )
                )

                if len(user.question_answers) < settings.MIN_QUESTIONS and\
                   user.onboarding:
                    answers_sent, questions_sent = self.send_rest_profile_story_fragments(
                        user, chat_id)

                    if not answers_sent and not questions_sent:
                        self.switch_next_profile_story(user, chat_id)
                else:
                    # finish onboarding
                    self.read_current_profile_story(user)
                    user.onboarding = False
                    user.state = ChatUser.STATE_READY_RECEIVED
                    user.save()

                if not user.current_profile_story:
                    # finish onboarding
                    user.state = ChatUser.STATE_READY_RECEIVED
                    user.onboarding = False
                    user.save()
                    # send available bulletins
                    if self.get_unread_bulletins(user) and\
                       user.current_bulletin is None:
                        self.start_bulletin_reading(user, chat_id)
                    else:
                        self.process_no_content(user, chat_id)

        elif user.state == ChatUser.STATE_WAITING_POLL:
            # resent current poll
            story = Story.objects.get(
                bulletin=user.current_bulletin,
                order=user.current_story_order
            )
            f = Fragment.objects.get(
                story=story,
                order=user.current_fragment_order
            )
            logger.warning('Resent poll fragment: {text}'.format(text=f.text))
            self.send_poll_fragment(chat_id, f)

        elif user.state == ChatUser.STATE_WAITING_ANSWER:
            user.disable_no_content = 0
            user.save()
            action = self.action_from_answer(user, msg)
            logger.info('action is {action}'.format(action=action))

            # Switch to the next fragment with Continue response
            if action == Fragment.ACTION_CONTINUE:
                answers_sent, polls_sent = self.send_rest_fragments(user, chat_id)
                if not answers_sent and not polls_sent:
                    if self.is_last_story(user.current_bulletin,
                                          user.current_story_order):
                        self.switch_next_bulletin(user, chat_id)
                    else:
                        self.switch_next_story(user, chat_id)

            elif action == Fragment.ACTION_NEXT:
                if self.is_last_story(user.current_bulletin,
                                      user.current_story_order):
                    self.switch_next_bulletin(user, chat_id)
                else:
                    self.switch_next_story(user, chat_id)

            else:
                logger.info('user has not responded any probable action')
                answers = self.get_prev_answers(user)
                if answers:
                    show_keyboard = self.get_answers_keyboard(answers)
                    fragment = namedtuple('Fragment', ['text'])(text=self.account.unknown_answer_message)
                    self.send_text_fragment(chat_id, fragment, show_keyboard)

        elif user.state == ChatUser.STATE_WAITING_PROFILE_ANSWER:
            switch_to_bullentins = False
            user.disable_no_content = 0
            user.save()

            action = self.action_from_answer(user, msg, story_model=ProfileStory)
            logger.info('action is {action}'.format(action=action))

            if action == Fragment.ACTION_CONTINUE:
                # Switch to the next fragment with Continue response
                answers_sent, questions_sent = self.send_rest_profile_story_fragments(user, chat_id)
                if not answers_sent and not questions_sent:
                    self.read_current_profile_story(user)

                    if len(user.question_answers) < settings.MIN_QUESTIONS and user.onboarding:
                        # continue onboarding questions
                        self.switch_next_profile_story(user, chat_id)
                        if not user.current_profile_story:
                            switch_to_bullentins = True

                    elif len(user.question_answers) >= settings.MIN_QUESTIONS and user.onboarding:
                        switch_to_bullentins = True
                        user.onboarding = False
                        user.save()

            elif action == Fragment.ACTION_NEXT:
                # Switch to the next Profile Story
                self.read_current_profile_story(user)
                if len(user.question_answers) < settings.MIN_QUESTIONS and user.onboarding:
                    self.switch_next_profile_story(user, chat_id)
                    if not user.current_profile_story:
                        switch_to_bullentins = True
                else:
                    switch_to_bullentins = True
                    user.onboarding = False
                    user.save()
            else:
                logger.info('user has not responded any probable action')
                answers = self.get_prev_answers(user, story_model=ProfileStory)
                show_keyboard = self.get_answers_keyboard(answers)

                fragment = namedtuple('Fragment', ['text'])(text=self.account.unknown_answer_message)
                self.send_text_fragment(chat_id, fragment, show_keyboard)

            if switch_to_bullentins:
                # send available bulletins
                if self.get_unread_bulletins(user) and\
                    user.current_bulletin is None:
                    self.start_bulletin_reading(user, chat_id)
                else:
                    self.process_no_content(user, chat_id)

    def sending_published_bulletins(self):
        # fetch all users subscribed to account
        users = ChatUser.objects.filter(account_id=self.account.id)
        logger.info('iterating users')
        for user in users:
            self.sending_published_bulletins_user(user.id)

    def sending_published_bulletins_user(self, user_id):

        user = ChatUser.objects.get(id=user_id)

        logger.info('checking {user} - {state}'.format(user=user.name, state=user.state))

        if (user.state == ChatUser.STATE_READY_RECEIVED or
            user.state == ChatUser.STATE_WAITING_ANSWER or
            user.state == ChatUser.STATE_WAITING_PROFILE_QUESTION or
            user.state == ChatUser.STATE_WAITING_PROFILE_ANSWER) and user.disabled == 0:

            if user.state in [ChatUser.STATE_WAITING_PROFILE_QUESTION, ChatUser.STATE_WAITING_PROFILE_ANSWER]:
                # bulletins have priority over profile stories
                if self.get_unread_bulletins(user):
                    user.current_profile_story = None
            elif user.state == ChatUser.STATE_WAITING_ANSWER:
                user.waiting += 1
            else:
                user.waiting = 0

            user.save()

            if user.waiting == 0 or user.waiting > 3:
                if user.waiting > 3:
                    if self.is_new_bulletins(user):
                        user.state = ChatUser.STATE_READY_RECEIVED
                        user.save()
                        logger.info('sending next bulletin to {user}'.format(user=user.name))
                        # this should be created as a delayed task
                        self.switch_next_bulletin(user, user.chat_id, True)
                else:
                    logger.info('start bulletin reading to {user}'.format(user=user.name))
                    # this should be created as a delayed task
                    self.start_bulletin_reading(user, user.chat_id, True)
                user.waiting = 0
                user.save()
