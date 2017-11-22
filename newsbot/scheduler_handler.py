from celery import Celery
from flask import Blueprint, request
from .models import Account
from settings import LOCAL_BROKER


bp = Blueprint('scheduler_handler', __name__)
app = Celery('tasks', broker=LOCAL_BROKER)

@bp.route('/task/<name>', methods=['GET'])
def task_launch(name):
    print("task {name} is going to be launched!!!".format(name=name))
    return 'OK'
