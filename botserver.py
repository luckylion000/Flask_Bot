import time
from urllib2 import urlopen

import mongoengine
import telepot

from emojipy import Emoji
from mixpanel import Mixpanel

import settings
from newsbot.models import (
    Bulletin,
    BulletinChatUser,
    ChatUser,
    Fragment,
    Story
)
from newsbot.server import create_app

mongoengine.connect(host=settings.MONGODB_SETTINGS['host'])

mp = Mixpanel(settings.MIXPANEL_TOKEN)

TYPING_TIME = 0.5


def get_user_from_msg(msg):
    if 'username' in msg['chat']:
        user = msg['chat']['username']
    elif 'first_name' in msg['chat'] and 'last_name' in msg['chat']:
        user = msg['chat']['first_name'] + " " + msg['chat']['last_name']
    elif 'first_name' in msg['chat']:
        user = msg['chat']['first_name']
    else:
        user = 'anonymous'
    return user


def get_unread_bulletins(chat_user):
    read_bulletins = []
    for r in BulletinChatUser.objects(chat_user=chat_user).only('bulletin'):
        read_bulletins.append(r.bulletin.id)
    unread_bulletins = Bulletin.objects(
        id__nin=read_bulletins).order_by('-published')
    for ur in unread_bulletins:
        print ur.id, ur.published

    return unread_bulletins


def start_story(bulletin, chat_user, chat_id):
    print 'NEW STORY'
    story = Story.objects(
        bulletin=bulletin).order_by('order')[chat_user.current_story]
    answer = Fragment.objects.filter(
        story=story, type__ne=Fragment.TYPE_IMAGE).order_by('order')[0]

    show_keyboard = {
        'keyboard': [[Emoji.shortcode_to_unicode(answer.text), 'Next']],
        'one_time_keyboard': True,
        'resize_keyboard': True
    }
    bot.sendChatAction(chat_id, "typing")
    time.sleep(TYPING_TIME)
    bot.sendMessage(chat_id, story.lead, reply_markup=show_keyboard,
                    disable_web_page_preview=True)
    chat_user.current_fragment += 1


def on_boarding(chat_id):
    bot.sendChatAction(chat_id, "typing")
    time.sleep(TYPING_TIME)
    bot.sendMessage(chat_id, "Welcome to bulletins.chat!")
    bot.sendChatAction(chat_id, "typing")
    time.sleep(TYPING_TIME)
    bot.sendMessage(chat_id,
                    "We will show you a set of news, all you need to "
                    "tellme if you need to continue with the story I am "
                    "telling you or go to next story!")
    bot.sendChatAction(chat_id, "typing")
    time.sleep(TYPING_TIME)
    bot.sendMessage(
        chat_id,
        "Are you ready?",
        reply_markup={'keyboard': [['Yes!']],
                      'one_time_keyboard': True,
                      'resize_keyboard': True},
        disable_web_page_preview=True)


def send_fragment(chat_id, fragment, reply_markup):
    print fragment.type, fragment.text, fragment.url
    if fragment.type == fragment.TYPE_PARAGRAPH:
        time.sleep(TYPING_TIME)
        bot.sendMessage(chat_id,
                        Emoji.shortcode_to_unicode(fragment.text),
                        reply_markup=reply_markup,
                        disable_web_page_preview=True)
    else:
        bot.sendPhoto(chat_id, ('image.jpg', urlopen(fragment.url)),
                      reply_markup=reply_markup)


def on_chat_message(msg):
    print msg
    content_type, chat_type, chat_id = telepot.glance(msg)
    # if chatuser is not registered
    try:
        chat_user = ChatUser.objects.get(chat_id=chat_id)
    except ChatUser.DoesNotExist:
        # save user id and set status
        # HERE GOES THE ONBOARDING
        on_boarding(chat_id)
        chat_user = ChatUser(chat_id=chat_id, name=get_user_from_msg(msg))
        chat_user.save()
        mp.people_set(chat_id, {
            '$username': get_user_from_msg(msg)
        })
        mp.track(chat_id, 'registered')
        return

    # check if chat is reading a bullettin
    if chat_user.current_bulletin is None:
        # find any unread bulletin
        unread_bulletins = get_unread_bulletins(chat_user)

        # check if there are bulletins!
        if len(unread_bulletins) == 0:
            bot.sendChatAction(chat_id, "typing")
            time.sleep(TYPING_TIME)
            bot.sendMessage(chat_id, 'No more content for today!')
            return

        bulletin = unread_bulletins[0]
        chat_user.current_bulletin = bulletin
        chat_user.current_story = 0
        chat_user.current_fragment = 0
        # if first fragment of the first story is an answer put it a keyboard

        start_story(bulletin, chat_user, chat_id)
        chat_user.save()
        mp.track(chat_id, 'read_bulletin')
        mp.track(chat_id, 'read_story')
        mp.track(chat_id, 'read_fragment')

        return
    # load current bulletin
    else:
        bulletin = Bulletin.objects.get(id=chat_user.current_bulletin.id)

    # next should be working in spannish or other languages
    if "Next" in msg['text']:
        # check if there are more stories
        print (chat_user.current_bulletin.title, chat_user.current_story,
               chat_user.current_fragment)
        if len(bulletin.content) > chat_user.current_story + 1:
            chat_user.current_story += 1
            chat_user.current_fragment = 0

            # this code is repeated
            start_story(bulletin, chat_user, chat_id)
            chat_user.save()
            mp.track(chat_id, 'read_story')
            mp.track(chat_id, 'read_fragment')
            return
        else:
            bcu = BulletinChatUser(bulletin=chat_user.current_bulletin,
                                   chat_user=chat_user)
            bcu.save()

            unread_bulletins = get_unread_bulletins(chat_user)
            if len(unread_bulletins) > 0:
                chat_user.current_bulletin = unread_bulletins[0]
                chat_user.current_story = 0
                chat_user.current_fragment = 0
                start_story(bulletin, chat_user, chat_id)
                chat_user.save()
                mp.track(chat_id, 'read_bulletin')
                mp.track(chat_id, 'read_story')
                mp.track(chat_id, 'read_fragment')
                return
            else:
                chat_user.current_bulletin = None
                bot.sendMessage(chat_id, 'No more news for today')
                chat_user.save()
                return

    is_answer = False
    while not is_answer:
        story = Story.objects(
            bulletin=chat_user.current_bulletin
        ).order_by('order')[chat_user.current_story]
        story_fragments = Fragment.objects(story=story).order_by('order')
        fragment = story_fragments[chat_user.current_fragment]
        bot.sendChatAction(chat_id, "typing")
        # while there is content in this story
        if len(story.content) > chat_user.current_fragment + 1:

            f_next = story_fragments[chat_user.current_fragment + 1]
            if f_next.type == fragment.TYPE_ANSWER:
                # send answer
                is_answer = True
                answer = f_next
                show_keyboard = {
                    'keyboard': [
                        [Emoji.shortcode_to_unicode(answer.text), 'Next']
                    ],
                    'one_time_keyboard': True,
                    'resize_keyboard': True
                }
                send_fragment(chat_id, fragment, show_keyboard)
                chat_user.current_fragment += 2
                mp.track(chat_id, 'read_fragment')

            else:
                send_fragment(chat_id, fragment, None)
                chat_user.current_fragment += 1
                mp.track(chat_id, 'read_fragment')

        else:

            # check if there are more histories of this bulletin:
            if len(bulletin.content) > chat_user.current_story + 1:
                chat_user.current_story += 1
                chat_user.current_fragment = 0
                start_story(bulletin, chat_user, chat_id)
                mp.track(chat_id, 'read_story')
                mp.track(chat_id, 'read_fragment')
                return

            # look for unread bulletins
            else:
                print 'NO MORE CONTENT'

                bcu = BulletinChatUser(bulletin=chat_user.current_bulletin,
                                       chat_user=chat_user)
                bcu.save()

                chat_user.current_bulletin = None
                chat_user.current_story = None
                chat_user.current_fragment = None
                bot.sendMessage(chat_id, 'No more news for today')
                chat_user.save()

                # find more content NOT IN READ
                unread_bulletins = get_unread_bulletins(chat_user)
                if len(unread_bulletins) > 0:
                    chat_user.current_bulletin = unread_bulletins[0]
                    chat_user.current_story = 0
                    chat_user.current_fragment = 0
                    chat_user.save()
                    start_story(bulletin, chat_user, chat_id)
                    return
                else:
                    chat_user.current_bulletin = None
                    bot.sendMessage("No more bulletins to show! wait a couple "
                                    "of hours")
                    chat_user.save()
                    return

        chat_user.save()

bot = telepot.Bot(settings.TELEGRAM_TOKEN)

with create_app().app_context():
    bot.message_loop(on_chat_message)

while 1:
    time.sleep(10)
