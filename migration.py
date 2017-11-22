from datetime import datetime, timedelta

from newsbot.forms import strip_filter
from newsbot.models import (
    Account, Bulletin, Fragment, User, ChatUser,
    Story, InformationMessage, BulletinChatUser,
    InformationMessageChatUser, AccountStats,
    PollQuestions)

from newsbot.server import create_app

app = create_app()

collection = Bulletin._get_collection()
collection.update_many({}, {'$rename': {'published': 'publish_at'}})

a = Account(name='Test account', audience=Account.AUDIENCE_CHOICES[0][0])
a.bulletins = [x for x in Bulletin.objects.all() if not x.account]
a.save()

for b in Bulletin.objects.all():
    if not b.expire_hours:
        b.expire_hours = 0
        b.save()

    if not b.account:
        b.account = a
        b.save()

    if not b.is_published:
        b.is_published = False
        b.save()

for f in Fragment.objects.filter(type=Fragment.TYPE_ANSWER):
    if not f.action:
        f.action = Fragment.ACTION_CONTINUE
        f.save()

for f in Fragment.objects.filter(type__in=[Fragment.TYPE_ANSWER,
                                           Fragment.TYPE_PARAGRAPH]):
    if f.text:
        f.text = strip_filter(f.text)
        f.save()

for u in User.objects.all():
    if not u.role:
        u.role = 'admin'
        u.save()

#for cu in ChatUser.objects.all():
#    print(cu.chat_id)
#    print(cu.disabled)
#    print(cu.account_id)
#    if not cu.disabled:
#        cu.disabled = 0
#        cu.save()

for a in Account.objects.all():
    if not a.welcome_message_1:
        a.welcome_message_1 = "I am a bot!"
    if not a.welcome_message_2:
        a.welcome_message_2 = "Thanks for adding me as a friend, I will keep you updated! You can interact with me with the buttons that appear at the bottom"
    if not a.welcome_answer_1:
        a.welcome_answer_1 = "Like that?"
    if not a.welcome_message_3:
        a.welcome_message_3 = "That's it! Are you ready?"
    if not a.welcome_answer_2_option_1:
        a.welcome_answer_2_option_1 = "Yess"
    if not a.welcome_answer_2_option_2:
        a.welcome_answer_2_option_2 = "Of course!"
    if not a.owner:
        if(len(a.users)<1): print('Account without users: ',a.id,a.users)
        else: a.owner = a.users[0]
    a.save()

# add created_at and updated_at fields for all models
all_models = [
    Account, Bulletin, Fragment, User, ChatUser,
    Story, InformationMessage, BulletinChatUser,
    InformationMessageChatUser, AccountStats
]

now = datetime.utcnow()

def get_valid_bulletins(bulletins):
    valid_bulletins = []
    for b in bulletins:
        publish_at = getattr(b, 'publish_at', None)
        if publish_at:
            valid_bulletins.append(b)

    return valid_bulletins

def read_first_bulletin_date(entity):
    if isinstance(entity, ChatUser) and entity.read_bulletins:
        bulletins = entity.read_bulletins
    elif isinstance(entity, Account) and entity.bulletins:
        bulletins = entity.bulletins
    else:
        return now

    valid_bulletins = sorted(
        get_valid_bulletins(bulletins),
        key=lambda b: b.publish_at, reverse=False
    )
    if valid_bulletins:
        return valid_bulletins[0].publish_at

    # take now if entity reference only to
    # not existing bulletin or has no bulletins
    return now

'''
for model in all_models:
    for document in model.objects().select_related():
        if isinstance(document, (ChatUser, Account,)):
            if not document.created_at:
                document.created_at = read_first_bulletin_date(document)
            if not document.updated_at:
                document.updated_at = now
        else:
            if not document.created_at:
                document.created_at = now
            if not document.updated_at:
                document.updated_at = now

        document.save()
'''
def daterange(start, end, step=timedelta(days=1)):
    current = start
    while current <= end:
        yield current
        current += step

def get_new_users(date, account_users):
    """get the number of users with creation date equal to that day."""
    users = filter(
        lambda u: u.created_at.date() == date,
        account_users
    )
    return len(list(users))

def get_dropped_users(date, account_users):
    """the users whose last bulletin is from that day."""
    dropped_users = 0
    for user in account_users:

        # only if user is disabled
        if user.disabled == 1:

            bulletins = sorted(
                get_valid_bulletins(user.read_bulletins),
                key=lambda b: b.publish_at, reverse=True
            )

            if bulletins and bulletins[0].publish_at.date() == date:
                dropped_users += 1

    return dropped_users

# generate AccountStats for existing accounts
'''
account_stats = []
for account in Account.objects():
    # generate AccountStats entities from interval [Account.created_at: today]
    start, end = account.created_at.date(), now.date()
    account_users = ChatUser.objects(account_id=account)

    exists_account_stats = AccountStats.objects(
        account=account)

    # active_users calculation algorithm
    #1 day active_users = new_users(day 1)
    #2 day active_users = active_users(day 1) + new_users(day 2) - dropped_users(day 2)
    #n day active_users = active_users(day n-1) + new_users(day n) - dropped_users(day n)
    active_users = 0

    total_droped_users = ChatUser.objects(account_id=account, disabled=1).count()

    for i, date in enumerate(daterange(start, end)):
        def comp(stat):
            return stat.date.date() == date

        stat = next(filter(comp, exists_account_stats), None)
        if stat:
            # ignore existing stats
            total_droped_users -= stat.dropped_users
            active_users += stat.new_users
            if i != 0:
                active_users -= stat.dropped_users

            print("Ignore duplicate account_stat(account=%s, date=%s)" % (account.id, date))
            continue

        new_users = get_new_users(date, account_users)
        dropped_users = get_dropped_users(date, account_users)
        total_droped_users -= dropped_users
        active_users += new_users
        if i != 0:
            active_users -= dropped_users

        if date == end:
            dropped_users = dropped_users + total_droped_users

        enabled_users = ChatUser.objects(account_id=account, disabled=0).count()
        assert active_users >= 0

        account_stats.append(AccountStats(
            new_users=new_users,
            dropped_users=dropped_users,
            active_users=active_users,
            enabled_users=enabled_users,
            date=date, created_at=now, updated_at=now,
            account=account
        ))

    del account_users, exists_account_stats
'''
#if account_stats:
#    AccountStats.objects.insert(account_stats)

# poll questions ordering
for poll_fragment in Fragment.objects(type=Fragment.TYPE_POLL):
    # order_by('') disabled default meta ordering
    polls = PollQuestions.objects(fragment=poll_fragment).order_by('')

    if next(filter(lambda p: p.order != 0, polls), None):
        continue
    elif len(polls) > 1:
        # if all order fields is 0 then recalculate orders
        for index, p in enumerate(polls):
            p.order = index
            p.save()
