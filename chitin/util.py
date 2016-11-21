import getpass
import hashlib
import json
import os
import sys
import time
import warnings

from datetime import datetime

import record
from cmd import attempt_parse_type, attempt_integrity_type

def get_file_record(path):
    path = os.path.abspath(path)
    try:
        item = record.Item.query.filter(record.Item.path==path)[0]
    except IndexError:
        return None
    return item

def write_status(path, status, cmd_str, meta=None, usage=False, uuid=None):
    abspath = os.path.abspath(path)

    if os.path.exists(abspath):
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])
    else:
        h = 0

    add_file_record(abspath, h, cmd_str, meta=meta, status=status, uuid=uuid)

def get_status(path, cmd_str=""):
    abspath = os.path.abspath(path)

    status = None
    last_h = 0
    path_record = get_file_record(abspath)
    if os.path.exists(abspath):
        if os.path.isfile(abspath):
            h = hashfile(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])

        if path_record:
            try:
                last_h = path_record.get_last_digest()
            except IndexError:
                pass

            # Path exists and we knew about it
            if path_record.get_last_digest() != h:
                status = "M"
            else:
                status = "U"
        else:
            # Path exists but it is a surprise
            status = "C"
    elif path_record:
        h = 0
        last_h = path_record.get_last_digest()
        status = "D"

    return (status, h, last_h)

def add_file_record(path, digest, cmd_str, status=False, parent=None, meta=None, uuid=None):
    item = get_file_record(path)
    if not item:
        item = record.Item(path)
        record.db.session.add(item)
        record.db.session.commit()

    event = None
    if uuid:
        try:
            event = record.Event.query.filter(record.Event.uuid==str(uuid))[0]
        except IndexError as e:
            pass

    if not event:
        event = record.Event(cmd_str, str(uuid))
        record.db.session.add(event)

        if meta:
            for mcat in meta:
                for key in meta[mcat]:
                    datum = record.Metadatum(event, mcat, key, meta[mcat][key])
                    record.db.session.add(datum)

    itemevent = record.ItemEvent(item, event, status)
    record.db.session.add(itemevent)

    if status != 'D':
        #NOTE This is a pretty hacky way of getting around accidentally handling
        #     files that have been deleted.
        f_meta = attempt_parse_type(item.path)
        if f_meta:
            for key in f_meta:
                datum = record.Metadatum(event, item.path, key, f_meta[key])
                record.db.session.add(datum)

    record.db.session.commit()

def check_integrity_set(path_set, file_tokens=None):
    if not file_tokens:
        file_tokens = []
    failed = []
    for item in path_set:
        item = os.path.abspath(item)
        if check_integrity(item, is_token=item in file_tokens):
            failed.append(item)

        if os.path.isdir(item):
            for subitem in os.listdir(item):
                i_abspath = os.path.join(item, subitem)
                if os.path.isdir(i_abspath):
                    if check_integrity(i_abspath):
                        failed.append(i_abspath)

                    for subsubitem in os.listdir(i_abspath):
                        j_abspath = os.path.join(i_abspath, subsubitem)
                        if j_abspath in path_set:
                            continue
                        if os.path.isfile(j_abspath):
                            if check_integrity(j_abspath, is_token=j_abspath in file_tokens):
                                failed.append(j_abspath)
                else:
                    #TODO Do we want to keep a record of the files of subfolders?
                    if i_abspath in path_set:
                        continue
                    if check_integrity(i_abspath, is_token=i_abspath in file_tokens):
                        failed.append(i_abspath)
    return sorted(failed)

def check_integrity(path, is_token=False):
    abspath = os.path.abspath(path)
    broken_integrity = False
    broken_rules = {}

    path_record = get_file_record(abspath)
    if os.path.exists(abspath):
        if os.path.isfile(abspath):
            h = hashfile(abspath)
            broken_rules = attempt_integrity_type(abspath)
        elif os.path.isdir(abspath):
            h = hashfiles([os.path.join(abspath,f) for f in os.listdir(abspath) if os.path.isfile(os.path.join(abspath,f))])

        if path_record:
            # Path exists and we knew about it
            if path_record.get_last_digest() != h:
                add_file_record(abspath, h, "MODIFIED by (?)")
                broken_integrity = True
        else:
            # Path exists but it is a surprise
            add_file_record(abspath, h, "CREATED by (?)")
            broken_integrity = True
    elif path_record:
        add_file_record(abspath, h, "DELETED by (?)")
        broken_integrity = True

    #TODO I don't want this here but I can't be bothered to move it right now
    if is_token:
        for rule, result in broken_rules.items():
            if not result and result is not None:
                print "[WARN] %s %s" % (path, rule[1])

    return broken_integrity

def parse_tokens(fields, env_vars):
    dirs_l = []
    file_l = []
    for field_i, field in enumerate(fields):
        for env_k in env_vars:
            if '$' + env_k in field:
                field = field.replace('$' + env_k, str(env_vars[env_k]))
                fields[field_i] = field

        had_semicolon = False
        if field[-1] == ";":
            has_semicolon = True
            field = field.replace(";", "")
        abspath = os.path.abspath(field)

        if os.path.exists(abspath):
            if had_semicolon:
                fields[field_i] = abspath + ';' # Update the command to use the full abspath
            else:
                fields[field_i] = abspath # Update the command to use the full abspath
            dirs_l.append(os.path.dirname(abspath))
        else:
            potential_dir = os.path.dirname(abspath)
            if os.path.exists(potential_dir):
                dirs_l.append(potential_dir)
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
