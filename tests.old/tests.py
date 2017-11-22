import os.path
import sys
import unittest

from datetime import datetime

from flask import url_for
from flask_login import current_user
from wtforms.validators import ValidationError

LOGIN = 'login'
PASSWORD = 'pass'


class TestingConfig(object):
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    TEST_IMG = os.path.join(PROJECT_ROOT, 'tests', 'test.png')

    TESTING = True
    LOGIN_DISABLED = True
    USERS = {LOGIN: PASSWORD}
    SECRET_KEY = 'secret'
    WTF_CSRF_ENABLED = False
    WTF_CSRF_METHODS = ['xxx']

    ACTIVE_ACCOUNT_KEY = 'active_account_id'

    # TODO replace with mongomock, once FlaskMongoengine supports it
    MONGODB_SETTINGS = {
        'db': 'test_db',
        'host': 'localhost',
    }


sys.modules['newsbot.test.config'] = TestingConfig


from newsbot.server import create_app  # NOQA
from newsbot.models import Account, Bulletin, Fragment, Story, User  # NOQA


app = create_app()


class BotTestCase(unittest.TestCase):

    app = app.test_client()

    def setUp(self):
        ctx = app.test_request_context()
        ctx.push()

        self.register_data = {
            'name': 'user',
            'password': 'passwd',
            'email': 'asd@asd.asd',
            'account-name': 'company',
            'account-audience': Account.AUDIENCE_CHOICES[0][0]
        }

        self._register(self.register_data['email'])

        self.user = User.objects.get(email=self.register_data['email'])
        self.b = Bulletin(account=self.user.accounts[0],
                          publish_at=datetime.now(),
                          title='xxx',
                          expire_hours=2)
        self.b.save()
        self.user.accounts[0].bulletins.append(self.b)
        self.user.accounts[0].save()

        self.s = []
        self.f = []
        for x in range(2):
            s = Story(title='xx', lead='xx', bulletin=self.b, order=x + 1)
            s.save()
            self.b.content.append(s)
            self.b.save()

            self.s.append(s)

        for idx, s in enumerate(self.s):
            f = Fragment(type=Fragment.TYPE_ANSWER, text='xx', story=s,
                         order=idx)
            f.save()
            s.content.append(f)
            s.save()

            self.f.append(f)

        self.login_url = url_for('auth.login')

    def tearDown(self):
        Fragment.objects.delete()
        Story.objects.delete()
        Bulletin.objects.delete()
        User.objects.delete()
        Account.objects.delete()

    def _register(self, email):
        data = self.register_data.copy()
        data['email'] = email

        return self.app.post(url_for('auth.register'), data=data)

    def test_register(self):
        email = 'xxx@xxx.xx'

        self.assertEqual(User.objects.count(), 1)
        rv = self._register(email=email)
        self.assertEqual(rv.status_code, 302)
        self.assertEqual(User.objects.count(), 2)
        self.assertEqual(User.objects.filter(email=email).count(), 1)

    def test_login(self):
        with self.app:
            rv = self.app.post(self.login_url, data=dict(
                email=self.register_data['email'],
                password=self.register_data['password']
            ))

            self.assertTrue('Location' in rv.headers, rv.data)
            self.assertEqual(current_user.email, self.register_data['email'])

    def test_fragment_delete_rules(self):
        f = self.f[0]
        s = f.story

        self.assertTrue(f in s.content)
        f.delete()

        s = Story.objects.get(id=s.id)
        self.assertFalse(f in s.content)

    def test_story_delete_rules(self):
        s = self.s[0]
        b = s.bulletin

        self.assertTrue(s in b.content)
        self.assertEqual(Fragment.objects.count(), 2)

        s.delete()
        self.assertEqual(Fragment.objects.count(), 1)

        b = Bulletin.objects.get(id=b.id)
        self.assertFalse(s in b.content)

    def test_bulletin_delete_rules(self):
        self.b.delete()

        self.assertEqual(Fragment.objects.count(), 0)
        self.assertEqual(Story.objects.count(), 0)
        self.assertEqual(Bulletin.objects.count(), 0)

    def test_account_delete_rules(self):
        self.assertEqual(len(User.objects.first().accounts), 1)

        self.user.accounts[0].delete()

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(User.objects.first().accounts), 0)

        self.assertEqual(Account.objects.count(), 0)
        self.assertEqual(Fragment.objects.count(), 0)
        self.assertEqual(Story.objects.count(), 0)
        self.assertEqual(Bulletin.objects.count(), 0)

    def test_user_delete_rules(self):
        self.assertEqual(len(Account.objects.first().users), 1)

        self.user.delete()

        self.assertEqual(Account.objects.count(), 1)
        self.assertEqual(len(Account.objects.first().users), 0)
        self.assertEqual(Fragment.objects.count(), 2)
        self.assertEqual(Story.objects.count(), 2)
        self.assertEqual(Bulletin.objects.count(), 1)

    def test_first_fragment_must_be_answer(self):
        s = Story(title='xx', lead='xx', bulletin=self.b,
                  order=len(self.b.content) + 1)
        s.save()

        def post(u):
            self.app.post(u, data={'text': 'text'})

        def post_img(u):
            with open(TestingConfig.TEST_IMG, 'rb') as f:
                self.app.post(u, data={'image': f})

        with self.app:
            self.app.post(self.login_url, data=dict(
                email=self.register_data['email'],
                password=self.register_data['password']
            ))

            url = url_for('index.stories_paragraph_add', sid=s.id)
            self.assertRaises(ValidationError, post, url)

            url = url_for('index.stories_image_add', sid=s.id)
            self.assertRaises(ValidationError, post_img, url)

            post(url_for('index.stories_answer_add', sid=s.id))


if __name__ == '__main__':
    unittest.main()
