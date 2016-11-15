import os
import subprocess
import sys
import uuid

from datetime import datetime

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
from pygments.lexers import BashLexer

import cmd
import util

def history(file_path):
    f = util.get_file_record(file_path)
    if not f:
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                print("No history.")
        else:
            print("No such path.")
    else:
        print f.path
        event_sets = {
            "actions": f.events.filter(record.ItemEvent.result_type!='U'),
            "usage": f.events.filter(record.ItemEvent.result_type=='U')
        }

        for e_set in ["actions", "usage"]:
            print e_set.upper()
            for j in event_sets[e_set]:
                print "{}\t{}\t{}\t{}\t{}".format(
                    j.event.timestamp.strftime("%c"),
                    j.event.user,
                    j.hash,
                    j.result_type,
                    j.event.cmd,
                )
                for m in j.event.meta.all():
                    print "{}{}\t{}\t{}".format(
                        " " * 80,
                        m.category,
                        m.key,
                        m.value
                    )
                for m in j.event.items.all():
                    print "{}{}\t{}".format(
                        " " * 80,
                        m.item.path,
                        m.hash,
                    )
            print ""

def how(path, hash):
    abspath = os.path.abspath(path)
    item = None
    try:
        ie = record.ItemEvent.query.join(record.Item).filter(record.ItemEvent.hash==hash, record.Item.path==abspath)[0]
    except IndexError:
        print "Not found..."
        return

    print "{}\t{}\t{}\t{}\t{}".format(
        ie.event.timestamp.strftime("%c"),
        ie.event.user,
        ie.hash,
        ie.result_type,
        ie.event.cmd,
    )
    for m in ie.event.meta.all():
        print "{}{}\t{}\t{}".format(
            " " * 80,
            m.category,
            m.key,
            m.value
        )
    for m in ie.event.items.all():
        print "{}{}\t{}".format(
            " " * 80,
            m.item.path,
            m.hash,
        )

def needed(path, hash):
    abspath = os.path.abspath(path)
    item = None
    try:
        ie = record.ItemEvent.query.join(record.Item).filter(record.ItemEvent.hash==hash, record.Item.path==abspath)[0]
    except IndexError:
        print "Not found..."
        return

    crit_paths = [i.item.path for i in ie.event.items.all()]
    events = [ie.event]
    uuids = set()
    needed_ies = []
    while len(events) > 0:
        event = events.pop()
        if event.uuid in uuids:
            continue
        uuids.add(event.uuid)
        for ie in event.items.all():
            if os.path.isdir(ie.item.path):
                continue

            if ie.result_type != 'U' and ie.item.path in crit_paths:
                needed_ies.append("%s (%s)\n\t%s" % (ie.item.path, ie.hash, ie.event.cmd))
                crit_paths.extend([i.item.path for i in ie.event.items.all()] )

            try:
                events.append(record.ItemEvent.query.join(record.Item).filter(record.ItemEvent.hash==ie.hash, record.Item.path==ie.item.path, record.ItemEvent.result_type!='U')[0].event)
            except IndexError:
                pass

    for ie in reversed(needed_ies):
        print ie

def discover(path):
    abspath = os.path.abspath(path)
    status = util.check_status_path_set(set(abspath))
    print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status.items(), key=lambda s: s[0]) if v!='U']))
    for path, status_code in status.items():
        if status_code == "C":
            status_code = "A"
        util.write_status(path, status_code, cmd_str)

def script(path):
    abspath = os.path.abspath(path)

def shell():
    cmd_history = InMemoryHistory()
    message = "Chitin v0.0.1"

    special_commands = {
        "history": history,
        #"discover": discover,
        "how": how,
        "needed": needed,
    }

    def get_bottom_toolbar_tokens(cli):
        return [(Token.Toolbar, ' '+message)]

    style = style_from_dict({
        Token.Toolbar: '#ffffff bg:#333333',
    })
    completer = SystemCompleter()
    del completer.completers["executable"]

    # Check whether files in and around the current directory have been changed...
    for failed in util.check_integrity_set(set(".")):
        print("[WARN] '%s' has been modified outside of lab book." % failed)
    try:
        while True:
            cmd_str = ""
            while len(cmd_str.strip()) == 0:
                cmd_str = prompt(u'===> ',
                        history=cmd_history,
                        auto_suggest=AutoSuggestFromHistory(),
                        completer=completer,
                        lexer=PygmentsLexer(BashLexer),
                        get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                        style=style,
                )
            fields = cmd_str.split(" ")

            # Special command handling
            if cmd_str[0] == '@' or cmd_str[0] == '%':
                special_cmd = fields[0][1:]
                if special_cmd in special_commands:
                    try:
                        special_commands[special_cmd](*fields[1:])
                    except TypeError as e:
                        print e
                        print("Likely incorrect usage of '%s'" % special_cmd)
                cmd_str=""
                continue

            # Determine files and folders on which to watch for changes
            token_p = util.parse_tokens(fields)
            token_p["dirs"].add(".")
            watched_dirs = token_p["dirs"]
            watched_files = token_p["files"]

            # Check whether files have been altered outside of environment before proceeding
            for failed in util.check_integrity_set(watched_dirs | watched_files):
                print("[WARN] '%s' has been modified outside of lab book." % failed)

            # Check whether any named files have results (usages) attached to files that
            # haven't been signed off...?
            pass

            # EXECUTE
            #####################################
            cmd_uuid = uuid.uuid4()
            cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths
            start_clock = datetime.now()

            proc = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            end_clock = datetime.now()

            print(stdout)
            print(stderr)
            print(cmd_uuid)

            if proc.returncode > 0:
                # Should probably still check tokens and such...
                continue

            run_meta = {"wall": str(end_clock - start_clock)}
            #####################################

            # Update field tokens
            fields = cmd_str.split(" ")
            token_p = util.parse_tokens(fields)
            new_dirs = token_p["dirs"] - watched_dirs
            new_files = token_p["files"] - watched_files
            cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

            # Parse the output
            #TODO New files won't yet have a file record so we can't use get_file_record in cmd.py
            meta = {}
            if cmd.can_parse(fields[0]):
                ap = cmd.attempt_parse(fields[0], cmd_str, stdout, stderr)
                meta["params"] = ap[0]
                meta["stdout"] = ap[1]
                meta["stdout"] = ap[2]
            meta["run"] = run_meta

            # Look for changes
            status = util.check_status_path_set(watched_dirs | watched_files | new_files | new_dirs)
            print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status["dirs"].items(), key=lambda s: s[0]) if v!='U']))
            print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status["files"].items(), key=lambda s: s[0]) if v!='U']))


            if status["codes"]["U"] != sum(status["codes"].values()):
                for path, status_code in status["dirs"].items() + status["files"].items():
                    usage = False
                    if status_code == "U":
                        usage = True
                        if path not in fields:
                            continue
                    util.write_status(path, status_code, cmd_str, usage=usage, meta=meta, uuid=cmd_uuid)

            for dup in status["dups"]:
                util.add_file_record(dup, None, None, parent=status["dups"][dup])


            message = "%s (%s): %d files changed, %d created, %d deleted." % (
                    cmd_str, run_meta["wall"], status["f_codes"]["M"], status["f_codes"]["C"], status["f_codes"]["D"]
            )

    except KeyboardInterrupt:
        print("Bye!")


if __name__ == "__main__":
    shell()
