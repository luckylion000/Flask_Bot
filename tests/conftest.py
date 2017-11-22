#!/usr/bin/env python

import os
import sys
import pytest
from mongoengine.connection import get_db
from newsbot.server import create_app


class TestingConfig(object):
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    TESTING = True
    WTF_CSRF_ENABLED = False
    ACTIVE_ACCOUNT_KEY = 'active_account_id'
    SERVER_NAME = 'localhost'
    BULLETIN_EXPIRE_HOURS = 2
    BULLETIN_NEW_TITLE_FORMAT = 'Draft for %m/%d/%Y at %H:%M'
    MAXIMUM_FILE_UPLOAD_SIZE_MB = 10
    MONGODB_SETTINGS = {
        'db': 'newsbot_test'
    }


@pytest.fixture(scope='function')
def app():
    sys.modules['newsbot.test.config'] = TestingConfig
    app = create_app()
    with app.app_context():
        get_db().client.drop_database(get_db().name)
        with app.test_request_context():
            yield app


@pytest.fixture(scope='function')
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def mock_s3_service(monkeypatch):
    monkeypatch.setattr(
        "newsbot.helpers.S3Service.__init__",
        lambda self: None
    )

    monkeypatch.setattr(
        "newsbot.helpers.S3Service.upload",
        lambda self, src_file: "http://localhost:5000/{f}".format(f=src_file.name)
    )
