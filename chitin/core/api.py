from chitin.core.database import db
from chitin.core.models import Node, Resource, Command, CommandOnResource, CommandGroup

def add_node(name):
    node = Node(name)
    db.session.add(node)
    db.session.commit()
    return node

def add_resource(curr_path, curr_hash, curr_node_obj, res_uuid=None):
    res = Resource(curr_path, curr_hash, curr_node_obj, res_uuid)
    db.session.add(res)
    db.session.commit()
    return res

def add_command(cmd_str, queued_at, group_obj, cmd_uuid=None):
    cmd = Command(cmd_str, queued_at, group_obj, cmd_uuid=cmd_uuid)
    db.session.add(cmd)
    db.session.commit()
    return cmd

def add_command_group(group_uuid=None):
    group = CommandGroup(group_uuid=group_uuid)
    db.session.add(group)
    db.session.commit()
    return group

def add_command_on_resource(cmd_obj, res_obj, res_hash, effect_status):
    cor = CommandOnResource(cmd_obj, res_obj, res_hash, effect_status)
    db.session.add(cor)
    db.session.commit()
    return cor

def get_resource_by_path(node_uuid, res_path):
    return Resource.query.filter(
            Node.uuid==node_uuid,                   # on Node
            Resource.current_path==res_path,        # at path
            Resource.ghost==False                   # not deleted
    ).first()

