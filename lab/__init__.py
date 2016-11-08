import os
import subprocess
import sys

from datetime import datetime

import click
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.contrib.completers import SystemCompleter
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.layout.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_dict
from prompt_toolkit.token import Token
from pygments.lexers import BashLexer

import util

@click.group()
def cli():
    pass

@cli.command(help="Open a lab shell")
def shell():
    history = InMemoryHistory()
    message = ""

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
                        history=history,
                        auto_suggest=AutoSuggestFromHistory(),
                        completer=completer,
                        lexer=PygmentsLexer(BashLexer),
                        get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                        style=style,
                )
            fields = cmd_str.split(" ")

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


@cli.command(help="List a file's history.")
@click.argument("file_path")
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

if __name__ == "__main__":
    cli()
