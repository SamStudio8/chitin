import getpass
import hashlib
import json
import os
import sys
import time
import warnings

from datetime import datetime

def get_records():
    records = {}
    try:
        fn = os.path.expanduser('~') + '/.lab.json'
        fh = open(fn, "r")
        records = json.loads("\n".join(fh.readlines()))
        fh.close()
    except IOError, ValueError:
        pass
    return records

def get_file_record(path):
    records = get_records()
    path = os.path.abspath(path)
    return records.get(path, None)

def changed_record(path, cmd_str=""):
    records = get_records()
    abspath = os.path.abspath(path)

    if os.path.exists(abspath):
        path_record = records.get(abspath, None)
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])

        if path_record:
            # Path exists and we knew about it
            if path_record["digest"] != h:
                print abspath, path_record["digest"], h
                add_file_record(abspath, h, "MODIFIED by %s" % cmd_str)
            else:
                add_file_record(abspath, h, "%s" % cmd_str, usage=True)
        else:
            # Path exists but it is a surprise
            add_file_record(abspath, h, "CREATED by %s" % cmd_str)
    elif abspath in records:
        add_file_record(abspath, h, "DELETED by %s" % cmd_str)

def add_file_record(path, digest, cmd_str, usage=False):
    records = get_records()
    fn = os.path.expanduser('~') + '/.lab.json'
    fh = open(fn, "w+")
    if path not in records:
        records[path] = {
            "digest": digest,
            "history": [],
            "usage": [],
        }
        records[path]["history"].append({
            "cmd": cmd_str,
            "digest": digest,
            "timestamp": int(time.mktime(datetime.now().timetuple())),
            "user": getpass.getuser(),
        })
    else:
        if usage:
            records[path]["usage"].append({
                "cmd": cmd_str,
                "digest": digest,
                "timestamp": int(time.mktime(datetime.now().timetuple())),
                "user": getpass.getuser(),
            })
        else:
            records[path]["digest"] = digest
            records[path]["history"].append({
                "cmd": cmd_str,
                "digest": digest,
                "timestamp": int(time.mktime(datetime.now().timetuple())),
                "user": getpass.getuser(),
            })

    fh.write(json.dumps(records))
    fh.close()

def check_integrity(path):
    records = get_records()
    abspath = os.path.abspath(path)

    if os.path.exists(abspath):
        path_record = records.get(abspath, None)
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])

        if path_record:
            # Path exists and we knew about it
            if path_record["digest"] != h:
                add_file_record(abspath, h, "MODIFIED by (?)")
                return True
            return False
        else:
            # Path exists but it is a surprise
            add_file_record(abspath, h, "CREATED by (?)")
            return True
    elif abspath in records:
        add_file_record(abspath, h, "DELETED by (?)")
        return True

def parse_tokens(fields):
    dirs_l = []
    file_l = []
    for field_i, field in enumerate(fields):
        abspath = os.path.abspath(field)
        if os.path.exists(abspath):
            fields[field_i] = abspath # Update the command to use the full abspath
        else:
            continue

        if os.path.isfile(abspath):
            file_l.append(abspath)
            dirs_l.append(os.path.dirname(abspath))
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

def hashfiles(paths, halg=hashlib.md5, bs=65536):
    tot_halg = halg()
    for path in sorted(paths):
        tot_halg.update(hashfile(path, halg=halg, bs=bs))
    return tot_halg.hexdigest()
