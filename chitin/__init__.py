import os
import subprocess
import sys

from datetime import datetime

from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
from pygments.lexers import BashLexer

import util

#TODO What about scripts? We could read them line by line for tokens...?

def history(file_path):
    f = util.get_file_record(file_path)
    if not f:
        if os.path.exists(file_path):
            if os.path.isfile(file_path):
                print("No history.")
        else:
            print("No such path.")
    else:
        if f["parent"]:
            print("PARENT RECORD: %s\n" % f["parent"])
        for key in ["history", "usage"]:
            print(key.upper())
            if len(f[key]) == 0:
                print("No recorded %s" % key)
                continue

            lastdigest = None
            for h in f[key]:
                if lastdigest != h["digest"]:
                    digest = h["digest"]
                    lastdigest = digest
                else:
                    digest = (15*' ') + "''" + (15*' ')
                print("%s\t%s\t%s\t%s" % (
                    datetime.fromtimestamp(h["timestamp"]).strftime('%c'),
                    h["user"],
                    digest,
                    h["cmd"],
                ))
            print("")

def discover(path):
    abspath = os.path.abspath(path)
    status = util.check_status_path_set(set(abspath))
    print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status.items(), key=lambda s: s[0]) if v!='U']))
    for path, status_code in status.items():
        if status_code == "C":
            status_code = "A"
        util.write_status(path, status_code, cmd_str)

def shell():
    cmd_history = InMemoryHistory()
    message = "Chitin v0.0.1"

    special_commands = {
        "history": history,
        #"discover": discover,
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
                    except TypeError:
                        print("Likely incorrect usage of '%s'" % special_cmd)
                cmd_str=""
                continue

            # Determine files and folders on which to watch for changes
            token_p = util.parse_tokens(fields)
            token_p["dirs"].add(".")
            watched_dirs = token_p["dirs"]
            watched_files = token_p["files"]
            cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

            # Check whether files have been altered outside of environment before proceeding
            for failed in util.check_integrity_set(watched_dirs | watched_files):
                print("[WARN] '%s' has been modified outside of lab book." % failed)

            # EXECUTE
            #####################################
            cmd_str = " ".join(fields)
            try:
                p = subprocess.check_output(cmd_str, shell=True)
                print(p)
            except subprocess.CalledProcessError:
                pass
            #####################################

            # Update field tokens
            fields = cmd_str.split(" ")
            token_p = util.parse_tokens(fields)
            new_dirs = token_p["dirs"] - watched_dirs
            new_files = token_p["files"] - watched_files
            cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

            # Look for changes
            status = util.check_status_path_set(watched_dirs | watched_files | new_files | new_dirs)
            print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status["dirs"].items(), key=lambda s: s[0]) if v!='U']))
            print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status["files"].items(), key=lambda s: s[0]) if v!='U']))

            if status["codes"]["U"] != sum(status["codes"].values()):
                for path, status_code in status["dirs"].items():
                    util.write_status(path, status_code, cmd_str)
                for path, status_code in status["files"].items():
                    util.write_status(path, status_code, cmd_str)

            for dup in status["dups"]:
                util.add_file_record(dup, None, None, parent=status["dups"][dup])

            message = "%s: %d files changed, %d created, %d deleted." % (
                    cmd_str, status["f_codes"]["M"], status["f_codes"]["C"], status["f_codes"]["D"]
            )

            #message = "\n".join(messages)

    except KeyboardInterrupt:
        print("Bye!")


if __name__ == "__main__":
    shell()
