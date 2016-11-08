import hashlib
import json
import os
import sys
import warnings

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

def add_file_record(path, digest, cmd_str):
    records = get_records()
    fn = os.path.expanduser('~') + '/.lab.json'
    fh = open(fn, "w+")
    if path not in records:
        records[path] = {
            "digest": digest,
            "tasks": [cmd_str]
        }
    else:
        records[path]["digest"] = digest
        records[path]["tasks"].append(cmd_str)

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
                h = hashfile(open(abspath, 'rb'), hashlib.md5())
                frec = records.get(abspath, None)
                if frec:
                    if frec["digest"] != h:
                        if not cmd_str:
                            warnings.warn("\nFile '%s' EDITED outside of lab book..." % abspath)
                            add_file_record(abspath, h, "EDITED")
                        else:
                            add_file_record(abspath, h, cmd_str)
                            messages.append("UPDATED %s\n" % abspath)
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

def hashfile(f, halg, bs=65536):
    buff = f.read(bs)
    while len(buff) > 0:
        halg.update(buff)
        buff = f.read(bs)
    return halg.hexdigest()

