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

def manage_file_integrity(fields, cmd_str=None):
    messages = []
    records = get_records()
    for field in fields:
        # Skip non-file looking things...
        if field[0] == "-":
            continue

        abspath = os.path.abspath(field)
        if os.path.exists(abspath):
            #TODO Check dirs and contents too...
            if os.path.isfile(abspath):
                h = hashfile(abspath)
                frec = records.get(abspath, None)
                if frec:
                    if frec["digest"] != h:
                        if not cmd_str:
                            warnings.warn("\nFile '%s' MODIFIED outside of lab book..." % abspath)
                            add_file_record(abspath, h, "MODIFIED")
                        else:
                            add_file_record(abspath, h, cmd_str)
                            messages.append("MODIFIED %s\n" % abspath)
                    elif cmd_str:
                        # No change, at start of program
                        add_file_record(abspath, h, cmd_str, usage=True)
                else:
                    if not cmd_str:
                        warnings.warn("\nFile '%s' CREATED outside of lab book..." % abspath)
                        add_file_record(abspath, h, "CREATED")
                    else:
                        add_file_record(abspath, h, "CREATED by %s" % cmd_str)
                        messages.append("CREATED %s\n" % abspath)
        elif abspath in records:
            if not cmd_str:
                warnings.warn("\nFile '%s' DELETED outside of lab book..." % abspath)
                add_file_record(abspath, 0, "DELETED")
            else:
                add_file_record(abspath, 0, "DELETED by %s" % cmd_str)
                messages.append("DELETED %s\n" % abspath)
    return messages

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

