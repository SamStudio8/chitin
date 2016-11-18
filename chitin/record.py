import getpass
import datetime
import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import util

app = Flask(__name__)
home = os.path.expanduser('~')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + home + '/.chitin.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

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

    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
    event = db.relationship('Event', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, event_id, category, key, value):
        self.event = event_id
        self.category = category
        self.key = key
        self.value = str(value)

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cmd = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime)
    user = db.Column(db.String(40))

    #TODO INDEX
    uuid = db.Column(db.String(36))

    def __init__(self, cmd_str, uuid):
        self.cmd = cmd_str
        self.user = getpass.getuser()
        self.timestamp = datetime.datetime.now()
        self.uuid = uuid


class ItemEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    item = db.relationship('Item', backref=db.backref('events', lazy='dynamic'))

    event_id = db.Column(db.Integer, db.ForeignKey('event.id'))
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

