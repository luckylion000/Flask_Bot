import os.path
import hashlib
import tempfile
import os

from uuid import uuid4
import itsdangerous

import boto3
from boto3.s3.transfer import S3Transfer
from botocore.client import Config
from flask import current_app as app, url_for, render_template
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from wtforms.validators import ValidationError
from flask_mail import Message

from .models import Fragment, User
from .extensions import mail

import settings

class S3Service(object):
    def __init__(self):
        for key in ['AWS_S3_KEY', 'AWS_S3_SECRET', 'AWS_S3_BUCKET',
                    'AWS_S3_REGION']:
            assert app.config.get(key) is not None

        self.s3 = boto3.client(
            's3',
            config=Config(signature_version='s3v4'),
            region_name=app.config['AWS_S3_REGION'],
            aws_access_key_id=app.config['AWS_S3_KEY'],
            aws_secret_access_key=app.config['AWS_S3_SECRET']
        )

    def upload(self, src_file):
        src_filename = secure_filename(src_file.data.filename)
        src_extension = os.path.splitext(src_filename)[1]

        dst_filename = uuid4().hex + src_extension

        # We should close the file before reading in order to ensure writing is
        # finished and file in not busy
        t = tempfile.NamedTemporaryFile(mode='wb', delete=False)
        t.write(src_file.data.read())
        t.close()

        try:
            transfer = S3Transfer(self.s3)
            transfer.upload_file(t.name,
                                 app.config['AWS_S3_BUCKET'],
                                 dst_filename,
                                 extra_args={'ACL': 'public-read'})
        finally:
            os.unlink(t.name)

        return ('https://s3-{AWS_S3_REGION}.amazonaws.com/'
                '{AWS_S3_BUCKET}/{file}').format(file=dst_filename,
                                                 **app.config)

    def delete(self, url):
        filename = os.path.split(url)[-1]
        ret = self.s3.delete_object(
            Bucket=app.config['AWS_S3_BUCKET'],
            Key=filename
        )

        # TODO replace with a humanized kind of an error
        assert 'ResponseMetadata' in ret
        assert ret['ResponseMetadata'].get('HTTPStatusCode', 0) == 204


def validate_fragments_order(fragments, ftype):
    if not fragments and ftype != Fragment.TYPE_ANSWER:
        raise ValidationError('First fragment must be an Answer')


def encrypt_password(password):
    return generate_password_hash(password, method='pbkdf2:sha512:5000')


def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    return value.strftime(format)


def md5(data):
    return hashlib.md5(data).hexdigest()


def generate_reset_password_token(user):
    password_hash = md5(user.password.encode('utf-8'))
    data = [user.email, password_hash]
    return itsdangerous.URLSafeTimedSerializer(app.secret_key).dumps(data)


def get_user_from_reset_token(token):

    serializer = itsdangerous.URLSafeTimedSerializer(app.secret_key)

    try:
        data = serializer.loads(token, max_age=86400)
    except itsdangerous.BadData:
        return ('invalid token', None)

    (email, password_hash) = data

    user = User.objects.filter(email=email).first()
    if user and md5(user.password.encode('utf-8')) == password_hash:
        return (None, user)

    return ('invalid token', None)


def send_mail_reset(email, token):

    reset_link = url_for('auth.reset_token', token=token, _external=True)

    msg = Message('Password Reset', recipients=[email])
    msg.body = render_template('email/reset_instructions.txt', reset_link=reset_link)
    msg.html = render_template('email/reset_instructions.html', reset_link=reset_link)

    mail.send(msg)


def send_mail_invite_old(user, account):

    index_link = url_for('index.index', _external=True)

    subject = 'You have been invited to collaborate with %s' % account.name
    msg = Message(subject, recipients=[user.email])
    msg.body = render_template('email/invite_user.txt',
                               username=user.name,
                               account_name=account.name,
                               index_link=index_link)
    msg.html = render_template('email/invite_user.html',
                               username=user.name,
                               account_name=account.name,
                               index_link=index_link)
    mail.send(msg)

def send_mail_invite_new(user, account, password):

    index_link = url_for('index.index', _external=True)

    subject = 'You have been invited to collaborate to %s' % account.name
    msg = Message(subject, recipients=[user.email])
    msg.body = render_template('email/invite_user_new.txt',
                               email=user.email,
                               account_name=account.name,
                               password=password,
                               index_link=index_link)
    msg.html = render_template('email/invite_user_new.html',
                               email=user.email,
                               account_name=account.name,
                               password=password,
                               index_link=index_link)
    mail.send(msg)


def send_mail_early_access(email, name):

    subject = 'Thank you for requesting early access!'
    msg = Message(subject, recipients=[email], bcc=settings.ADMINS_EMAIL)
    msg.body = render_template('email/early_access.txt',
                               email=email,
                               name=name)

    msg.html = render_template('email/early_access.html',
                               email=email,
                               name=name)
    mail.send(msg)

def stats_to_dicts(account_stats):
    def to_zero_if_none(value):
        if value is None:
            return 0
        return value

    result = []
    for _stat in account_stats:
        result.append({
            'active_users': to_zero_if_none(_stat['active_users']),
            'new_users': to_zero_if_none(_stat['new_users']),
            'dropped_users': to_zero_if_none(_stat['dropped_users']),
            'enabled_users': to_zero_if_none(_stat['enabled_users']),
            'messages_received': to_zero_if_none(_stat['messages_received']),
            'date': _stat['date'].strftime('%Y-%m-%d')
        })
    return result

def group_anwers(answers):
    """ group answers by question and calculate amount for each answer """
    questions = {}
    for _a in answers:
        pk = str(_a.question.pk)

        if questions.get(pk):
            q = questions[pk]
        else:
            q = {
                'name': _a.question.text,
                'chart': _a.question.attribute.chart,
                'answers': {}
            }

        # increment amout of answers
        if q['answers'].get(_a.answer):
            q['answers'][_a.answer] += 1
        else:
            q['answers'][_a.answer] = 1

        questions[pk] = q
    return questions

def env_setting(setting_name, default=''):

    """ Fetch setting value from env, if not exist take default """
    if os.environ.get(setting_name):
        return os.environ[setting_name]
    return default

def get_media_fragment_type(mimetype):
    if 'image' in mimetype:
        return Fragment.TYPE_IMAGE
    elif 'audio' in mimetype:
        return Fragment.TYPE_AUDIO
    elif 'video' in mimetype:
        return Fragment.TYPE_VIDEO
    else:
        return Fragment.TYPE_DOCUMENT
