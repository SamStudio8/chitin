import os
import signal
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

import daemon
import util
import conf

#import multiprocessing, logging
#mpl = multiprocessing.log_to_stderr()
#mpl.setLevel(logging.DEBUG)

VERSION = "Chitin 0.0.3a: Curious Crustacean (develop)"
WELCOME = VERSION + """
Please don't rely on the database schema to be the same tomorrow... <3

Source and Issues   https://github.com/SamStudio8/chitin
Documentation       https://chitin.readthedocs.io
About               https://samnicholls.net/2016/11/16/disorganised-disaster/

== What do? ==
Execute one-liner commands as if this were your normal shell.
Currently interactive and multi-line commands don't work, sorry about that.

== Special Commands ==
%q                      Switch suppression of stderr and stdout
%i                      Switch performing full pre-command integrity checks

%j                      Show command result buffer list
%o <job>                Show stdout for given command result number
"""

special_commands = {
}

class Chitin(object):

    def __init__(self, MAX_PROC=8, RES_PROC=2, SHELL_MODE=False):
        self.variables = {}
        self.meta = {}

        self.client_uuid = str(uuid.uuid4())

        self.skip_integrity = False
        self.suppress = False
        self.ignore_dot = False

        self.out_q = Queue()
        self.post_q = Queue()
        self.result_q = Queue()

        self.MAX_RESULTS = 10
        self.curr_result_ptr = 0
        self.results = [None] * self.MAX_RESULTS

        self.show_stderr=False

        signal.signal(signal.SIGINT, self.signal_handler)
        self.daemon = Process(target=daemon.ChitinDaemon.orchestrate,
            args=(None, self.out_q, self.post_q, self.result_q, MAX_PROC, RES_PROC, SHELL_MODE, self.client_uuid))
        self.daemon.start()


    def signal_handler(self, signal, frame):
        #TODO ew
        if frame.f_code.co_name != "orchestrate":
            return

        # Purge uncompleted jobs from cmd_q
        r = util.emit('command/purge/', {
            'node': conf.NODE_NAME,
            'queue': 'default',
        }, self.client_uuid)
        print("Purged %d jobs." % r["count"])

        # Wait for running jobs to complete
        print("Waiting for remaining jobs to complete.")
        print("chitin should die automatically.")

    def attempt_special(self, cmd_str):
        # Special command handling
        fields = cmd_str.split(" ")
        SKIP = False

        command_set = []
        if cmd_str[0] == '@' or cmd_str[0] == '%':
            SKIP = True
            special_cmd = fields[0][1:]
            if special_cmd == "script":
                command_set = self.parse_script(fields[1], *fields[2:])
                SKIP = False #there's always one
            elif special_cmd == "o":
                self.print_stdout(int(fields[1]))
            elif special_cmd == "j":
                self.print_results(force=True)
                print("")
            elif special_cmd == "q":
                if self.suppress:
                    self.suppress = False
                else:
                    self.suppress = True
            elif special_cmd == "i":
                if self.skip_integrity:
                    self.skip_integrity = False
                else:
                    self.skip_integrity = True
            elif special_cmd in special_commands:
                try:
                    special_commands[special_cmd](*fields[1:])
                except TypeError as e:
                    print e
                    print("Likely incorrect usage of '%s'" % special_cmd)
        return SKIP, command_set

    def super_handle(self, command_set, run=None):
        self.execute(command_set, run=run)

    #TODO FUTURE default is a shit default
    def exe_script(self, script, job_uuid, job_params, node="default", queue="default"):
        for p in job_params:
            if not job_params[p]:
                print("[FAIL] Unset experiment parameter '%s'. Job NOT submitted." % p)
                return None

        # TODO Should probably prevent overriding of defaults?
        util.emit('job/update/', {
            'job_uuid': job_uuid,
            'params': job_params,
        }, self.client_uuid)

        commands = self.parse_script2(script, job_params)
        self.execute(commands, run=job_uuid, node=node, queue=queue) #could actually get the UUID from the run_params["job_uuid"]

    def execute(self, command_set, run=None, node="default", queue="default"):
        cmd_block_uuid = util.emit('command-block/add/', {
            'uuid': run
        }, self.client_uuid)["uuid"]
        last_uuid = None
        for command_i, command in enumerate(command_set):
            token_p = util.parse_tokens(command.split(" "))

            # Collapse new command tokens to cmd_str
            cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

            cmd_uuid = util.emit('command/add/', {
                'cmd_str': cmd_str,
                'cmd_block': cmd_block_uuid,
                'blocked_by': last_uuid
            }, self.client_uuid)["uuid"]
            #util.add_command_meta(cmd.uuid, self.meta) TODO -- we don't really want to repeat this experiment data for every command
            last_uuid = cmd_uuid

            # Add to queue
            util.emit('command/queue/', {
                'cmd_uuid': cmd_uuid,
                'node': node,
                'queue': queue,
            }, self.client_uuid)

    def parse_script2(self, path, param_d):
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
                if in_block:
                    current_block.append(line)
                else:
                    # Not currently in a block, so just make a new block with the current line
                    blocks.append([line])

        meta = {"script": {"path": path}}
        fixed_blocks = []
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
            fixed_blocks.append(BLOCK_COMMAND)

        meta["script"].update(input_meta)

        self.meta.update(meta)
        return fixed_blocks

    def parse_script(self, path, *tokens):
        print("[WARN] parse_script is deprecated, use parse_script2 instead.")
        print("       parse_script2 accepts a dictionary of named parameters")
        print("       parse_script will wrap parse_script2 eventually without further notice")
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

    def move_result_q(self):
        temp_ptr = self.curr_result_ptr
        while not self.result_q.empty():
            block = self.result_q.get()
            if block:
                self.results[self.curr_result_ptr] = block
                self.curr_result_ptr += 1

            if self.curr_result_ptr == self.MAX_RESULTS:
                self.curr_result_ptr = 0
        return temp_ptr != self.curr_result_ptr

    def print_results(self, force=False):
        #if self.move_result_q() or force:
        #    for pos in range(self.curr_result_ptr-1, -1, -1) + range(self.MAX_RESULTS-1,self.curr_result_ptr-1,-1):
        #        block = self.results[pos]
        #        if block is not None:
        #            print("(%d) %s...%s\t%s" % (pos, block["uuid"][:6], block["uuid"][-5:], block["cmd_str"][:61]))
        pass

    def print_stdout(self, pos):
        #TODO Would be well nice if we could just spawn `less` with the stdout lines here...
        #block = self.results[pos]
        #if block is not None:
        #    print("(%d) %s...%s\t%s" % (pos, block["uuid"][:6], block["uuid"][-5:], block["cmd_str"][:61]))
        #    print(block["stdout"])
        print("[WARN] Sorry I broke this for now")
        pass

def shell():
    c = Chitin(SHELL_MODE=True)

    cmd_history = FileHistory(os.path.expanduser('~') + '/.chitin.history')
    print(WELCOME)
    message = VERSION

    project_uuid = util.register_or_fetch_project("Shell Sessions")
    exp_uuid = util.register_experiment(os.path.abspath('.'), project_uuid, name="Shell Session @ %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"), shell=True)
    run_uuid, params = util.register_job(exp_uuid)

    def get_bottom_toolbar_tokens(cli):
        return [(Token.Toolbar, ' '+message)]

    style = style_from_dict({
        Token.Toolbar: '#ffffff bg:#333333',
    })
    completer = SystemCompleter()
    del completer.completers["executable"]

    # Check whether files in and around the current directory have been changed...
    print("Performing opening integrity check...")
    for failed in util.check_integrity_set2(set(".")):
        print("[WARN] '%s' has been modified outside of lab book." % failed)
    try:
        skip = False
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

                if not skip:
                    c.print_results()
                    if len(cmd_str.strip()) > 0:
                        print("")

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

            c.execute(command_set, run=run_uuid, node=conf.NODE_NAME)

    except EOFError:
        print("Bye!")
        c.daemon.terminate()


def make_web():
    from record import app
    import web.web
    app.run()

if __name__ == "__main__":
    shell()
