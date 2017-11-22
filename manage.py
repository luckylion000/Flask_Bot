#!/usr/bin/env python

import click
from flask.cli import FlaskGroup

from newsbot.server import create_app


def create_newsbot_app(info):
    return create_app()


@click.group(cls=FlaskGroup, create_app=create_newsbot_app)
def cli():
    """This is a management script for newsbot application."""
    pass


if __name__ == '__main__':
    cli()
