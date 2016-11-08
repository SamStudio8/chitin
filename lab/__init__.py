import time
import subprocess
import sys

from datetime import datetime

import click
from prompt_toolkit import prompt
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.contrib.completers import SystemCompleter, PathCompleter
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

    try:
        while True:
            cmd_str = ""
            while len(cmd_str.strip()) == 0:
                cmd_str = prompt(u'===> ',
                        history=history,
                        auto_suggest=AutoSuggestFromHistory(),
                        completer=PathCompleter(),
                        lexer=PygmentsLexer(BashLexer),
                        get_bottom_toolbar_tokens=get_bottom_toolbar_tokens,
                        style=style,
                )
            fields = cmd_str.split(" ")

            # Determine files and locations to watch for changes before and after exec
            for field_i, field in enumerate(fields):
                # Skip non-file looking things...
                if field[0] == "-":
                    continue
            util.manage_file_integrity(fields)

            # Replace the cmd_str
            cmd_str = " ".join(fields)

            metadata = {
                "cmd_str": cmd_str,
                "timestamp": int(time.mktime(datetime.now().timetuple())),
                "params": {
                    "unparsed": ""
                },
            }

            # EXECUTE
            #####################################
            try:
                p = subprocess.check_output(cmd_str, shell=True)
                print(p)
            except subprocess.CalledProcessError:
                pass
            #####################################

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
        for task in f["tasks"]:
            print(task)

if __name__ == "__main__":
    cli()
