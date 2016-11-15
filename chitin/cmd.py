import re
import os


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
def find_stderr(lines):
    return {
    }

def bowtie_stdout(lines):
    return {
    }
def bowtie_stderr(lines):
    lines = [l for l in lines.split("\n") if len(l.strip()) > 0]
    return {
        "alignment": float(lines[-1].split("%")[0].strip())
    }


find_job = {
    "cmd_handler": find_cmd,
    "stdout_handler": find_stdout,
    "stderr_handler": find_stderr,
}

bowtie_job = {
    "cmd_handler": bowtie_cmd,
    "stdout_handler": bowtie_stdout,
    "stderr_handler": bowtie_stderr,
}


handlers = {
    "find": find_job,
    "bowtie2": bowtie_job
}


def vcf_handler(path):
    from subprocess import check_output
    try:
        p = check_output("grep -vc '^#' %s" % path, shell=True)
        return {"snp_n": p.split("\n")[0].strip()}
    except:
        return {}

def bam_handler(path):
    from subprocess import check_output
    try:
        p = check_output("samtools view -c %s" % path, shell=True)
        return {"read_n": p.split("\n")[0].strip()}
    except:
        return {}

def bam_integ_handler(path):
    from subprocess import check_output

    reads = 0
    try:
        p = check_output("samtools view -c %s" % path, shell=True)
        reads = int(p.split("\n")[0].strip())
    except Exception as e:
        print e
        pass

    has_index = False
    has_ood_index = None
    if os.path.exists(path + ".bai"):
        has_index = True
        if os.path.getmtime(path) > os.path.getmtime(path + ".bai"):
            has_ood_index = True
        else:
            has_ood_index = False

    return {
        ("has_reads", "has 0 reads"): reads > 0,
        ("has_index", "has no BAI"): has_index,
        ("has_ood_index", "has a BAI older than itself"): has_ood_index,
    }


type_watchers = {
    "vcf": vcf_handler,
    "bam": bam_handler,
}

type_integrity = {
    "bam": bam_integ_handler,
}

def attempt_parse_type(path):
    for t in type_watchers:
        if path.lower().endswith("." + t):
            ret = type_watchers[t](path)
            ret["handler"] = t
            return ret
    return {}

def attempt_integrity_type(path):
    for t in type_integrity:
        if path.lower().endswith("." + t):
            ret = type_integrity[t](path)
            ret["handler"] = t
            return ret
    return {}


def can_parse(command):
    return command in handlers

def attempt_parse(command, cmd_str, stdout, stderr):
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
            handlers[command]["stdout_handler"](stdout),
            handlers[command]["stderr_handler"](stderr)
    )

