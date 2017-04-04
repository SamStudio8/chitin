import getpass
import hashlib
import json
import os
import sys
import time
import warnings

import requests

from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

import conf

from cmd import attempt_integrity_type

def emit(endpoint, payload, client_uuid):
    payload['client'] = client_uuid
    r = requests.post(conf.ENDPOINT_BASE + endpoint, json=payload)
    return r.json()

def get_resource_by_path(path):
    path = os.path.abspath(path)
    return emit('resource/get/', {
        "path": path,
    }, None)

def get_resource_by_uuid(uuid):
    return emit('resource/get/', {
        "uuid": uuid,
    }, None)

def get_experiment_by_uuid(uuid):
    return emit('experiment/get/', {
        "uuid": uuid,
    }, None)
    
def register_or_fetch_project(name):
    try:
        return emit('project/add/', {
            "name": name,
        }, None)["uuid"]
    except Exception:
        raise Exception

def register_experiment(path, project_uuid, create_dir=False, params=None, name=None, shell=False):
    exp = None
    try:
        exp = emit('experiment/add/', {
            "path": path,
            "project_uuid": project_uuid,
            "params": params,
            "shell": shell,
            "name": name,
        }, None)
    except Exception as e:
        raise e

    if create_dir:
        try:
            os.mkdir(exp["path"])
        except:
            #TODO would be nice if we could distinguish between OSError 13 (permission) etc.
            print("[WARN] Encountered trouble creating %s" % exp["path"])
            raise Exception
    return exp["uuid"]

def register_job(exp_uuid, create_dir=False):
    job = None
    try:
        job = emit('job/add/', {
            "exp_uuid": exp_uuid,
        }, None)
    except Exception as e:
        raise e

    if create_dir:
        try:
            os.mkdir(job["path"])
        except:
            #TODO would be nice if we could distinguish between OSError 13 (permission) etc.
            print("[WARN] Encountered trouble creating %s" % job["path"])

    return job["uuid"], job["params"]
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
                    #TODO Do we want to keep track of the files of subfolders?
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
                    emit('resource/update/', {
                        "path": abspath,
                        "cmd_str": "MODIFIED by (?)",
                        "status_code": 'M',
                        "path_hash": hashfile(path),
                        "node_uuid": conf.NODE_UUID,
                        "metacommand": True,
                    }, None)
                    broken_integrity = True
            else:
                # Path exists but it is a surprise
                emit('resource/update/', {
                    "path": abspath,
                    "cmd_str": "CREATED by (?)",
                    "status_code": 'C',
                    "path_hash": hashfile(path),
                    "node_uuid": conf.NODE_UUID,
                    "metacommand": True,
                }, None)
                broken_integrity = True
        elif resource:
            emit('resource/update/', {
                "path": abspath,
                "cmd_str": "DELETED by (?)",
                "status_code": 'D',
                "path_hash": None,
                "node_uuid": conf.NODE_UUID,
                "metacommand": True,
            }, None)
            broken_integrity = True
    return broken_integrity


def check_hash_integrity(path):
    """Check whether the given path has a different hash from the one currently
    stored in the database. Returns False if the file's integrity is broken."""
    abspath = os.path.abspath(path)
    now_hash = hashfile(abspath)
    resource = get_resource_by_path(abspath)
    return now_hash == resource["current_hash"]

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
                    #TODO Do we want to keep track of the files of untargeted subfolders?
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
    resource = get_resource_by_path(abspath)
    if os.path.exists(abspath):
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = None

        if resource:
            try:
                last_h = resource["current_hash"]
            except IndexError:
                pass

            # Path exists and we knew about it
            if resource["current_hash"] != h:
                status = "M"
            else:
                status = "U"
        else:
            # Path exists but it is a surprise
            status = "C"
    elif resource:
        last_h = resource["current_hash"]
        status = "D"

    return (status, h, last_h)

###############################################################################
def parse_tokens(fields, insert_uuids=False):
    dirs_l = []
    file_l = []
    for field_i, field in enumerate(fields):
        #for env_k in env_vars:
        #    if '$' + env_k in field:
        #        field = field.replace('$' + env_k, str(env_vars[env_k]))
        #        fields[field_i] = field

        had_semicolon = False
        if field[-1] == ";":
            had_semicolon = True
            field = field.replace(";", "")

        if field.startswith("chitin://"):
            resource = get_resource_by_uuid(field.split("chitin://")[1])
            if resource:
                field = resource["current_path"]
        abspath = os.path.abspath(field)

        # Does the path exist? We might want to add its parent directory
        if os.path.exists(abspath):
            field_ = abspath
            if insert_uuids:
                resource = get_resource_by_path(field_)
                if resource:
                    field_ = "chitin://" + str(resource["uuid"])

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
                    #TODO Do we want to keep track of the files of subfolders?
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


def archive_experiment(exp_uuid, tar_path=None, manifest=True, new_root=None):
    import tarfile
    exp = get_experiment_by_uuid(exp_uuid)
    if not exp:
        return None

    def translate_tarinfo(info):
        info.name = os.path.join(exp["uuid"], "".join(info.name.split(exp["uuid"])[1:])[1:])
        if new_root:
            info.name = os.path.join(new_root, info.name)
        return info

    if tar_path is None:
        tar_path = os.path.join(exp["path"], exp["uuid"] + ".tar.gz")

    tar = tarfile.open(tar_path, "w|gz")
    tar.add(exp["path"], filter=translate_tarinfo)

    tar.close()

    return tar_path

def generate_experiment_manifest(exp_uuid, dest=None):
    exp = get_experiment_by_uuid(exp_uuid)
    if not exp:
        return None

    if not dest:
        dest = os.path.join(exp["path"], exp["uuid"] + ".manifest")
    dest_fh = open(dest, "w")

    #TODO FIX
    #for r in exp["runs"]:
    #    dest_fh.write(
    #        ("%s\t" % r.uuid) + "\t".join([m.value for m in r.rmeta]) + "\n"
    #    )
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
    exp = get_experiment_by_uuid(exp_uuid)
    if not exp:
        return None
    if not exp or not os.path.exists(exp["path"]):
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
    new_img.save(os.path.join(exp["path"], name))

###############################################################################

