import os

import record

def get_ghosts_by_path(path, uuid=None):
    if uuid:
        resources = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==True, record.Resource.uuid!=uuid)
    else:
        resources = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==True)
    return resources

def get_resource_by_path(path):
    return record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==False).first()

def get_resource_by_uuid(uuid):
    return record.Resource.query.filter(record.Resource.uuid==uuid).first()

def get_node_queue_by_name(node, queue):
    #TODO FUTURE Check permissions to submit to Q etc. ?
    return record.CommandQueue.query.join(record.Node).filter(record.Node.name == node, record.CommandQueue.name == queue).first()

def get_command_by_uuid(uuid):
    return record.Command.query.filter(record.Command.uuid==str(uuid)).first()

def get_experiment_by_uuid(uuid):
    return record.Experiment.query.filter(record.Experiment.uuid==str(uuid)).first()

def get_project_by_uuid(uuid):
    return record.Project.query.filter(record.Project.uuid==str(uuid)).first()

def get_node_by_uuid(uuid):
    return record.Node.query.filter(record.Node.uuid==str(uuid)).first()

def get_job_by_uuid(uuid):
    return record.Job.query.filter(record.Job.uuid==str(uuid)).first()

def get_block_by_uuid(uuid):
    return record.CommandBlock.query.filter(record.CommandBlock.uuid==str(uuid)).first()


def add_user(username, password):
    user = record.User(username, password)
    record.add_and_commit(user)
    return user.uuid, user.username

def register_or_fetch_nodeq(name, url, desc, qname):
    node = record.Node.query.filter(record.Node.name == name).first()
    if not node:
        node = record.Node(name, url, desc)
        record.add_and_commit(node)

    q = record.CommandQueue.query.join(record.Node).filter(record.CommandQueue.name == qname, record.Node.uuid == node.uuid).first()
    if not q:
        q = record.CommandQueue(qname, node)
        record.add_and_commit(q)

    print("NODE_NAME='%s'" % node.name)
    print("NODE_UUID='%s'" % node.uuid)
    print("QUEUE_UUID='%s'" % q.uuid)

