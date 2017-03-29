import getpass
import hashlib
import json
import os
import sys
import time
import warnings

from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

import record
from cmd import attempt_parse_type, attempt_integrity_type

def get_file_record(path):
    path = os.path.abspath(path)
    try:
        item = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==False)[0]
    except IndexError:
        return None
    return item

def get_resource_by_path(path):
    path = os.path.abspath(path)
    try:
        resource = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==False)[0]
    except IndexError:
        return None
    return resource

def get_ghosts_by_path(path, uuid=None):
    path = os.path.abspath(path)
    try:
        if uuid:
            resources = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==True, record.Resource.uuid!=uuid)
        else:
            resources = record.Resource.query.filter(record.Resource.current_path==path, record.Resource.ghost==True)
    except IndexError:
        return None
    return resources

def get_resource_by_uuid(uuid):
    try:
        resource = record.Resource.query.filter(record.Resource.uuid==uuid)[0]
    except IndexError:
        return None
    return resource

def add_file_record2(path, cmd_str, status, cmd_uuid=None, new_path=None):
    resource = get_resource_by_path(path)
    if not resource:
        new_hash = hashfile(path)
        resource = record.Resource(path, new_hash)
        record.db.session.add(resource)
        record.db.session.commit()
    else:
        try:
            new_hash = hashfile(path)
        except:
            new_hash = None

    if cmd_uuid:
        # There is always one, except for (?)
        cmd = get_command_by_uuid(cmd_uuid)
    else:
        block = add_command_block(0)
        record.db.session.add(block)
        record.db.session.commit()
        cmd = add_command(cmd_str, block)
        record.db.session.add(cmd)
        record.db.session.commit()

    if cmd:
        resource_command = record.ResourceCommand(resource, cmd, status, h=new_hash, new_path=new_path)
        record.db.session.add(resource_command)

        meta = attempt_parse_type(path)
        if meta:
            for key, value in meta.items():
                record.db.session.add(record.ResourceCommandMeta(resource_command, "handler", key, value))

    record.db.session.commit()


def add_command_block(run_uuid, job=None):
    run = None
    try:
        run = record.Job.query.filter(record.Job.uuid==str(run_uuid))[0]
    except IndexError as e:
        pass
    command_block = record.CommandBlock(job_uuid=run)
    record.db.session.add(command_block)
    record.db.session.commit()
    return command_block

def add_command(cmd_str, cmd_block):
    cmd = record.Command(cmd_str, cmd_block)
    record.db.session.add(cmd)
    record.db.session.commit()
    return cmd

def get_command_by_uuid(uuid):
    cmd = None
    try:
        cmd = record.Command.query.filter(record.Command.uuid==str(uuid))[0]
    except IndexError as e:
        pass
    return cmd

def add_uuid_cmd_str(cmd_uuid, uuid_cmd_str):
    cmd = get_command_by_uuid(cmd_uuid)
    cmd.cmd_uuid_str = uuid_cmd_str
    record.db.session.commit()

def add_command_text(cmd_uuid, key, text):
    if len(text) == 0:
        return
    cmd = get_command_by_uuid(cmd_uuid)
    ctxt = record.CommandText(cmd, key, text)
    record.db.session.add(ctxt)
    record.db.session.commit()

def add_command_meta(cmd_uuid, meta_d):
    cmd = get_command_by_uuid(cmd_uuid)
    for meta_cat in meta_d:
        for key, value in meta_d[meta_cat].items():
            record.db.session.add(record.CommandMeta(cmd, meta_cat, key, value))
    record.db.session.commit()

def set_command_return_code(cmd_uuid, return_code):
    cmd = get_command_by_uuid(cmd_uuid)
    cmd.return_code = return_code
    record.db.session.commit()

################################################################################
def check_integrity_set2(path_set, skip_check=False):
    """Check the hash integrity of a set of filesystem paths"""
    failed = []

    for resource_path in path_set:
        resource_path = os.path.abspath(resource_path)

        if os.path.isfile(resource_path):
            if check_integrity2(resource_path, skip_hash=skip_check):
                failed.append(resource_path)
            if skip_check:
                continue

        elif os.path.isdir(resource_path):
            for subitem in os.listdir(resource_path):
                i_abspath = os.path.join(resource_path, subitem)
                if os.path.isdir(i_abspath):
                    for subsubitem in os.listdir(i_abspath):
                        j_abspath = os.path.join(i_abspath, subsubitem)
                        if j_abspath in path_set:
                            continue
                        if os.path.isfile(j_abspath):
                            if check_integrity2(j_abspath):
                                failed.append(j_abspath)
                elif os.path.isfile(i_abspath):
                    #TODO Do we want to keep a record of the files of subfolders?
                    if i_abspath in path_set:
                        continue
                    if check_integrity2(i_abspath):
                        failed.append(i_abspath)

    return sorted(failed)


def check_integrity2(path, skip_hash=False):
    abspath = os.path.abspath(path)
    broken_integrity = False

    if skip_hash:
        if os.path.exists(abspath):
            if os.path.isfile(abspath):
                check_rules_integrity(path)
    else:
        resource = get_resource_by_path(abspath)
        if os.path.exists(abspath):
            if os.path.isfile(abspath):
                check_rules_integrity(path)

            if resource:
                # Path exists and we knew about it
                if not check_hash_integrity(abspath):
                    add_file_record2(abspath, "MODIFIED by (?)", 'M')
                    broken_integrity = True
            else:
                # Path exists but it is a surprise
                add_file_record2(abspath, "CREATED by (?)", 'C')
                broken_integrity = True
        elif path_record:
            add_file_record2(abspath, "DELETED by (?)", 'D')
            broken_integrity = True
    return broken_integrity


def check_hash_integrity(path):
    """Check whether the given path has a different hash from the one currently
    stored in the database. Returns False if the file's integrity is broken."""
    abspath = os.path.abspath(path)
    now_hash = hashfile(abspath)
    resource = get_resource_by_path(abspath)
    return now_hash == resource.current_hash

def check_rules_integrity(path):
    """Check whether the given path violates any rules associated with its type.
    Returns False if the file has broken at least one rule."""
    abspath = os.path.abspath(path)
    broken_rules = {}

    broken_rules = attempt_integrity_type(abspath)
    for rule, result in broken_rules.items():
        if not result and result is not None:
            print "[WARN] %s %s" % (path, rule[1])
    return len(broken_rules) == 0

def check_status_set2(path_set):
    file_statii = {}
    codes = {"C": 0, "M": 0, "D": 0, "U": 0, "V": 0}
    hashes = {}
    moves = {}

    for item in path_set:
        item = os.path.abspath(item)
        if not os.path.exists(item):
            stat = get_status(item)
            file_statii[item] = stat[0]
            hashes[item] = (stat[1], stat[2])

        if os.path.isdir(item):
            stat = get_status(item)
            hashes[item] = (stat[1], stat[2])

            for subitem in os.listdir(item):
                i_abspath = os.path.join(item, subitem)
                if os.path.isdir(i_abspath):
                    pass
                else:
                    #TODO Do we want to keep a record of the files of untargeted subfolders?
                    stat = get_status(i_abspath)
                    file_statii[i_abspath] = stat[0]
                    hashes[i_abspath] = (stat[1], stat[2])
        elif os.path.isfile(item):
            stat = get_status(item)
            file_statii[item] = stat[0]
            hashes[item] = (stat[1], stat[2])

    #TODO Naive move checking
    for deleted_f in [f for f in file_statii if file_statii[f] == "D"]:
        for created_f in [f for f in file_statii if file_statii[f] == "C"]:
            if hashes[deleted_f][1] == hashes[created_f][0]:
                # Deleted file was moved (probably)!
                moves[deleted_f] = created_f
                codes["V"] += 1
                del file_statii[deleted_f]
                del file_statii[created_f]
                break

    for s in file_statii.values():
        codes[s] += 1

    return {
        "files": file_statii,
        "codes": codes,
        "hashes": hashes,
        "moves": moves,
    }

################################################################################


def get_status(path, cmd_str=""):
    abspath = os.path.abspath(path)

    h = 0
    status = '?'
    last_h = 0
    path_record = get_file_record(abspath)
    if os.path.exists(abspath):
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = None

        if path_record:
            try:
                last_h = path_record.current_hash
            except IndexError:
                pass

            # Path exists and we knew about it
            if path_record.current_hash != h:
                status = "M"
            else:
                status = "U"
        else:
            # Path exists but it is a surprise
            status = "C"
    elif path_record:
        last_h = path_record.current_hash
        status = "D"

    return (status, h, last_h)

###############################################################################
def parse_tokens(fields, env_vars, insert_uuids=False):
    dirs_l = []
    file_l = []
    for field_i, field in enumerate(fields):
        for env_k in env_vars:
            if '$' + env_k in field:
                field = field.replace('$' + env_k, str(env_vars[env_k]))
                fields[field_i] = field

        had_semicolon = False
        if field[-1] == ";":
            had_semicolon = True
            field = field.replace(";", "")

        if field.startswith("chitin://"):
            resource = get_resource_by_uuid(field.split("chitin://")[1])
            if resource:
                field = resource.current_path
        abspath = os.path.abspath(field)

        # Does the path exist? We might want to add its parent directory
        if os.path.exists(abspath):
            field_ = abspath
            if insert_uuids:
                resource = get_resource_by_path(field_)
                if resource:
                    field_ = "chitin://" + str(resource.uuid)

            if had_semicolon:
                fields[field_i] = field_ + ';' # Update the command to use the full abspath
            else:
                fields[field_i] = field_ # Update the command to use the full abspath
        else:
            continue

        ### Files
        if os.path.isfile(abspath):
            file_l.append(abspath)

        ### Dirs
        elif os.path.isdir(abspath):
            dirs_l.append(abspath)

            for item in os.listdir(abspath):
                i_abspath = os.path.join(abspath, item)
                if os.path.isdir(i_abspath):
                    dirs_l.append(i_abspath)
                else:
                    #TODO Do we want to keep a record of the files of subfolders?
                    pass
    return {
        "fields": fields,
        "files": set(file_l),
        "dirs": set(dirs_l),
    }


def hashfile(path, halg=hashlib.md5, bs=65536):
    f = open(path, 'rb')
    buff = f.read(bs)
    halg = halg()
    halg.update(buff)
    while len(buff) > 0:
        buff = f.read(bs)
        halg.update(buff)
    f.close()
    return halg.hexdigest()

################################################################################
def register_or_fetch_project(name):
    try:
        project = record.Project.query.filter(record.Project.name == name)[0]
    except IndexError:
        project = record.Project(name)
        record.db.session.add(project)
        record.db.session.commit()
    return project

def register_experiment(path, project, create_dir=False, params=None, name=None):
    exp = record.Experiment(path, project, name=name)
    record.db.session.add(exp)
    record.db.session.commit()

    #TODO Would be nice to check whether params[p] is a Resource?
    if params:
        for i, p in enumerate(params):
            #p = record.ExperimentParameter(self, p, params[p], i)
            p = record.ExperimentParameter(exp, p, params[p])
            record.db.session.add(p)
        record.db.session.commit()

    if create_dir:
        try:
            os.mkdir(exp.get_path())
        except:
            #TODO would be nice if we could distinguish between OSError 13 (permission) etc.
            print("[WARN] Encountered trouble creating %s" % exp.get_path())
    return exp

def register_job(exp_uuid, create_dir=False):
    exp = None
    try:
        exp = record.Experiment.query.filter(record.Experiment.uuid==str(exp_uuid))[0]
    except IndexError as e:
        pass

    job_params = exp.make_params()

    job = record.Job(exp)
    record.db.session.add(job)

    job_path = "" # euch, this is going to cause trouble
    if create_dir:
        try:
            os.mkdir(job.get_path())
            job_path = job.get_path()
        except:
            #TODO would be nice if we could distinguish between OSError 13 (permission) etc.
            print("[WARN] Encountered trouble creating %s" % job.get_path())

    job_params["exp_uuid"] = exp.uuid
    job_params["job_uuid"] = job.uuid
    job_params["job_dir"] = job_path
    return job, job_params

def register_run(exp_uuid, create_dir=False, meta=None):
    print("[WARN] register_run is deprecated, use register_job instead")
    print("       Note that you no longer pass parameters to register_job,")
    print("       register_run now returns a dict for you to fill in")
    return register_job(exp_uuid, create_dir=create_dir)

def archive_experiment(exp_uuid, tar_path=None, manifest=True, new_root=None):
    import tarfile
    exp = record.Experiment.query.get(exp_uuid)
    if not exp:
        return None

    def translate_tarinfo(info):
        info.name = os.path.join(exp.uuid, "".join(info.name.split(exp.uuid)[1:])[1:])
        if new_root:
            info.name = os.path.join(new_root, info.name)
        return info

    if tar_path is None:
        tar_path = os.path.join(exp.get_path(), exp.uuid + ".tar.gz")

    tar = tarfile.open(tar_path, "w|gz")
    tar.add(exp.get_path(), filter=translate_tarinfo)

    tar.close()

    return tar_path

def generate_experiment_manifest(exp_uuid, dest=None):
    exp = record.Experiment.query.get(exp_uuid)
    if not exp:
        return None

    if not dest:
        dest = os.path.join(exp.get_path(), exp.uuid + ".manifest")
    dest_fh = open(dest, "w")

    for r in exp.runs:
        dest_fh.write(
            ("%s\t" % r.uuid) + "\t".join([m.value for m in r.rmeta]) + "\n"
        )
    dest_fh.close()


def copy_experiment_archive(exp_uuid, hostname, ssh_config_path=None, dest=None, new_root=None, manifest=False):
    import paramiko

    tar_path = archive_experiment(exp_uuid, new_root=new_root, manifest=manifest)

    pw = getpass.getpass()

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    config = paramiko.SSHConfig()
    if not ssh_config_path:
        ssh_config_path = os.path.expanduser("~/.ssh/config")

    config.parse(open(ssh_config_path))

    connect_config = dict(config.lookup(hostname))
    if 'user' in connect_config:
        connect_config['username'] = connect_config['user']
        del connect_config['user']
    if 'proxycommand' in connect_config:
        connect_config['sock'] = paramiko.ProxyCommand(connect_config['proxycommand'])
        del connect_config['proxycommand']

    connect_config["look_for_keys"] = False
    connect_config["allow_agent"] = False
    connect_config["password"] = pw
    ssh.connect(**connect_config)

    sftp = ssh.open_sftp()
    if dest is not None:
        sftp.chdir(dest)
    print(sftp.put(tar_path, os.path.basename(tar_path), confirm=True))

    if dest is None:
        dest = "~"
    stdin, stdout, stderr = ssh.exec_command('tar -xvPf ' + os.path.join(dest, os.path.basename(tar_path)))
    print("".join(stdout.readlines()))
    ssh.close()


#TODO(samstudio8) Find a non-garbage way of finding a nice default truetype font
def watermark_experiment_image(exp_uuid, image_path, font_path="/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf", name=None):
    exp = record.Experiment.query.get(exp_uuid)
    if not exp or not os.path.exists(exp.get_path()):
        print("[WARN] Could not create watermarked experiment image.")
        return

    font = ImageFont.truetype(font_path, 36)
    img = Image.open(image_path)
    width, height = img.size

    # Create a new image with some space at the bottom for metadata
    # color=(0,0,0) somewhat assumes RGB so might implode
    new_img = Image.new(img.mode, (width, height+48), color=(0,0,0))
    new_img.paste(img, (0,0))

    # Draw the UUID onto the image
    draw = ImageDraw.Draw(new_img)
    t_msg = exp_uuid
    msg_w, msg_h = draw.textsize(t_msg, font=font)
    draw.text(((width-msg_w)/2, height), t_msg, font=font)

    # Save the image
    if not name:
        name = datetime.now().strftime("%Y-%m-%d_%H:%M:%S") + ".png"
    new_img.save(os.path.join(exp.get_path(), name))
