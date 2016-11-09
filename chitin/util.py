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

def write_status(path, status, cmd_str, meta=None, usage=False):
    records = get_records()
    abspath = os.path.abspath(path)

    if os.path.exists(abspath):
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])
    else:
        h = 0

    add_file_record(abspath, h, "%s %s" % (status, cmd_str), meta=meta, usage=usage)

def get_status(path, cmd_str=""):
    records = get_records()
    abspath = os.path.abspath(path)

    status = None
    last_h = 0
    if os.path.exists(abspath):
        path_record = records.get(abspath, None)
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])

        if path_record:
            try:
                last_h = path_record["history"][-1]["digest"]
            except IndexError:
                pass

            # Path exists and we knew about it
            if path_record["digest"] != h:
                status = "M"
            else:
                status = "U"
        else:
            # Path exists but it is a surprise
            status = "C"
    elif abspath in records:
        h = 0
        path_record = records.get(abspath, None)
        last_h = path_record["history"][-1]["digest"]
        status = "D"

    return (status, h, last_h)

def add_file_record(path, digest, cmd_str, usage=False, parent=None, meta=None):
    records = get_records()
    fn = os.path.expanduser('~') + '/.lab.json'
    fh = open(fn, "w+")
    if path not in records:
        records[path] = {
            "digest": digest,
            "history": [],
            "usage": [],
            "parent": None,
        }
        records[path]["history"].append({
            "cmd": cmd_str,
            "digest": digest,
            "timestamp": int(time.mktime(datetime.now().timetuple())),
            "user": getpass.getuser(),
            "meta": meta
        })
    else:
        if usage:
            records[path]["usage"].append({
                "cmd": cmd_str,
                "digest": digest,
                "timestamp": int(time.mktime(datetime.now().timetuple())),
                "user": getpass.getuser(),
            })
        elif parent:
            records[path]["parent"] = parent
        else:
            records[path]["digest"] = digest
            records[path]["history"].append({
                "cmd": cmd_str,
                "digest": digest,
                "timestamp": int(time.mktime(datetime.now().timetuple())),
                "user": getpass.getuser(),
                "meta": meta
            })

    fh.write(json.dumps(records))
    fh.close()

def check_integrity_set(path_set):
    failed = []
    for item in path_set:
        item = os.path.abspath(item)
        if check_integrity(item):
            failed.append(item)

        if os.path.isdir(item):
            for subitem in os.listdir(item):
                i_abspath = os.path.join(item, subitem)
                if os.path.isdir(i_abspath):
                    if check_integrity(i_abspath):
                        failed.append(i_abspath)

                    for subsubitem in os.listdir(i_abspath):
                        j_abspath = os.path.join(i_abspath, subsubitem)
                        if os.path.isfile(j_abspath):
                            if check_integrity(j_abspath):
                                failed.append(j_abspath)
                else:
                    #TODO Do we want to keep a record of the files of subfolders?
                    if check_integrity(i_abspath):
                        failed.append(i_abspath)
    return sorted(failed)

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
    return False

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

def check_status_path_set(path_set):
    dir_statii = {}
    file_statii = {}
    dir_codes = {"C": 0, "M": 0, "D": 0, "U": 0}
    file_codes = {"C": 0, "M": 0, "D": 0, "U": 0}
    codes = {"C": 0, "M": 0, "D": 0, "U": 0}
    hashes = {}

    for item in path_set:
        item = os.path.abspath(item)
        if not os.path.exists(item):
            stat = get_status(item)
            file_statii[item] = stat[0]
            hashes[item] = (stat[1], stat[2])

        if os.path.isdir(item):
            stat = get_status(item)
            dir_statii[item] = stat[0]
            hashes[item] = (stat[1], stat[2])

            for subitem in os.listdir(item):
                i_abspath = os.path.join(item, subitem)
                if os.path.isdir(i_abspath):
                    stat = get_status(i_abspath)
                    dir_statii[i_abspath] = stat[0]
                    hashes[i_abspath] = (stat[1], stat[2])
                else:
                    #TODO Do we want to keep a record of the files of untargeted subfolders?
                    stat = get_status(i_abspath)
                    file_statii[i_abspath] = stat[0]
                    hashes[i_abspath] = (stat[1], stat[2])
        elif os.path.isfile(item):
            stat = get_status(item)
            file_statii[item] = stat[0]
            hashes[item] = (stat[1], stat[2])

    for s in dir_statii.values():
        dir_codes[s] += 1
        codes[s] += 1
    for s in file_statii.values():
        file_codes[s] += 1
        codes[s] += 1

    moves = {}
    for path in file_statii:
        if file_statii[path] == "C":
            for hpath in hashes:
                if hashes[path][0] == hashes[hpath][1] and hpath != path:
                    moves[path] = "%s (%s)" % (hpath, hashes[hpath][1]) #todo did I break it

    return {
        "dirs": dir_statii,
        "files": file_statii,
        "d_codes": dir_codes,
        "f_codes": file_codes,
        "codes": codes,
        "hashes": hashes,
        "dups": moves,
    }
