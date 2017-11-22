
from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
    current_app
)

from settings import TELEGRAM_ENDPOINT, FACEBOOK_APP_ID, FACEBOOK_APP_SECRET

from mongoengine.errors import NotUniqueError
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import login_manager
from .facebook_api import FacebookAPI, FacebookAuth
from .forms import (
    LoginForm,
    ProfileForm,
    RegisterForm,
    RegisterInAccountForm,
    AccountBaseForm,
    AccountOnboardingForm,
    AccountTelegramForm,
    AccountFacebookForm,
    AccountUserSearchForm,
    AccountForm,
    ForgotPasswordForm,
    ResetPasswordForm,
    NameEmailForm
)
from .helpers import (
    encrypt_password,
    generate_reset_password_token,
    get_user_from_reset_token,
    send_mail_reset,
    send_mail_invite_old,
    send_mail_invite_new,
    send_mail_early_access
)
from .models import Account, User, AccountFacebookPage
import telepot


bp = Blueprint('auth', __name__)


@login_manager.user_loader
def user_loader(email):
    return User.objects.filter(email=email).first()


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('index.index'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        login_user(form.user)

        _next = request.args.get('next')
        return redirect(_next or url_for('index.bulletins_list'))

    return render_template('auth/login.html', form=form)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        u = User(name=form.name.data,
                 email=form.email.data,
                 password=encrypt_password(form.password.data))
        a = Account(name=form.account.form.name.data,
                    audience=form.account.audience.data,timezone=form.account.timezone.data)

        u.save()
        a.save()

        u.accounts.append(a)
        a.owner = u
        a.users.append(u)

        u.save()
        a.save()

        login_user(u)

        return redirect(url_for('index.bulletins_list'))

    return render_template('auth/register.html', form=form)


@bp.route('/early_access', methods=['GET', 'POST'])
def early_access():
    form = NameEmailForm()

    if form.validate_on_submit():

        # send email to Xavi & Elies
        name = form.name.data
        email = form.email.data

        # send email to Person!
        send_mail_early_access(email=email, name=name)
        return redirect(url_for('index.index'))

    return render_template('auth/early_access.html', form=form)


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index.index'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = ProfileForm(
        data={'name': current_user.name, 'email': current_user.email})

    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.email = form.email.data

        if form.new_password.data:
            current_user.password = encrypt_password(form.new_password.data)

        current_user.save()

        flash('Saved successfully', 'success')

    return render_template('auth/profile.html', form=form)


@bp.route('/reset', methods=['GET', 'POST'])
def reset():

    form = ForgotPasswordForm()
    message = None

    if form.validate_on_submit():

        user = User.objects.filter(email=form.email.data).first()
        if user:
            token = generate_reset_password_token(user)
            send_mail_reset(user.email, token)
        else:
            current_app.logger.warning(
                "email: '%s' not found for password reset",
                form.email.data)

        flash('An e-mail has been sent', 'success')

    return render_template('auth/forgot_password.html', form=form)


@bp.route('/reset/<token>', methods=['GET', 'POST'])
def reset_token(token):

    (error, user) = get_user_from_reset_token(token)

    if error:
        flash(error, 'error')
        return redirect(url_for('auth.login'))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.password = encrypt_password(form.password.data)
        user.save()
        flash('Your password has been reset', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form, token=token, email=user.email)


@bp.route('/account/create', methods=['GET', 'POST'])
@login_required
def account_create():

    form = AccountForm()

    if form.validate_on_submit():

        user = current_user._get_current_object()

        a = Account(name=form.name.data,
                    audience=form.audience.data,
                    timezone=form.timezone.data,
                    owner=user, users=[user])
        a.save()

        user.accounts.append(a)
        user.save()

        g.current_account = a

        return redirect(url_for('index.bulletins_list'))

    return render_template('account/account_create.html', form=form)


@bp.route('/account/edit/<string:aid>', methods=['GET', 'POST'])
@login_required
def edit_account(aid):
    account = Account.objects.filter(
        id=aid, users__in=[current_user.id]).first_or_404()

    form = AccountBaseForm(obj=account)

    if form.validate_on_submit():
        form.populate_obj(account)
        account.save()

        g.current_account = account

        flash('Saved successfully', 'success')

    return render_template('account/account.html', account_id=aid, form=form)


@bp.route('/account/onboarding/edit/<string:aid>', methods=['GET', 'POST'])
@login_required
def edit_account_onboarding(aid):
    account = Account.objects.filter(
        id=aid, users__in=[current_user.id]).first_or_404()

    form = AccountOnboardingForm(obj=account)

    if form.validate_on_submit():
        form.populate_obj(account)
        account.save()
        g.current_account = account
        flash('Saved successfully', 'success')

    return render_template('account/account_onboarding.html', account_id=aid, form=form,name=account.name)


@bp.route('/account/telegram/edit/<string:aid>', methods=['GET', 'POST'])
@login_required
def edit_account_telegram(aid):
    account = Account.objects.filter(
        id=aid, users__in=[current_user.id]).first_or_404()

    form = AccountTelegramForm(obj=account)

    if form.validate_on_submit():
        form.populate_obj(account)
        account.save()

        host = request.url_root.replace('/', '').replace('http:', '').replace('https:', '')
        if account.botconnection_telegram_token != "":
            bot = telepot.Bot(account.botconnection_telegram_token, endpoint=TELEGRAM_ENDPOINT)
            bot.setWebhook("https://" + host + "/telegram/" + account.botconnection_telegram_token)
        print(account.botconnection_telegram_token)

        g.current_account = account

        flash('Saved successfully', 'success')

    return render_template('account/account_telegram.html', account_id=aid, form=form,name=account.name)


@bp.route('/account/facebook/edit/<string:aid>', methods=['GET', 'POST'])
@login_required
def edit_account_facebook(aid):
    account = Account.objects.filter(
        id=aid, users=current_user.id).first_or_404()

    form = AccountFacebookForm()
    form.page.choices = [('', 'none')] + [(p.id, p.name) for p in account.facebook_pages]

    if form.validate_on_submit():

        if form.page.data:

            pages = {page.id: page for page in account.facebook_pages}
            account.botconnection_facebook_page_id = form.page.data
            account.botconnection_facebook_token = pages[form.page.data].access_token

            api = FacebookAPI(account.botconnection_facebook_token)
            api.subscribed_apps()

        else:
            account.botconnection_facebook_page_id = ''
            account.botconnection_facebook_token = ''

        try:
            account.save()
        except NotUniqueError as e:
            flash("page '%s' already used" % pages[form.page.data].name, 'error')
        else:
            flash('Saved successfully', 'success')
        return redirect(url_for('auth.edit_account_facebook', aid=account.id))

    else:
        form.page.data = account.botconnection_facebook_page_id

    return render_template('account/account_facebook.html',
                           account=account,
                           form=form)


@bp.route('/account/facebook/get_pages/<string:aid>', methods=['GET', 'POST'])
@login_required
def account_facebook_get_pages(aid):

    account = Account.objects.filter(
        id=aid, users=current_user.id).first_or_404()

    redirect_uri = url_for('auth.account_facebook_get_pages', aid=aid, _external=True)
    auth_api = FacebookAuth(FACEBOOK_APP_ID, FACEBOOK_APP_SECRET)

    code = request.args.get('code')
    if not code:
        return redirect(auth_api.get_login_url(redirect_uri))

    token = auth_api.get_access_token(code, redirect_uri)

    api = FacebookAPI(token['access_token'])
    data = api.get_batch_user_and_accounts()
    (user, fb_pages) = (data[0]['body'], data[1]['body'])

    account.facebook_username = user['name']

    account.facebook_pages = []
    for page in fb_pages['data']:
        account.facebook_pages.append(
            AccountFacebookPage(id=page['id'],
                                access_token=page['access_token'],
                                name=page['name']))

    account.botconnection_facebook_token = ''
    account.botconnection_facebook_page_id = ''

    account.save()

    flash('pages updated, select which one you want to link the bot with', 'success')

    return redirect(url_for('auth.edit_account_facebook', aid=account.id))


@bp.route('/account/users/edit/<string:aid>', methods=['GET', 'POST'])
@login_required
def edit_account_users(aid):
    account = Account.objects.filter(
        id=aid, users__in=[current_user.id]).first_or_404()

    form = AccountUserSearchForm()
    account_users = g.current_account.users
    if form.validate_on_submit():
        user = User.objects.filter(email=form.email.data).first()
        if(user):
            return render_template('account/account_users_add.html', 
                                    account_id=aid,account_owner=account.owner,
                                    name=account.name, users=account_users,
                                    user_email=user.email,user_id=user.id)
        else:
            form = RegisterInAccountForm()
            return render_template('account/account_users_register.html', 
                                    account_id=aid,account_owner=account.owner,
                                    name=account.name, users=account_users,form=form)

    return render_template(
        'account/account_users.html',
        account_id=aid,
        account_owner=account.owner,
        name=account.name, users=account_users,
        form=form)


@bp.route('/account/users/confirm_access/<string:aid>/<string:uid>', methods=['GET'])
@login_required
def account_confirm_access(aid, uid):

    account = Account.objects.filter(id=aid, users=current_user.id).first_or_404()
    user = User.objects.filter(id=uid).first_or_404()

    if account not in user.accounts:
        user.accounts.append(account)
        user.save()

    if user not in account.users:
        account.users.append(user)
        account.save()

    send_mail_invite_old(user, account)
    return redirect(url_for('auth.edit_account_users', aid=aid))


@bp.route('/account/users/add/<string:aid>', methods=['GET', 'POST'])
@login_required
def register_in_account(aid):
    
    account = Account.objects.filter(id=aid, users=current_user.id).first_or_404()

    form = RegisterInAccountForm()

    if form.validate_on_submit():

        user = User(name=form.name.data,
                    email=form.email.data,
                    password=encrypt_password(form.password.data))

        user.accounts.append(account)
        account.users.append(user)

        user.save()
        account.save()

        send_mail_invite_new(user, account, form.password.data)

        return redirect(url_for('auth.edit_account_users', aid=aid))

    return render_template('account/account_users_register.html',
                           account_id=aid,
                           account_owner=account.owner,
                           name=account.name,
                           users=g.current_account.users,
                           form=form)


@bp.route('/account/remove/<string:aid>/<string:uid>', methods=['GET'])
@login_required
def remove_user_from_account(aid,uid):
    account = Account.objects.filter(id=aid, users__in=[current_user.id]).first_or_404()
    user = User.objects.filter(id=uid).first_or_404()
    
    account_users = []
    for u in account.users:
        if not(str(u.id)==uid):account_users.append(u)
    account.users = account_users
    account.save()
    
    user_accounts = []
    for a in user.accounts:
        if not(str(a.id)==aid):user_accounts.append(a)
    user.accounts = user_accounts
    user.save()

    return redirect(url_for('auth.edit_account_users',aid=aid))


@bp.route('/account/switch/<string:aid>', methods=['GET', 'POST'])
@login_required
def switch_account(aid):
    account = Account.objects.filter(
        id=aid, users__in=[current_user.id]).first_or_404()

    g.current_account = account

    return redirect(url_for('index.bulletins_list'))
