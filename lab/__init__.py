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

def history(file_path):
    f = util.get_file_record(file_path)
    if not f:
        print("No history.")
    else:
        for key in ["history", "usage"]:
            print(key.upper())
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

def shell():
    cmd_history = InMemoryHistory()
    message = "Chitin v0.0.1"

    special_commands = {
        "history": history
    }

    def get_bottom_toolbar_tokens(cli):
        return [(Token.Toolbar, ' '+message)]

    style = style_from_dict({
        Token.Toolbar: '#ffffff bg:#333333',
    })
    completer = SystemCompleter()
    del completer.completers["executable"]

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
            if cmd_str[0] == '@' or cmd_str[0] == '%':
                special_cmd = fields[0][1:]
                if special_cmd in special_commands:
                    try:
                        special_commands[special_cmd](*fields[1:])
                    except TypeError:
                        print("Likely incorrect usage of '%s'" % special_cmd)
                cmd_str=""
                continue

            inputs = {}
            for field_i, field in enumerate(fields):
                abspath = os.path.abspath(field)
                if os.path.isfile(abspath):
                    fields[field_i] = abspath
                    inputs[abspath] = util.hashfile(abspath)
            util.manage_file_integrity(fields)

            # Replace the cmd_str
            cmd_str = " ".join(fields)

            # EXECUTE
            #####################################
            print(inputs)
            try:
                p = subprocess.check_output(cmd_str, shell=True)
                print(p)
            except subprocess.CalledProcessError:
                pass
            #####################################

            fields = cmd_str.split(" ")
            for field_i, field in enumerate(fields):
                abspath = os.path.abspath(field)
                if os.path.isfile(abspath):
                    fields[field_i] = abspath
            cmd_str = " ".join(fields)
            messages = util.manage_file_integrity(fields, cmd_str)
            message = "\n".join(messages)

    except KeyboardInterrupt:
        print("Bye!")


if __name__ == "__main__":
    shell()
