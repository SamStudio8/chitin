import getpass
import datetime
import os
import uuid

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import util

app = Flask(__name__, template_folder='web/templates')
home = os.path.expanduser('~')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + home + '/.chitin.dev.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

#class Labbook(db.Model):
#    uuid = db.Column(db.String(40), primary_key=True)
#
#    def __init__(self, path):
#        self.uuid = str(uuid.uuid4())

class Experiment(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    base_path = db.Column(db.String(512))

    #FUTURE(samstudio8) Experiments belong to books
    #book_id = db.Column(db.Integer, db.ForeignKey('labbook.uuid'))
    #book = db.relationship('Labbook', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, path):
        self.uuid = str(uuid.uuid4())
        self.base_path = os.path.abspath(path)

    def get_path(self):
        return os.path.join(self.base_path, self.uuid)

class Run(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)

    exp_id = db.Column(db.Integer, db.ForeignKey('experiment.uuid'))
    exp = db.relationship('Experiment', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, exp_uuid):
        self.uuid = str(uuid.uuid4())
        self.exp = exp_uuid

    def get_path(self):
        return os.path.join(self.exp.get_path(), self.uuid)

class EventGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    run_uuid = db.Column(db.Integer, db.ForeignKey('run.uuid'))
    run = db.relationship('Run', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, run_uuid=None):
        if run_uuid is not None:
            self.run = run_uuid

class RunMetadatum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40))
    value = db.Column(db.String(40))

    run_uuid = db.Column(db.Integer, db.ForeignKey('run.uuid'))
    run = db.relationship('Run', backref=db.backref('rmeta', lazy='dynamic'))

    def __init__(self, run_uuid, key, value):
        self.run = run_uuid
        self.key = key
        self.value = str(value)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(512))

    def __init__(self, path):
        self.path = os.path.abspath(path)

    def get_last_digest(self):
        try:
            return self.events.all()[-1].hash
        except IndexError:
            return None

#todo gross
class Metadatum(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40))
    key = db.Column(db.String(40))
    value = db.Column(db.String(40))

    event_uuid = db.Column(db.Integer, db.ForeignKey('event.uuid'))
    event = db.relationship('Event', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, event_uuid, category, key, value):
        self.event = event_uuid
        self.category = category
        self.key = key
        self.value = str(value)

class Event(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    cmd = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime)
    user = db.Column(db.String(40))

    event_group_id = db.Column(db.Integer, db.ForeignKey('event_group.id'))
    event_group = db.relationship('EventGroup', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, cmd_str, event_uuid, group_id):
        self.cmd = cmd_str
        self.user = getpass.getuser()
        self.timestamp = datetime.datetime.now()
        self.group = group_id

        if not event_uuid:
            event_uuid = str(uuid.uuid4())
        self.uuid = event_uuid


class ItemEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    item = db.relationship('Item', backref=db.backref('events', lazy='dynamic'))

    event_id = db.Column(db.Integer, db.ForeignKey('event.uuid'))
    event = db.relationship('Event', backref=db.backref('items', lazy='dynamic'))

    hash = db.Column(db.String(64))
    result_type = db.Column(db.String(1))

    def __init__(self, item, event, result_type):
        self.item = item
        self.event = event
        self.result_type = result_type

        abspath = item.path
        if os.path.isfile(abspath):
            h = util.hashfile(abspath)
        elif os.path.isdir(abspath):
            h = util.hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])
        else:
            #???
            h = 0
        self.hash = h

db.create_all()

