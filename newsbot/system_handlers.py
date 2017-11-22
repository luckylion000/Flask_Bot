from flask import (
    current_app as app,
    g,
    session
)
from flask_login import current_user

from .models import Account


def before_request():
    g.current_account = None
    account_id = session.get(app.config['ACTIVE_ACCOUNT_KEY'])

    if current_user.is_authenticated:
        if(len(current_user.accounts)<1): 
            print ('User no has any accounts')
            return
        if account_id is None:
            g.current_account = current_user.accounts[0]
        else:
            account = Account.objects.filter(
                id=account_id, users__in=[current_user.id]).first()
            g.current_account = account or current_user.accounts[0]


def after_request(response):
    key = app.config['ACTIVE_ACCOUNT_KEY']

    if current_user.is_authenticated and g.current_account is not None:
        session[key] = str(g.current_account.id)

    return response
