import re


def find_stdout(lines):
    import os

    results = 0
    lengths = {}

    for line in lines.split("\n"):
        line = line.strip()
        if len(line) == 0:
            continue
        results += 1

        fields = line.split(os.path.sep)
        last = fields[-1]
        if len(last) not in lengths:
            lengths[len(last)] = 0
        lengths[len(last)] += 1

    return {
        "results": results,
        "lengths": lengths,
    }

def find_cmd(cmd_str):
    s = re.search(r'.* -name (.*)$|\s.*', cmd_str, re.M|re.I)
    return {
        "name": s.group(1)
    }

find_job = {
    "cmd_handler": find_cmd,
    "stdout_handler": find_stdout,
}


handlers = {
    "find": find_job
}

def can_parse(command):
    return command in handlers

def attempt_parse(command, cmd_str, output):
    if command not in handlers:
        return

    print "***"
    print "HANDLER: ", command
    print ""
    print "cmd_handler"
    print handlers[command]["cmd_handler"](cmd_str)
    print ""
    print "stdout_handler"
    print handlers[command]["stdout_handler"](output)

    return (
            handlers[command]["cmd_handler"](cmd_str),
            handlers[command]["stdout_handler"](output)
    )

