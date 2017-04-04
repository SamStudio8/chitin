import os

import record

#def get_file_record(path):
#    try:
#        item = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==False)[0]
#    except IndexError:
#        return None
#    return item

def get_ghosts_by_path(path, uuid=None):
    try:
        if uuid:
            resources = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==True, record.Resource.uuid!=uuid)
        else:
            resources = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==True)
    except IndexError:
        return None
    return resources

def get_resource_by_path(path):
    try:
        resource = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==False)[0]
    except IndexError:
        return None
    return resource

def get_resource_by_uuid(uuid):
    try:
        resource = record.Resource.query.filter(record.Resource.uuid==uuid)[0]
    except IndexError:
        return None
    return resource

def get_node_queue_by_name(node, queue):
    #TODO FUTURE Check permissions to submit to Q etc. ?
    try:
        return record.CommandQueue.query.join(record.Node).filter(record.Node.name == node, record.CommandQueue.name == queue)[0]
    except IndexError:
        return None

def purge_commands_by_client(client_uuid):
    count = 0
    for command in record.Command.query.filter(record.Command.client == client_uuid, record.Command.claimed == False, record.Command.return_code == -1):
        command.return_code = 128
        command.active = False
        record.db.session.commit()
        count += 1
    return count

def get_command_by_uuid(uuid):
    cmd = None
    try:
        cmd = record.Command.query.filter(record.Command.uuid==str(uuid))[0]
    except IndexError:
        pass
    return cmd

def get_experiment_by_uuid(uuid):
    exp = None
    try:
        exp = record.Experiment.query.filter(record.Experiment.uuid==str(uuid))[0]
    except IndexError:
        pass
    return exp

def get_project_by_uuid(uuid):
    project = None
    try:
        project = record.Project.query.filter(record.Project.uuid==str(uuid))[0]
    except IndexError:
        pass
    return project

def get_node_by_uuid(uuid):
    node = None
    try:
        node = record.Node.query.filter(record.Node.uuid==str(uuid))[0]
    except IndexError as e:
        pass
    return node

def get_job_by_uuid(uuid):
    job = None
    try:
        job = record.Job.query.filter(record.Job.uuid==str(uuid))[0]
    except IndexError as e:
        pass
    return job

def get_block_by_uuid(uuid):
    b = None
    try:
        b = record.CommandBlock.query.filter(record.CommandBlock.uuid==str(uuid))[0]
    except IndexError as e:
        pass
    return b

