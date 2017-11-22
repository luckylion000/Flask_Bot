import sys

from werkzeug.serving import run_simple
from werkzeug.contrib.fixers import ProxyFix

from newsbot.server import create_app


application = create_app()
application.wsgi_app = ProxyFix(application.wsgi_app)

if __name__ == '__main__':
    run_simple(application.config.get('SERVER_HOST', 'localhost'),
               (sys.argv[1:] and
                int(sys.argv[1]) or application.config['SERVER_PORT']),
               application,
               use_reloader=True,
               threaded=True,
               extra_files='./templates/*')
