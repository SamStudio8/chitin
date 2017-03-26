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

#TODO Replace experiment
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

    def get_fixed_params(self):
        return [p for p in self.params.all() if p.default_value != None]

    def get_param_keys(self):
        return [p for p in self.params.all() if p.default_value == None]

    def make_params(self):
        params = {}
        for p in self.params.all():
            params[p.key] = p.default_value
        return params

class Job(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)

    exp_id = db.Column(db.Integer, db.ForeignKey('experiment.uuid'))
    exp = db.relationship('Experiment', backref=db.backref('jobs', lazy='dynamic'))

    def __init__(self, exp):
        self.uuid = str(uuid.uuid4())
        self.exp = exp

    def get_path(self):
        return os.path.join(self.exp.get_path(), self.uuid)

    def get_params(self):
        return [p for p in self.job_params.all() if p.value != p.exp_param.default_value]

    def get_command_count(self):
        count = 0
        for g in self.blocks:
            count += g.commands.count()
        return count

class CommandBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    job_uuid = db.Column(db.Integer, db.ForeignKey('job.uuid'))
    job = db.relationship('Job', backref=db.backref('blocks', lazy='dynamic'))

    def __init__(self, job_uuid=None):
        if job_uuid is not None:
            self.job = job_uuid

class ExperimentParameter(db.Model):
    #TODO Future: Type, description?
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(40))
    default_value = db.Column(db.String(128))
    #order = db.Column(db.Integer)

    exp_uuid = db.Column(db.Integer, db.ForeignKey('experiment.uuid'))
    exp = db.relationship('Experiment', backref=db.backref('params', lazy='dynamic'))

    def __init__(self, exp, key, value):
        self.exp = exp
        self.key = key
        self.default_value = value
        #self.order = order

class JobMeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    exp_param_id = db.Column(db.Integer, db.ForeignKey('experiment_parameter.id'))
    exp_param = db.relationship('ExperimentParameter')

    job_uuid = db.Column(db.Integer, db.ForeignKey('job.uuid'))
    job = db.relationship('Job', backref=db.backref('job_params', lazy='dynamic'))

    value = db.Column(db.String(128))

    def __init__(self, job, exp_param, value):
        self.job = job
        self.exp_param = exp_param
        self.value = str(value)

class Resource(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    current_path = db.Column(db.String(512))
    current_hash = db.Column(db.String(64))

    def __init__(self, path, rhash):
        self.uuid = str(uuid.uuid4())
        self.current_path = path
        self.current_hash = rhash

    @property
    def hash_friends(self):
        return Resource.query.filter(Resource.current_hash == self.current_hash)

    @property
    def last_command(self):
        return self.commands.filter(ResourceCommand.status != 'U')[-1]

class CommandMeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40))
    key = db.Column(db.String(40))
    value = db.Column(db.String(40))

    command_uuid = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    command = db.relationship('Command', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, command_uuid, category, key, value):
        self.command = command_uuid
        self.category = category
        self.key = key
        self.value = str(value)

class Command(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    cmd = db.Column(db.String(512))
    cmd_uuid_str = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime)
    user = db.Column(db.String(40))

    block_id = db.Column(db.Integer, db.ForeignKey('command_block.id'))
    block = db.relationship('CommandBlock', backref=db.backref('commands', lazy='dynamic'))

    def __init__(self, cmd_str, cmd_block):
        self.uuid = str(uuid.uuid4())
        self.cmd = cmd_str
        self.user = getpass.getuser()
        self.timestamp = datetime.datetime.now()
        self.block = cmd_block

class ResourceCommand(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)

    resource_id = db.Column(db.Integer, db.ForeignKey('resource.uuid'))
    resource = db.relationship('Resource', backref=db.backref('commands', lazy='dynamic'))

    command_id = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    command = db.relationship('Command', backref=db.backref('resources', lazy='dynamic'))

    hash = db.Column(db.String(64))

    status = db.Column(db.String(1))

    def __init__(self, resource, cmd, status):
        self.uuid = str(uuid.uuid4())
        self.resource = resource
        self.command = cmd
        self.status = status

        abspath = resource.current_path
        self.hash = util.hashfile(abspath)

db.create_all()

