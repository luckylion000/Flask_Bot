import os.path
import sys

import click
from flask.cli import with_appcontext


@click.command('ishell', short_help='Runs IPython shell in the app context.')
@click.option('--no-ipython', default=False)
@with_appcontext
def shell_command(no_ipython):
    """Runs an interactive Python shell in the context of a given
    Flask application.  The application will populate the default
    namespace of this shell according to it's configuration.

    This is useful for executing small snippets of management code
    without having to manually configuring the application.
    """
    import code
    from flask.globals import _app_ctx_stack
    app = _app_ctx_stack.top.app
    banner = 'Python %s on %s\nApp: %s%s\nInstance: %s' % (
        sys.version,
        sys.platform,
        app.import_name,
        app.debug and ' [debug]' or '',
        app.instance_path,
    )
    ctx = {}

    # Support the regular Python interpreter startup script if someone
    # is using it.
    startup = os.environ.get('PYTHONSTARTUP')
    if startup and os.path.isfile(startup):
        with open(startup, 'r') as f:
            eval(compile(f.read(), startup, 'exec'), ctx)

    ctx.update(app.make_shell_context())

    from .extensions import db
    import newsbot.models
    ctx['db'] = db
    ctx['models'] = newsbot.models

    if not no_ipython:
        try:
            from IPython import embed
            embed(banner1=banner, user_ns=ctx)
            return
        except ImportError:
            pass

    code.interact(banner=banner, local=ctx)
