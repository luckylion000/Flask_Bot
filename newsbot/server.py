
import logging
import logging.handlers
import os.path
import sys

from flask import Flask, request, render_template
from raven.contrib.flask import Sentry
#import redis

#from flask.ext.session import Session

from .admin import admin
from .assets import setup_assets
from .auth import bp as bp_auth
from .telegramhandler import bp as bp_telegram
from .facebookhandler import bp as bp_facebook
from .scheduler_handler import bp as bp_scheduler
from .extensions import csrf, db, login_manager, mail
from .management import shell_command
from .system_handlers import after_request, before_request
from .views import bp as bp_index
from .helpers import datetimeformat

sentry = Sentry()

def setup_logging(app):
    if not app.config.get('LOGGING_ENABLED'):
        return

    file_handler = logging.handlers.WatchedFileHandler(app.config['LOG_FILE'])
    file_handler.setFormatter(logging.Formatter(app.config['LOG_FORMAT']))
    app.logger.setLevel(app.config['LOG_LEVEL'])
    app.logger.addHandler(file_handler)

    if app.config.get('LOG_REQUEST', False):
        @app.before_request
        def before_request():
            if request.method == 'GET':
                app.logger.info(request.url)
            else:
                chunks = []
                for k, v in request.values.iteritems():
                    chunks.append('%s=%s' %
                                  (k, (v if k != 'password' else 'sorry')))
                app.logger.info('%s POST %s' % (request.url, '&'.join(chunks)))

    if app.config.get('LOG_RESPONSE', False):
        @app.after_request
        def after_request(response):
            app.logger.info(response.data)
            return response


def setup_management(app):
    app.cli.add_command(shell_command)

def page_not_found(e):
    go_back = request.referrer if request.referrer else '/'
    return render_template('404.html', go_back=go_back), 404

def create_app():
    project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    app = Flask(__name__,
                static_folder=os.path.join(project_root, 'static'),
                template_folder=os.path.join(project_root, 'templates'))

    if 'newsbot.test.config' in sys.modules:  # test config
        app.config.from_object(sys.modules['newsbot.test.config'])
    else:
        app.config.from_object('settings')

    #app.config.SESSION_TYPE = 'redis'
    #app.config.SESSION_USE_SIGNER = False
    #sess = Session()
    #sess.init_app(app)

    app.register_error_handler(404, page_not_found)
    app.after_request(after_request)
    app.before_request(before_request)
    app.secret_key = 's3cr3t'
    app.register_blueprint(bp_index, url_prefix='')
    app.register_blueprint(bp_auth, url_prefix='')
    app.register_blueprint(bp_telegram, url_prefix='')
    app.register_blueprint(bp_facebook, url_prefix='')
    app.register_blueprint(bp_scheduler, url_prefix='')

    app.jinja_env.tests['list'] = lambda x: isinstance(x, list)
    app.jinja_env.filters['datetimeformat'] = datetimeformat

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    admin.init_app(app)

    setup_management(app)
    setup_logging(app)
    setup_assets(app)

    csrf.exempt(bp_telegram)
    sentry.init_app(app)

    mail.init_app(app)

    return app
