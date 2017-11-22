import imghdr

from flask_login import current_user
from flask_wtf import FlaskForm as Form
from werkzeug.security import check_password_hash
from wtforms import (
    BooleanField,
    DateTimeField,
    FieldList,
    FileField,
    FormField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
    DateField
)

from wtforms.validators import (
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
    StopValidation,
    ValidationError
)

from .models import (
    Account, Fragment, User, OptionsItem,
    Invitation, ChatUserAttribute)

from datetime import datetime, timedelta

MIN_PASSWORD_LENGTH = 3


def strip_filter(val):
    if val is None:
        return val

    return val.strip().replace('\u2063', '')

def last_30days():
    return datetime.utcnow().date() - timedelta(days=30)


class MediaFileRequired(object):
    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        if (field.data is None):
            message = self.message or 'An file is required'
            raise StopValidation(message)

        field.data.seek(0)


class LoginForm(Form):
    email = StringField('Email', [InputRequired()])
    password = PasswordField('Password', [InputRequired()])

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.user = None

    def validate(self):
        success = super(LoginForm, self).validate()
        if not success:
            return success

        user = User.objects.filter(email=self.email.data).first()
        if (user is not None and
                check_password_hash(user.password, self.password.data)):
            self.user = user
            return True

        self.email.errors.append('Invalid username or password')

        return False


class BulletinAddForm(Form):
    title = StringField('Title', validators=[InputRequired()],
                        filters=[strip_filter])
    is_breaking = BooleanField('Breaking')
    is_published = BooleanField('Publish')
    send_immediately = BooleanField('Send immediately')
    expire_hours = IntegerField('User will no longer see this bulletin after..')
    publish_at = DateTimeField('Publish on', format='%m/%d/%Y %H:%M')

    def obj_validate_publish(self, obj):
        # We should do this check only when a user is going to publish a
        # bulletin
        if not self.is_published.data:
            return True

        if not obj.content:
            self.is_published.errors.append('Please add at least one story')
            return False

        for s in obj.content:
            if not s.content:
                self.is_published.errors.append(
                    'Every story has to contain at least one fragment')
                return False
            f = Fragment.objects.filter(story=s)

            # Actually this should never happen, due to we check it when
            # adding/editing a story
            if f[0].type != Fragment.TYPE_ANSWER:
                self.is_published.errors.append(
                    'Make sure a story has Answer as a first fragment')
                return False

            if not [x for x in f if x.type != Fragment.TYPE_ANSWER]:
                self.is_published.errors.append(
                    'Make sure a story has at least one non-answer fragment')
                return False


            def _check_polls(fragments):

                for i in range(len(fragments)-1):
                    (t1, t2) = fragments[i].type, fragments[i+1].type
                    if t1 == Fragment.TYPE_POLL and t2 == Fragment.TYPE_ANSWER:
                        return False

                return True

            if not _check_polls(f):
                self.is_published.errors.append(
                    "In story '%s' after poll fragment has to be non-answer fragment" % s.title)
                return False

        return True


class TextForm(Form):
    text = StringField('Text', validators=[InputRequired()],
                       filters=[strip_filter])


class QuestionForm(TextForm):
    attribute = StringField('Attribute',
                            validators=[InputRequired()],
                            filters=[strip_filter])

    def validate(self):
        success = super(QuestionForm, self).validate()
        if not success:
            return False

        attr = ChatUserAttribute.objects.\
            filter(id=self.attribute.data).first()
        if not attr:
            self.attribute.errors.append('Attribute not exists')
            return False
        else:
            self.attribute = attr

        return True


class PollForm(TextForm):
    question = FieldList(
        StringField('Question', validators=[InputRequired()]),
        min_entries=1)


class ActivateForm(Form):
    active = BooleanField('Active')



class AnswerForm(TextForm):
    action = SelectField(label='Action',
                         validators=[InputRequired()],
                         filters=[strip_filter],
                         choices=Fragment.ACTION_CHOICES)


class UploadMediaForm(Form):
    text = FileField('Document', filters=[strip_filter])
    media = FileField('Media', [MediaFileRequired()])


class OrderForm(Form):
    object_id = StringField('Id', validators=[InputRequired()],
                            filters=[strip_filter])
    order = IntegerField('Order', [InputRequired(), NumberRange(min=1)])


class OrderChangeForm(Form):
    objects = FieldList(FormField(OrderForm), [InputRequired()])


class AccountForm(Form):
    name = StringField('Company', validators=[InputRequired()],
                       filters=[strip_filter])
    timezone = SelectField('Timezone', coerce=str,
                           choices=Account.TIMEZONES_CHOICES,
                           default=Account.timezone.default)
    audience = SelectField('Audience', [InputRequired()],
                           coerce=int,
                           choices=Account.AUDIENCE_CHOICES)

class NameEmailForm(Form):
    name = StringField('Name', validators=[InputRequired()],
                       filters=[strip_filter])
    email = StringField('Email', validators=[InputRequired(), Email()],
                        filters=[strip_filter])


class RegisterForm(NameEmailForm):
    password = PasswordField('Password',
                             validators=[InputRequired(),
                                         Length(min=MIN_PASSWORD_LENGTH)],
                             filters=[strip_filter])
    code = StringField('Code', validators=[InputRequired()],
                       filters=[strip_filter])
    account = FormField(AccountForm, [InputRequired()])

    def validate_email(form, field):
        if User.objects.filter(email=field.data).count():
            raise ValidationError('User with such email already exists')

    def validate_code(form, field):
        if not Invitation.objects.filter(code=field.data).count():
            raise ValidationError('Not valid invation code')

class RegisterInAccountForm(NameEmailForm):
    password = PasswordField('Password',
                             validators=[InputRequired(),
                                         Length(min=MIN_PASSWORD_LENGTH)],
                             filters=[strip_filter])

    def validate_email(form, field):
        if User.objects.filter(email=field.data).count():
            raise ValidationError('User with such email already exists')

class ProfileForm(NameEmailForm):
    old_password = PasswordField('Old password',
                                 validators=[Optional(),
                                             Length(min=MIN_PASSWORD_LENGTH)],
                                 filters=[strip_filter])
    new_password = PasswordField(
        'New password',
        validators=[Optional(),
                    Length(min=MIN_PASSWORD_LENGTH),
                    EqualTo('new_password1', 'Passwords do not match')],
        filters=[strip_filter]
    )
    new_password1 = PasswordField(
        'Confirm password',
        validators=[Optional(),
                    Length(min=MIN_PASSWORD_LENGTH),
                    EqualTo('new_password', 'Passwords do not match')],
        filters=[strip_filter]
    )

    def validate(self):
        success = super(ProfileForm, self).validate()
        if not success:
            return success

        together = [self.old_password, self.new_password, self.new_password1]

        if any(x.data for x in together) and not all(x.data for x in together):
            for f in together:
                if not f.data:
                    f.errors.append('This field required')

            return False

        if any(x.data for x in together):
            if self.new_password.data != self.new_password1.data:
                self.new_password.errors.append('Passwords mismatch')
                return False

            if not check_password_hash(current_user.password,
                                       self.old_password.data):
                self.old_password.errors.append('Invalid password')
                return False

        return True

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self
class OptionsForm(Form):
    text = StringField("Text: ", render_kw={"placeholder": "Text"})
    value = StringField('Value: ', render_kw={"placeholder": "Value"})

class ChatUserAttributeAddForm(Form):
    attribute = StringField('Attribute:', validators=[InputRequired()],  filters=[strip_filter])
    type = SelectField('type:',choices=[('int','int'),('float','float'),('text','text')])
    chart = SelectField('chart:',choices=[('bars','bars'),('pie','pie')])
    options = FieldList(FormField(OptionsForm), min_entries=1) 

    def obj_validate_publish(self, obj):
        # We should do this check only when a user is going to publish a
        # bulletin
        if len(self.attribute.data)<1:
            self.attribute.errors.append('This field required')
            return False
        if not(self.type.data in ['int','float','text']):
            self.attribute.errors.append('Only int,float or text')
            return False
        if not(self.chart.data in ['bars','pie']):
            self.attribute.errors.append('Only bars or pie')
            return False

        return True
    def populate_obj(self, obj):
        obj.attribute = self.attribute.data
        obj.type = self.type.data
        obj.chart = self.chart.data
        options = []
        for i in self.options.data:
            if(len(i['text'])==0 and len(i['value'])==0):continue
            t = OptionsItem()
            t.text = i['text']
            t.value = i['value']
            options.append(t)
        obj.options = options
        return obj


#--------------account-----------------
class AccountBaseForm(Form):
    name = StringField('Company', validators=[InputRequired()],
                       filters=[strip_filter])
    timezone = SelectField('Timezone',coerce=str,choices=Account.TIMEZONES_CHOICES)
    up_to_date_message = StringField('Up to date message', validators=[InputRequired()],
                       filters=[strip_filter])
    unknown_answer_message = StringField('Unknown answer message', validators=[InputRequired()],
                       filters=[strip_filter])
    skip_poll_message = StringField('Skip poll message', validators=[InputRequired()],
                       filters=[strip_filter])


class AccountOnboardingForm(Form):
    welcome_message_1 = TextAreaField('Welcome message 1', validators=[InputRequired()],filters=[strip_filter])
    welcome_message_2 = TextAreaField('Welcome message 2', validators=[InputRequired()],filters=[strip_filter])
    welcome_answer_1 = TextAreaField('Answer 1', validators=[InputRequired()],filters=[strip_filter])
    welcome_message_3 = TextAreaField('Welcome message 3', validators=[InputRequired()],filters=[strip_filter])
    welcome_answer_2_option_1 = TextAreaField('Answer 2 (option 1)', validators=[InputRequired()],filters=[strip_filter])
    welcome_answer_2_option_2 = TextAreaField('Answer 2 (option 2)', validators=[InputRequired()],filters=[strip_filter])


class AccountTelegramForm(Form):
    botconnection_telegram_name = StringField('Telegram bot name', validators=[InputRequired()],
                       filters=[strip_filter])
    botconnection_telegram_token = StringField('Telegram token', validators=[InputRequired()],
                       filters=[strip_filter])


class AccountFacebookForm(Form):
    page = SelectField(label='Facebook Page')


class AccountUserSearchForm(Form):
    email = StringField('Email', validators=[Email()],filters=[strip_filter])


class ForgotPasswordForm(Form):
    email = StringField(
        'Email',
        validators=[InputRequired(message='Email not provided'),
                    Email(message='Invalid email address')],
        filters=[strip_filter])


class ResetPasswordForm(Form):
    password = PasswordField(
        'New password',
        validators=[InputRequired(message='Password not provided'),
                    Length(min=MIN_PASSWORD_LENGTH)])

    password_confirm = PasswordField(
        'Confirm password',
        validators=[EqualTo('password', message='Passwords do not match')])


class AccountStatsDetailForm(Form):
    date_to = DateField('To', format='%m/%d/%Y',
        default=datetime.utcnow().date, validators=[Optional()]
    )
    date_from = DateField('From', format='%m/%d/%Y',
        default=last_30days, validators=[Optional()]
    )

    def __init__(self, *args, **kwargs):
        kwargs['csrf_enabled'] = False
        super(AccountStatsDetailForm, self).__init__(*args, **kwargs)
