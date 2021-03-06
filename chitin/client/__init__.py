import signal
import subprocess
import uuid
import os
import sys
import glob

from datetime import datetime
#from shutil import which
from whichcraft import which # fucking python2v3 bullshit in 2018 ffs

#import chitin.client.api as api
from .api import base
from . import cmd
from . import conf
from . import util



def parse_tokens(fields):
    dirs_l = []
    file_l = []
    maybe_file_l = []
    executables = []

    fields.append( os.path.abspath(".") ) # always spy on the current dir, i guess?
    for field_i, field in enumerate(fields):
        had_semicolon = False
        if field[-1] == ";":
            had_semicolon = True
            field = field.replace(";", "")

        if field[0] == "~":
            expand_field = os.path.expanduser(field)
            if os.path.exists(expand_field):
                field = expand_field

        if '*' in field:
            # Let's try some fucking globbo
            # Don't update the actual field though, because it'll probably be a fucking disaster
            file_l.extend([os.path.abspath(x) for x in glob.glob(field)])

        #if field.startswith("chitin://"):
        #    resource = get_resource_by_uuid(field.split("chitin://")[1])
        #    if resource:
        #        field = resource["current_path"]
        abspath = os.path.abspath(field)

        # Does the path exist? We might want to add its parent directory
        if os.path.exists(abspath):
            field_ = abspath

            if had_semicolon:
                fields[field_i] = field_ + ';' # Update the command to use the full abspath
            else:
                fields[field_i] = field_ # Update the command to use the full abspath
        else:
            # Is the field an executable in the PATH?
            which_path = which(field)
            if which_path:
                executables.append(which_path)

            # Perhaps this is a file that has previously existed or is about to exist?
            if os.path.exists(os.path.dirname(abspath)):
                maybe_file_l.append(abspath)
            continue

        ### Files
        if os.path.isfile(abspath):
            file_l.append(abspath)

            # Is the path an executable script?
            if os.access(abspath, os.X_OK):
                executables.append(abspath)

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
        "fields": fields[:-1], # remove sneaky abspath(.) field
        "files": set(file_l),
        "dirs": set(dirs_l),
        "maybe_files": set(maybe_file_l),
        "executables": {os.path.basename(p):p for p in set(executables)},
    }

def inflate_path_set(path_set):
    paths = set({})
    for item in path_set:
        item = os.path.abspath(item)

        if os.path.isdir(item):
            for subitem in os.listdir(item):
                i_abspath = os.path.join(item, subitem)
                if os.path.isdir(i_abspath):
                    #TODO Do we want to keep track of the files of untargeted subfolders?
                    pass
                else:
                    paths.add(i_abspath)
        elif os.path.isfile(item):
            paths.add(item)

    return paths

class ClientDaemon(object):
    @staticmethod
    def run_command(cmd_uuid, cmd_str):
        def preexec_function():
            # http://stackoverflow.com/questions/5045771/python-how-to-prevent-subprocesses-from-receiving-ctrl-c-control-c-sigint <3
            # Ignore the SIGINT signal by setting the handler to the standard signal handler SIG_IGN
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        #Check whether files have been altered outside of environment before proceeding
        #token_p = parse_tokens(cmd_str.split(" "))
        #for failed in check_integrity_set2(token_p["dirs"] | token_p["files"]):
        #        print("[WARN] '%s' has been modified outside of lab book." % failed)

        # Organise watch lists (to keep track of deleted files later)
        fields = cmd_str.split(" ")
        token_p = parse_tokens(fields)
        watched_dirs = token_p["dirs"]
        watched_files = token_p["files"]

        precommand_paths = inflate_path_set( set(watched_files) )

        start_clock = datetime.now()
        proc = subprocess.Popen(
                cmd_str,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                #env=dict(os.environ).update(block["env_vars"]),
                preexec_fn = preexec_function,
        )
        stdout, stderr = proc.communicate()
        end_clock = datetime.now()
        return_code = proc.returncode

        run_meta = [
            { "tag": "meta", "name": "wall", "type": "int", "value": str(end_clock - start_clock)}
        ]

        if return_code != 0:
            #TODO Future: We should do something here - like warn/stop the command?
            pass

        #####################################

        # Update field tokens (to find newly created files)
        fields = cmd_str.split(" ")
        token_p = parse_tokens(fields)
        watched_dirs = watched_dirs.union(token_p["dirs"])
        #watched_dirs.add(command_r["job_path"])
        watched_files = watched_files.union(token_p["files"])

        cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

        # Parse the output, apply any appropriate executable handlers
        meta = []
        for executie_name in token_p["executables"]:
            if cmd.can_parse_exec(executie_name):
                parsed_meta = cmd.attempt_parse_exec(executie_name, token_p["executables"][executie_name], cmd_str, stdout, stderr)
                meta.extend(parsed_meta)
        meta.extend( run_meta )

        # Look for changes
        paths = set(precommand_paths).union(set(inflate_path_set(watched_dirs | watched_files)))
        resource_info = []
        for path in paths:
            resource_hash = '0'
            resource_size = 0
            resource_exists = os.path.exists(path)
            if resource_exists:
                resource_hash = util.hashfile(path, start_clock, force_hash=path in precommand_paths)
                resource_size = os.path.getsize(path)

                # Run any appropriate filetype handlers IF the hash has changed
                fmeta = []
                if resource_hash:
                    if cmd.can_parse_type(path):
                        parsed_meta = cmd.attempt_parse_type(path)
                        fmeta.extend(parsed_meta)

            resource_info.append({
                "node_uuid": util.get_node(path)[1],
                "path": path,
                "name": os.path.basename(path),
                "lpath": path.split(os.path.sep)[1:-1],
                "exists": resource_exists,
                "precommand_exists": path in precommand_paths,
                "hash": resource_hash,
                "size": resource_size,
                "metadata": fmeta,
            })

        # Pretty hacky way to get the UUID cmd str
        #token_p = parse_tokens(fields, insert_uuids=True)
        #uuid_cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths
        base.emit2("command/update", {
            "cmd_uuid": cmd_uuid,
            "return_code": return_code,
            "text": {
                "stdout": stdout.decode('utf-8'),
                "stderr": stderr.decode('utf-8'),
            },
            "resources": resource_info,
            "started_at": int(start_clock.strftime("%s")),
            "finished_at": int(end_clock.strftime("%s")),
            "metadata": meta,
        }, to_uuid=None)

class Client(object):

    def __init__(self):
        self.meta = {}

    def signal_handler(self):
        pass

    def parse_script(self, script_path, param_d=None):
        if not param_d:
            param_d = {}

        def check_line(line):
            if len(line.strip()) <= 1:
                # Ignore lines with a single character (after strip)
                return False
            if line[0] == '#' and not line[1] == '@':
                # Skip any comments that aren't meant for Chitin
                return False
            return True

        script_lines = [l.strip() for l in open(script_path).readlines() if check_line(l)]

        input_map = {}      # Map a CHITIN_INPUT parameter to a "dollar" number
        input_meta = {}     # Store key-value pairs of metadata for display later

        blocks = []         # Parsed command blocks
        current_block = []  # Current command block to be appended to
        in_block = False    # Flag for whether we are in or out of a block

        # Read each line from the script and sort them into blocks (delimited by
        # CHITIN_START_BLOCK and CHITIN_END_BLOCK).
        for line in script_lines:
            if line.startswith("#@CHITIN_START_BLOCK"):
                if len(current_block) > 0:
                    # Catch scenario where there is a missing CHITIN_END_BLOCK
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
                # Map the parameter name (defined in the script) to its dollar number
                # We will replace all $N with the value from param_d with the matching key
                v_fields = line.split(" ")
                input_map[v_fields[2]] = int(v_fields[1])

            elif line.startswith("#@CHITIN_META"):
                v_fields = line.split(" ")
                try:
                    input_meta[v_fields[1]] = v_fields[2]
                except IndexError:
                    pass

            else:
                # Elsewise this is a regular script line
                if in_block:
                    current_block.append(line)
                else:
                    # Not currently in a block, so just make a new block with the current line
                    blocks.append([line])

        meta = {"script": {"path": script_path}}

        # Polish blocks by adding semi-colons between multiple script lines and
        # insert any mapped parameters to the appropriate "dollar" variable
        command_blocks = []
        for b in blocks:
            BLOCK_COMMAND = "; ".join(b)

            # Blindly replace variables using the parameter dictionary
            for param_name, param_value in param_d.items():
                try:
                    # Look up which dollar number to replace in the bash script
                    BLOCK_COMMAND = BLOCK_COMMAND.replace("$" + str(input_map[param_name]), str(param_value))
                    meta["script"][param_name] = param_value
                except KeyError:
                    pass
            command_blocks.append(BLOCK_COMMAND)

        # Update the meta dictionary for the client, this gets uploaded later
        meta["script"].update(input_meta)
        self.meta.update(meta)

        return command_blocks

    #def exe_script(self, script, job_uuid, job_params, node="default", queue="default"): ??? how to get params to SGE...
    def execute_script(self, script_path):
        #for p in job_params:
        #    if not job_params[p]:
        #        print("[FAIL] Unset experiment parameter '%s'. Job NOT submitted." % p)
        #        return None
        commands_list = self.parse_script(script_path)
        self.execute(commands_list)

    def execute(self, commands_list):
        group_uuid = str(uuid.uuid4())
        for command_i, command in enumerate(commands_list):
            cmd_uuid = str(uuid.uuid4())

            # Collapse new command tokens to cmd_str
            token_p = parse_tokens(command.split(" "))
            cmd_str = " ".join(token_p["fields"]) # cmd_str now uses abspaths

            base.emit2("command/new", {
                "cmd_uuid": cmd_uuid,
                "group_uuid": group_uuid,
                "cmd_str": cmd_str,
                "queued_at": int(datetime.now().strftime("%s")),
                "order": command_i,
            })

            # Run and handle command
            ClientDaemon.run_command(cmd_uuid, cmd_str)




#class ChitinSGEClient(object):
#    def do(self, script):
#        # parse meta lines for SGE too
#        pass

def exec_script():
    from chitin.client import Client
    c = Client()
    c.execute_script(sys.argv[1])

def cli():
    if len(sys.argv) == 1:
        print("its chitin")
        print("ls\t\tlist the contents of this directory")
        return
    if sys.argv[1] == "ls":
        if len(sys.argv) == 3:
            path = os.path.abspath(sys.argv[2])
        else:
            path = os.path.abspath('.')
        node_path, node_uuid = util.get_node(path)
        res = base.emit2("group/view", {
            "node_uuid": node_uuid,
            "path": path,
            "lpath": node_path.split(os.path.sep)[1:],
        })
        print(res["group"]["name"])
        for resource in sorted(res["group"]["resources"], key=lambda x: x["name"]):
            print("%s\t%s" % (resource["uuid"], resource["name"]))

def notice():
    cmd_uuid = str(uuid.uuid4())
    timestamp = datetime.now()
    base.emit2("command/new", {
        "cmd_uuid": cmd_uuid,
        "cmd_str": 'chitin-notice %s' % sys.argv[1],
        "queued_at": int(timestamp.strftime("%s"))-1,
        "order": 0,
    })
    
    resource_info = []
    for path in inflate_path_set([sys.argv[1]]):
        resource_hash = '0'
        resource_size = 0
        resource_exists = os.path.exists(path)
        if resource_exists:
            resource_hash = util.hashfile(path, timestamp, force_hash=True)
            resource_size = os.path.getsize(path)

        node_path, node_uuid = util.get_node(path)
        resource_info.append({
            "node_uuid": node_uuid,
            "path": path,
            "name": os.path.basename(path),
            "lpath": node_path.split(os.path.sep)[1:-1],
            "exists": resource_exists,
            "precommand_exists": True,
            "hash": resource_hash,
            "size": resource_size,
        })
    base.emit2("command/update", {
        "cmd_uuid": cmd_uuid,
        "meta": {},
        "return_code": None,
        "text": {
            "stdout": "",
            "stderr": "",
        },
        "resources": resource_info,
        "started_at": int(timestamp.strftime("%s")),
        "finished_at": int(timestamp.strftime("%s")),
    }, to_uuid=None)

def tag():
    import argparse
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--path")
    group.add_argument("--group")
    parser.add_argument('tag')
    parser.add_argument('name')
    parser.add_argument('value')
    args = parser.parse_args()

    path = None
    group = None
    if args.path:
        path = os.path.abspath(args.path)
    elif args.group:
        group = args.group

    base.emit2("resource/meta", {
        "node_uuid": util.get_node(path)[1],

        "path": path,
        "group_uuid": group,
        "timestamp": int(datetime.now().strftime("%s")),

        "metadata": [
            {
                "tag": args.tag,
                "name": args.name,
                "type": "str",
                "value": args.value,
            }
        ],
    })

def group():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument('resources', nargs='*')
    parser.add_argument('--parents', nargs='*')
    args = parser.parse_args()

    base.emit2("resource/group", {
        "timestamp": int(datetime.now().strftime("%s")),
        "name": args.name,
        "resources": [ {"node_uuid": util.get_node(os.path.abspath(resource)[1]), "path": os.path.abspath(resource)} for resource in args.resources],
        "parents": args.parents,
    })
