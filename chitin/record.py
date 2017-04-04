import getpass
import datetime
import os
import uuid

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

import conf
import util

app = Flask(__name__, template_folder='web/templates')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + conf.DATABASE_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

#class Labbook(db.Model):
#    uuid = db.Column(db.String(40), primary_key=True)
#
#    def __init__(self, path):
#        self.uuid = str(uuid.uuid4())

def add_and_commit(thing):
    db.session.add(thing)
    db.session.commit()

class Project(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(64)) # TODO Force unique names

    last_exp_ts = db.Column(db.DateTime)

    def __init__(self, name):
        self.uuid = str(uuid.uuid4())
        self.name = name
        self.last_exp_ts = datetime.datetime.now()

    def get_experiments(self):
        for exp in self.experiments:
            path = exp.get_path()
            #TODO Not very efficient and a bit gross
            if not exp.shell and not os.path.exists(path):
                exp.active = False
                db.session.commit() #TODO Is this needed?
        return self.experiments.order_by(Experiment.timestamp.desc())


#TODO Replace experiment
class Experiment(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(64))
    base_path = db.Column(db.String(512))

    project_uuid = db.Column(db.Integer, db.ForeignKey('project.uuid'))
    project = db.relationship('Project', backref=db.backref('experiments', lazy='dynamic'))

    timestamp = db.Column(db.DateTime)
    active = db.Column(db.Boolean)
    shell = db.Column(db.Boolean)

    def __init__(self, path, project, name=None, shell=False):
        self.uuid = str(uuid.uuid4())
        self.base_path = os.path.abspath(path)
        self.project = project
        self.timestamp = datetime.datetime.now()
        self.project.last_exp_ts = self.timestamp
        self.active = True
        self.shell = shell

        if name:
            self.name = name
        else:
            self.name = self.uuid

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

    #TODO Grim
    @property
    def return_code(self):
        for b in self.blocks:
            for c in b.commands:
                if c.return_code == -1:
                    return -1
                elif c.return_code != 0:
                    return c.return_code
        return 0

    def get_path(self):
        return os.path.join(self.exp.get_path(), self.uuid)

    def get_params(self):
        return [p for p in self.job_params.all() if p.value != p.exp_param.default_value]

    def get_command_count(self):
        count = 0
        for g in self.blocks:
            count += g.commands.count()
        return count

class Node(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(64))
    url = db.Column(db.String(64))
    description = db.Column(db.String(64))

    def __init__(self, name, url, desc):
        self.uuid = str(uuid.uuid4())
        self.name = name
        self.url = url
        self.description = desc


class CommandQueue(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(64)) # TODO Force unique names by node

    node_uuid = db.Column(db.Integer, db.ForeignKey('node.uuid'))
    node = db.relationship('Node', backref=db.backref('queues', lazy='dynamic'))

    def __init__(self, name, node):
        self.uuid = str(uuid.uuid4())
        self.name = name
        self.node = node

class CommandBlock(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)

    job_uuid = db.Column(db.Integer, db.ForeignKey('job.uuid'))
    job = db.relationship('Job', backref=db.backref('blocks', lazy='dynamic'))

    def __init__(self, job_uuid=None):
        self.uuid = str(uuid.uuid4())
        if job_uuid is not None:
            self.job = job_uuid

class ExperimentParameter(db.Model):
    #TODO Future: Type, description?
    #TODO Could have a ponteitla Resource pointer here...
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

    ghost = db.Column(db.Boolean)

    current_node_uuid = db.Column(db.Integer, db.ForeignKey('node.uuid'))
    current_node = db.relationship('Node', backref=db.backref('resources', lazy='dynamic'))

    def __init__(self, node, path, rhash):
        self.uuid = str(uuid.uuid4())
        self.current_node = node
        self.current_path = path
        self.current_hash = rhash
        self.ghost = False

    @property
    def hash_friends(self):
        return Resource.query.filter(Resource.current_hash == self.current_hash, Resource.uuid != self.uuid, Resource.ghost == False)

    @property
    def full_path(self):
        return self.current_node.name + ":" + self.current_path

    @property
    def last_command(self):
        try:
            return self.commands.filter(ResourceCommand.status != 'U')[-1]
        except:
            return None

class CommandMeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40))
    key = db.Column(db.String(40))
    value = db.Column(db.String(40))

    command_uuid = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    command = db.relationship('Command', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, command, category, key, value):
        self.command = command
        self.category = category
        self.key = key
        self.value = str(value)

class ResourceCommandMeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(40))
    key = db.Column(db.String(40))
    value = db.Column(db.String(40))

    resource_command_uuid = db.Column(db.Integer, db.ForeignKey('resource_command.uuid'))
    resource_command = db.relationship('ResourceCommand', backref=db.backref('meta', lazy='dynamic'))

    def __init__(self, resource_command, category, key, value):
        self.resource_command = resource_command
        self.category = category
        self.key = key
        self.value = str(value)

class Command(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)
    cmd = db.Column(db.String(512))
    cmd_uuid_str = db.Column(db.String(512))
    timestamp = db.Column(db.DateTime)
    user = db.Column(db.String(40))

    block_id = db.Column(db.Integer, db.ForeignKey('command_block.uuid'))
    block = db.relationship('CommandBlock', backref=db.backref('commands', lazy='dynamic'))

    blocked_by_uuid = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    blocked_by = db.relationship('Command', backref=db.backref('blocking', lazy='dynamic'), remote_side="Command.uuid")

    return_code = db.Column(db.Integer)

    #TODO FUTURE
    # Some of this can live in a middle meta class, but for ease it goes here
    queue_uuid = db.Column(db.Integer, db.ForeignKey('command_queue.uuid'))
    queue = db.relationship('CommandQueue', backref=db.backref('commands', lazy='dynamic'))
    position = db.Column(db.Integer)
    active = db.Column(db.Boolean)
    claimed = db.Column(db.Boolean)
    client = db.Column(db.String(40))

    def __init__(self, cmd_str, cmd_block, return_code=-1, blocked_by=None):
        self.uuid = str(uuid.uuid4())
        self.cmd = cmd_str
        self.user = getpass.getuser()
        self.timestamp = datetime.datetime.now()
        self.block = cmd_block
        self.return_code = return_code

        if blocked_by:
            self.blocked_by=blocked_by

        self.active = True
        self.claimed = False
        self.position = 0

class ResourceCommand(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)

    resource_id = db.Column(db.Integer, db.ForeignKey('resource.uuid'))
    resource = db.relationship('Resource', backref=db.backref('commands', lazy='dynamic'))

    command_id = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    command = db.relationship('Command', backref=db.backref('resources', lazy='dynamic'))

    hash = db.Column(db.String(64))

    status = db.Column(db.String(1))

    def __init__(self, resource, cmd, status, h=None, new_path=None):
        self.uuid = str(uuid.uuid4())
        self.resource = resource
        self.command = cmd
        self.status = status

        self.hash = h
        if status == "V" and new_path:
            self.resource.current_path = new_path
            self.hash = self.resource.current_hash
        if status == "D" and not h:
            self.resource.ghost = True
        else:
            # Don't update the current_hash for ghosts, this means users
            # can find copies of the deleted file through its hash_friends
            self.resource.current_hash = self.hash

    def check_hash(self):
        return self.resource.current_hash == self.hash

class CommandText(db.Model):
    uuid = db.Column(db.String(40), primary_key=True)

    name = db.Column(db.String(40))
    num_lines = db.Column(db.Integer)

    command_uuid = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    command = db.relationship('Command', backref=db.backref('texts', lazy='dynamic'))

    text = db.Column(db.Text())

    def __init__(self, cmd, name, text):
        self.uuid = str(uuid.uuid4())
        self.command = cmd
        self.name = name
        self.text = text
        self.num_lines = text.count("\n")

db.create_all()
