import uuid

from chitin.core.database import db

class Node(db.Model):
    """Any device or computer capable of storing a Resource, or executing a Command.

    Attributes
    ----------

    uuid : uuid.uuid4
        The unique identifier of the Node.

    name : str
        The human understandable nickname of the Node.
    """

    uuid = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(64))

    def __init__(self, name):
        self.uuid = str(uuid.uuid4())
        self.name = name

class Resource(db.Model):
    """A Resource effectively binds a unique ID to some file system entity.

    Attributes
    ----------

    uuid : uuid.uuid4
        The unique identifier for the Resource.

    current_path : str
        The last known file path for the Resource.

    current_hash : str
        The last observed file hash for the Resource.

    current_node: db.relationship
        Pointer to the current Node on which the Resource (and current_path) reside.

    ghost: bool
        Whether or not the file has been removed from the file system.
    """

    uuid = db.Column(db.String(40), primary_key=True)
    ghost = db.Column(db.Boolean)

    # Last known hash, node and location (avoids some lookups)
    current_path = db.Column(db.String(512))
    current_hash = db.Column(db.String(64))
    current_node_uuid = db.Column(db.Integer, db.ForeignKey('node.uuid'))
    current_node = db.relationship('Node', backref=db.backref('resources', lazy='dynamic'))

    def __init__(self, curr_path, curr_hash, curr_node_obj, res_uuid=None):
        if not res_uuid:
            res_uuid = str(uuid.uuid4())
        self.uuid = res_uuid
        self.current_node = curr_node_obj
        self.current_path = curr_path
        self.current_hash = curr_hash
        self.ghost = False

    @property
    def hash_friends(self): 
        """Return other Resources who share the current_hash, that are not the current Resource, or ghosted."""
        return Resource.query.filter(Resource.current_hash == self.current_hash, Resource.uuid != self.uuid, Resource.ghost == False)

    @property
    def full_path(self):
        return self.current_node.name + ':' + self.current_path

    @property
    def last_command_effect(self):
        """Return the last CommandOnResource that had an effect on this Resource."""
        try:
            return self.command_effects[-1]
        except:
            return None

    @property
    def ghosts(self):
        return Resource.query.filter(Resource.current_path==self.current_path, Resource.ghost==True, Resource.uuid!=self.uuid)

class CommandGroup(db.Model):
    """A group of executed commands, such as a script, or terminal session.
    A group of commands may have been executed under test with some parameterisation.

    Attributes
    ----------

    uuid : uuid.uuid4
        The unique identifier for the CommandGroup.
    """

    uuid = db.Column(db.String(40), primary_key=True)

    def __init__(self, group_uuid=None):
        if group_uuid is None:
            self.uuid = str(uuid.uuid4())
        else:
            self.uuid = group_uuid

    #@property
    #def created_at(self):
    #    return self.commands.order_by("-queued_at")[0]

class Command(db.Model):
    """An executed command.

    Attributes
    ----------

    uuid : uuid.uuid4
        The unique identifier for the Command.

    cmd : str
        The command as submitted by the user.

    return_code : int
        The exit status of the command.

    queued_at : datetime
        Timestamp when the Command was added to a queue.

    started_at : datetime
        Timestamp when the Command began execution.

    finished_at : datetime
        Timestamp when the Command stopped being executed.

    group : CommandGroup
        The group in which this Command belongs.
    """

    uuid = db.Column(db.String(40), primary_key=True)
    cmd_str = db.Column(db.String(512))
    return_code = db.Column(db.Integer)

    queued_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)

    order = db.Column(db.Integer)

    group_uuid = db.Column(db.Integer, db.ForeignKey('command_group.uuid'))
    group = db.relationship('CommandGroup', backref=db.backref('commands', lazy='dynamic'))

    def __init__(self, cmd_str, queued_at, group_obj, order, cmd_uuid=None):
        if cmd_uuid is None:
            self.uuid = str(uuid.uuid4())
        else:
            self.uuid = cmd_uuid
        self.cmd_str = cmd_str
        self.return_code = -1

        self.queued_at = queued_at
        self.started_at = None
        self.finished_at = None

        self.order = order
        self.group = group_obj

    @property
    def prev(self):
        return self.group.commands.filter(Command.order == self.order-1).first()

    @property
    def next(self):
        return self.group.commands.filter(Command.order == self.order+1).first()


class CommandOnResource(db.Model):
    """A Resource, affected by a Command

    Attributes
    ----------

    uuid : uuid.uuid4
        The unique identifier for this Resource-Command interaction.

    resource : Resource
        The Resource acted upon by a Command

    command : Command
        The Command executed that had an effect or usage of the Resource

    resource_hash : str
        The hash of the file following the end of Command

    effect_status : str(1)
        A short code form describing the change:
            * (C)reated
            * (M)odified
            * (D)eleted
            * Mo(V)ed
    """

    uuid = db.Column(db.String(40), primary_key=True)

    resource_id = db.Column(db.Integer, db.ForeignKey('resource.uuid'))
    resource = db.relationship('Resource', backref=db.backref('command_effects', lazy='dynamic'))

    command_id = db.Column(db.Integer, db.ForeignKey('command.uuid'))
    command = db.relationship('Command', backref=db.backref('resource_effects', lazy='dynamic'))

    resource_hash = db.Column(db.String(64))

    effect_status = db.Column(db.String(1))

    def __init__(self, cmd_obj, res_obj, resource_hash, effect_status, new_path=None):
        self.uuid = str(uuid.uuid4())
        self.command = cmd_obj
        self.resource = res_obj
        self.resource_hash = resource_hash
        self.effect_status = effect_status

        if new_path:
            self.resource.current_path = new_path
            self.hash = self.resource.current_hash
        elif effect_status == "D":
            self.resource.ghost = True
        else:
            self.resource.current_hash = self.resource_hash

