import os
import re
import subprocess
import sys
import uuid

from datetime import datetime
from multiprocessing import Process, Queue

from prompt_toolkit import prompt, AbortAction
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
from pygments.lexers import BashLexer

import cmd
import util

VERSION = "Chitin 0.0.1a: Curious Crustacean"
WELCOME = VERSION + """
Please don't rely on the database schema to be the same tomorrow... <3

Source and Issues   https://github.com/SamStudio8/chitin
Documentation       https://chitin.readthedocs.io
About               https://samnicholls.net/2016/11/16/disorganised-disaster/

== What do? ==
Execute one-liner commands as if this were your normal shell.
Currently interactive and multi-line commands don't work, sorry about that.

== Special Commands ==
%history <path>         List complete history for a given path
%how <path> <md5>       List history for given path and a particular hash
%needed <path> <md5>    List required commands and files to generate a file hash
%hashdir <path> <md5>   List hashes of directory contents for a given dir hash
%script <path> [...]    Execute a bash script (very beta and awesomely grim)

%q                      Switch suppression of stderr and stdout
%i                      Switch performing full pre-command integrity checks
"""

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

#TODO Bonus points for allowing one to order by name or timestamp
#TODO Additional bonus points for allowing one to ignore subdirs or not
def hashdir(path, hash):
    abspath = os.path.abspath(path)
    if not os.path.exists(abspath) or not os.path.isdir(abspath):
        print("Not a valid directory?")
        return

    dir_ie_record = None
    try:
        dir_ie_record = record.ItemEvent.query.join(record.Item).filter(record.ItemEvent.hash==hash, record.Item.path==abspath)[0]
    except IndexError:
        print("Not a directory that I have encountered?")
        return

    # Get items that contain the abspath in their path, that have Events before the hash of the target directory
    potential_item_set = record.ItemEvent.query.join(record.Item).filter(record.Item.path.like(abspath+'%')).join(record.Event).filter(record.Event.timestamp <= dir_ie_record.event.timestamp).group_by(record.Item.path).order_by(record.Item.path).all()

    #TODO This is a gross workaround for not having the concept of ItemSets...
    for ie in potential_item_set:
        if ie.hash != '0':
            print "%s\t%s" % (ie.hash, ie.item.path)

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

special_commands = {
    "history": history,
    #"discover": discover,
    "how": how,
    "needed": needed,
    "hashdir": hashdir,
    "script": None,
}

class ChitinDaemon(object):

    def __init__(self, MAX_PROC=32):
        self.MAX_PROC = MAX_PROC
        self.processes = {}

    def run(self, cmd_q, output_q):
        try_outs = False
        WAIT_TO_DONE = False
        while True:
            if cmd_q.empty() or try_outs == True or WAIT_TO_DONE == True:
                try_outs = False
                if output_q.empty():
                    if WAIT_TO_DONE == True and len(self.processes) == 0:
                        return
                    continue

                block = output_q.get()
                cmd_uuid = block["uuid"]
                self.processes[cmd_uuid].terminate()
                Chitin.handle_post_command(block)
                del self.processes[cmd_uuid]

            else:
                if len(self.processes) < self.MAX_PROC:
                    block = cmd_q.get()

                    if not block:
                        WAIT_TO_DONE = True
                        continue

                    cmd_uuid = block["uuid"]
                    self.processes[cmd_uuid] = Process(target=self.run_command,
                            args=(block, output_q))
                    self.processes[cmd_uuid].start()
                else:
                    print("Not enough processes currently. Will wait a little while.")
                    try_outs = True



    def run_command(self, block, output_q):
        print("INTG", block["uuid"])
        # Check whether files have been altered outside of environment before proceeding
        if not block["skip_integrity"]:
            for failed in util.check_integrity_set(block["wd"] | block["wf"], file_tokens=block["tokens"]["files"]):
                print("[WARN] '%s' has been modified outside of lab book." % failed)
        else:
            print("[WARN] You are brave... PRE-COMMAND INTEGRITY CHECKS ARE DISABLED")

        # Check whether any named files have results (usages) attached to files that
        # haven't been signed off...?
        pass

        print("EXEC", block["uuid"])
        print(block["cmd"])
        start_clock = datetime.now()
        proc = subprocess.Popen(
                block["cmd"],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(os.environ).update(block["env_vars"]),
        )
        stdout, stderr = proc.communicate()
        end_clock = datetime.now()

        output_q.put({
            "uuid": block["uuid"],
            "stdout": stdout,
            "stderr": stderr,
            "start_clock": start_clock,
            "end_clock": end_clock,
            "cmd_block": block,
            "return_code": proc.returncode,
        })

class Chitin(object):

    def __init__(self):
        self.variables = {}
        self.meta = {}

        self.skip_integrity = False
        self.suppress = False
        self.ignore_dot = False
        self.ignore_parents = False

        self.cmd_q = Queue()
        self.out_q = Queue()

        d = ChitinDaemon(MAX_PROC=32)
        self.d = d
        daemon = Process(target=d.run, #TODO This seems to actually copy Chitin to the worker
            args=(self.cmd_q, self.out_q))
        daemon.start()



    def queue_command(self, cmd_uuid, cmd_str, env_vars, watch_dirs, watch_files, input_meta, tokens, self_flags):
        print("Queued.")
        self.cmd_q.put({
            "uuid": cmd_uuid,
            "cmd": cmd_str,
            "env_vars": env_vars,
            "wd": watch_dirs,
            "wf": watch_files,
            "input_meta": input_meta,
            "suppress": self_flags["suppress"],
            "tokens": tokens,
            "skip_integrity": self_flags["skip_integ"],
            "ignore_parents": self_flags["ignore_parents"],
        })

    def attempt_special(self, cmd_str):
        # Special command handling
        fields = cmd_str.split(" ")
        SKIP = False

        command_set = []
        if cmd_str[0] == '@' or cmd_str[0] == '%':
            special_cmd = fields[0][1:]
            if special_cmd == "script":
                command_set = self.parse_script(fields[1], *fields[2:])
            elif special_cmd == "q":
                if self.suppress:
                    self.suppress = False
                else:
                    self.suppress = True
                SKIP = True
            elif special_cmd == "i":
                if self.skip_integrity:
                    self.skip_integrity = False
                else:
                    self.skip_integrity = True
                SKIP = True
            elif special_cmd in special_commands:
                try:
                    special_commands[special_cmd](*fields[1:])
                    SKIP = True
                except TypeError as e:
                    print e
                    print("Likely incorrect usage of '%s'" % special_cmd)
        return SKIP, command_set

    def super_handle(self, command_set, dry=False):
        s_handled = {}
        for command_i, command in enumerate(command_set):
            handled = self.handle_command(command.split(" "), self.variables, self.meta, dry)

            """
            if handled:
                if "cmd_str" in handled:
                    if "cmd_str" not in s_handled:
                        s_handled["cmd_str"] = []
                    s_handled["cmd_str"].append(handled["cmd_str"])
            """
            print("")
            #####################################

        #TODO return aggregate message for scripts instead of last message
        return s_handled

    def end_q(self):
        self.cmd_q.put(None)


    @staticmethod
    def handle_post_command(block):
        # disgusting
        stdout = block["stdout"]
        stderr = block["stderr"]

        end_clock = block["end_clock"]
        start_clock = block["start_clock"]
        env_vars = block["cmd_block"]["env_vars"]
        return_code = block["return_code"]
        cmd_str = block["cmd_block"]["cmd"]
        cmd_uuid = block["cmd_block"]["uuid"]
        input_meta = block["cmd_block"]["input_meta"]

        watched_dirs = block["cmd_block"]["wd"]
        watched_files = block["cmd_block"]["wf"]

        suppress = block["cmd_block"]["suppress"]

        if not suppress:
            print(stdout)
            print(stderr)

        if return_code > 0:
            # Should probably still check tokens and such...
            return

        run_meta = {"wall": str(end_clock - start_clock)}
        #####################################

        # Update field tokens
        fields = cmd_str.split(" ")
        token_p = util.parse_tokens(fields, env_vars, ignore_parents=block["cmd_block"]["ignore_parents"])
        new_dirs = token_p["dirs"] - watched_dirs
        new_files = token_p["files"] - watched_files
        cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

        # Parse the output
        #TODO New files won't yet have a file record so we can't use get_file_record in cmd.py
        meta = {}
        if cmd.can_parse(fields[0]):
            parsed_meta = cmd.attempt_parse(fields[0], cmd_str, stdout, stderr)
            meta.update(parsed_meta)
        meta.update(input_meta)
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

        #TODO Commented out for now as %needed can now follow cp and mv
        #for dup in status["dups"]:
        #    util.add_file_record(dup, None, None, parent=status["dups"][dup])

        message = "%s (%s): %d files changed, %d created, %d deleted." % (
                cmd_str, run_meta["wall"], status["f_codes"]["M"], status["f_codes"]["C"], status["f_codes"]["D"]
        )

        return {
            "message": message,
        }


    def handle_command(self, fields, env_variables, input_meta, dry=False):
        cmd_uuid = str(uuid.uuid4())

        # Determine files and folders on which to watch for changes
        token_p = util.parse_tokens(fields, env_variables, ignore_parents=self.ignore_parents)
        if not self.ignore_dot:
            token_p["dirs"].add(".")
        watched_dirs = token_p["dirs"]
        watched_files = token_p["files"]

        # Collapse new command tokens to cmd_str and print cmd with uuid to user (before warnings)
        cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

        if dry:
            return {
                "message": "There was no effect.",
                "cmd_str": cmd_str
            }

        ### Queue for Execution
        self.queue_command(cmd_uuid, cmd_str, env_variables, watched_dirs, watched_files, input_meta, token_p,
                {"suppress": self.suppress,
                 "skip_integ": self.skip_integrity,
                 "ignore_parents": self.ignore_parents})


    def parse_script(self, path, *tokens):
        def check_line(line):
            if len(line.strip()) < 2:
                return False
            if line[0] == '#' and not line[1] == '@':
                return False
            return True
        script_lines = [l.strip() for l in open(path).readlines() if check_line(l)]

        # Split the blocks
        blocks = []
        current_block = []
        in_block = False
        input_map = {}
        input_meta = {}

        for line in script_lines:
            if line.startswith("#@CHITIN_START_BLOCK"):
                if len(current_block) > 0:
                    blocks.append(current_block)
                    current_block = []
                else:
                    in_block = True
            elif line.startswith("#@CHITIN_END_BLOCK"):
                if len(current_block) > 0:
                    blocks.append(current_block)
                    current_block = []
                in_block = False

            elif line.startswith("#@CHITIN_INPUT"):
                v_fields = line.split(" ")
                input_map[int(v_fields[1])] = v_fields[2]

            elif line.startswith("#@CHITIN_META"):
                v_fields = line.split(" ")
                input_meta[v_fields[1]] = v_fields[2]

            else:
                if in_block:
                    current_block.append(line)
                else:
                    blocks.append([line])

        meta = {"script": {"path": path}}
        fixed_blocks = []
        for b in blocks:
            BLOCK_COMMAND = "; ".join(b)
            for i, value in enumerate(tokens):
                BLOCK_COMMAND = BLOCK_COMMAND.replace("$" + str(i+1), str(value))
                meta["script"][input_map[i+1]] = value
            fixed_blocks.append(BLOCK_COMMAND)

        meta["script"].update(input_meta)

        self.meta.update(meta)
        return fixed_blocks

def shell():
    c = Chitin()

    cmd_history = FileHistory(os.path.expanduser('~') + '/.chitin.history')
    print(WELCOME)
    message = VERSION

    def get_bottom_toolbar_tokens(cli):
        return [(Token.Toolbar, ' '+message)]

    style = style_from_dict({
        Token.Toolbar: '#ffffff bg:#333333',
    })
    completer = SystemCompleter()
    del completer.completers["executable"]

    # Check whether files in and around the current directory have been changed...
    print("Performing opening integrity check...")
    for failed in util.check_integrity_set(set(".")):
        print("[WARN] '%s' has been modified outside of lab book." % failed)
    try:
        while True:
            cmd_str = ""
            while len(cmd_str.strip()) == 0:
                if c.suppress:
                    current_prompt = u"~~~>"
                else:
                    current_prompt = u"===>"

                if c.skip_integrity:
                    current_prompt = u'!' + current_prompt
                else:
                    current_prompt = u'' + current_prompt

                cmd_str = prompt(current_prompt,
                        history=cmd_history,
                        auto_suggest=AutoSuggestFromHistory(),
                        completer=completer,
                        lexer=PygmentsLexer(BashLexer),
                        get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                        style=style,
                        on_abort=AbortAction.RETRY,
                )


            fields = cmd_str.split(" ")
            command_set = [" ".join(fields)]

            skip, special_command_set = c.attempt_special(cmd_str)
            if skip:
                continue
            if len(special_command_set) > 0:
                command_set = special_command_set

            #####################################
            handled = c.super_handle(command_set)
            if handled:
                if "message" in handled:
                    message = handled["message"]
                else:
                    message = VERSION
            #####################################

    except EOFError:
        print("Bye!")


if __name__ == "__main__":
    shell()
