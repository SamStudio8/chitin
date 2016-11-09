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
    cmd_str = " ".join(cmd_str)
    s = re.search(r'.* -name (.*)$|\s.*', cmd_str, re.M|re.I)
    return {
        "name": s.group(1)
    }



def bowtie_cmd(fields):
    import util
    import glob

    interesting = {
        "-1": "reads1",
        "-2": "reads2",
        "-x": "btindex",
        "--un": "unaligned",
        "-S": "out",
        "-U": "reads",
        }
    meta = {"leftover": []}
    skip = False
    for field_i, field in enumerate(fields):
        if skip:
            skip = False
            continue

        if field in interesting:
            try:
                if field == "-x":
                    h = util.hashfiles(glob.glob(fields[field_i + 1] + "*"))
                else:
                    #h = util.get_file_record(fields[field_i + 1])["digest"]
                    h = util.hashfile(fields[field_i + 1])
            except:
                pass
                h = 0
            meta[interesting[field]] = "%s (%s)" % (fields[field_i + 1], h)
            skip = True
            continue

        meta["leftover"].append(field)

    return meta

def bowtie_stdout(lines):
    lines = [l for l in lines.split("\n") if len(l.strip()) > 0]
    return {
        "alignment": float(lines[-1].split("%")[0].strip())
    }


find_job = {
    "cmd_handler": find_cmd,
    "stdout_handler": find_stdout,
}

bowtie_job = {
    "cmd_handler": bowtie_cmd,
    "stdout_handler": bowtie_stdout,
}


handlers = {
    "find": find_job,
    "bowtie2": bowtie_job
}

def can_parse(command):
    return command in handlers

def attempt_parse(command, cmd_str, output):
    if command not in handlers:
        return

    """
    print "***"
    print "HANDLER: ", command
    print cmd_str
    print ""
    print "cmd_handler"
    print handlers[command]["cmd_handler"](cmd_str.split(" ")[1:])
    print ""
    print "stdout_handler"
    print handlers[command]["stdout_handler"](output)
    """

    return (
            handlers[command]["cmd_handler"](cmd_str.split(" ")[1:]),
            handlers[command]["stdout_handler"](output)
    )

