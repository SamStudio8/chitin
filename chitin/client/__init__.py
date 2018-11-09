import hashlib
import signal
import subprocess
import uuid
import os
import sys

from datetime import datetime
#from shutil import which
from whichcraft import which # fucking python2v3 bullshit in 2018 ffs

#import chitin.client.api as api
from .api import base
from . import conf


import syslog
syslog.openlog('chitind')

def hashfile(path, start_clock, halg=hashlib.md5, bs=65536, force_hash=False, partial_limit=10737418240, partial_sample=5368709120):
    start_time = datetime.now()

    hashed=False
    mod_time = os.path.getmtime(path)
    if mod_time >= int(start_clock.strftime("%s")) or force_hash:

        # For files less than partial_limit, just get on with it
        if os.path.getsize(path) <= partial_limit:
            f = open(path, 'rb')
            buff = f.read(bs)
            halg = halg()
            halg.update(buff)
            while len(buff) > 0:
                buff = f.read(bs)
                halg.update(buff)
            f.close()
            hashed=True
        else:
            # I want to ensure no hashing process takes longer than 5 minutes
            # Caveat: The longer the file is, the more sparse the samples are
            # NOTE This is probably a fucking terrible idea

            # Assuming a total of partial_sample bytes to sample for the hash,
            # find the skip size needed to evenly sample the file with bs blocks
            file_size_middleish = int(os.path.getsize(path)) - (2 * 100 * bs)
            num_blocks_maxsample = (partial_sample / bs)-200  # Number of available samples
            seek_size = int(file_size_middleish / num_blocks_maxsample) # Break the file into block pieces

            # Read the first 100 blocks
            f = open(path, 'rb')
            halg = halg()
            for i in range(100):
                buff = f.read(bs)
                halg.update(buff)

            # Now seek to the evenly distributed sample points across the middleish
            tell = f.tell()
            for pos in range(tell, file_size_middleish + tell - bs, seek_size):
                f.seek(pos)
                buff = f.read(bs)
                halg.update(buff)

            # And just finish the buffer (should be ~100 blocks)
            while len(buff) > 0:
                buff = f.read(bs)
                halg.update(buff)
            f.close()
            hashed=True
    else:
        # The file /probably/ hasn't change, so don't bother rehashing...
        pass

    ret = None
    if hashed:
        ret = halg.hexdigest()

    end_time = datetime.now()
    hash_time = end_time - start_time
    syslog.syslog('Hashed %s (%.2fGB in %s)' % (path, float(os.path.getsize(path)) / 1e+9, str(hash_time)))

    return ret


def parse_tokens(fields):
    dirs_l = []
    file_l = []
    executables = []

    for field_i, field in enumerate(fields):
        had_semicolon = False
        if field[-1] == ";":
            had_semicolon = True
            field = field.replace(";", "")

        if field[0] == "~":
            expand_field = os.path.expanduser(field)
            if os.path.exists(expand_field):
                field = expand_field

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

    print {
        "fields": fields,
        "files": set(file_l),
        "dirs": set(dirs_l),
        "executables": set(executables),
    }
    return {
        "fields": fields,
        "files": set(file_l),
        "dirs": set(dirs_l),
        "executables": set(executables),
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

        run_meta = {"wall": str(end_clock - start_clock)}

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

        # Parse the output
        meta = {}
        #if cmd.can_parse(fields[0]):
        #    parsed_meta = cmd.attempt_parse(fields[0], cmd_str, stdout, stderr)
        #    meta.update(parsed_meta)
        meta["run"] = run_meta

        # Look for changes
        paths = inflate_path_set(watched_dirs | watched_files)
        resource_info = []
        for path in paths:
            resource_hash = '0'
            resource_size = 0
            resource_exists = os.path.exists(path)
            if resource_exists:
                resource_hash = hashfile(path, start_clock, force_hash=path in precommand_paths)
                resource_size = os.path.getsize(path)

            resource_info.append({
                #TODO Need a nice way to get the NODE UUID
                "node_uuid": conf.NODE_UUID,
                "path": path,
                "exists": resource_exists,
                "precommand_exists": path in precommand_paths,
                "hash": resource_hash,
                "size": resource_size,
            })

        # Terrible way to run filetype handlers
        #check_integrity_set2(watched_files)

        # Pretty hacky way to get the UUID cmd str
        #token_p = parse_tokens(fields, insert_uuids=True)
        #uuid_cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths
        base.emit2("command/update", {
            "cmd_uuid": cmd_uuid,
            "meta": meta,
            "return_code": return_code,
            "text": {
                "stdout": stdout.decode('utf-8'),
                "stderr": stderr.decode('utf-8'),
            },
            "resources": resource_info,
            "started_at": int(start_clock.strftime("%s")),
            "finished_at": int(end_clock.strftime("%s")),
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
            resource_hash = hashfile(path, timestamp, force_hash=True)
            resource_size = os.path.getsize(path)

        resource_info.append({
            #TODO Need a nice way to get the NODE UUID
            "node_uuid": conf.NODE_UUID,
            "path": path,
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

    base.emit2("resource/meta", {
        "node_uuid": conf.NODE_UUID,
        "path": sys.argv[1],
        "timestamp": int(datetime.now().strftime("%s")),

        "metadata": [
            {
                "tag": sys.argv[2],
                "name": sys.argv[3],
                "type": "str",
                "value": sys.argv[4],
            }
        ],
    })
