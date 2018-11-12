import re
import os

from . import handlers

command_handlers = {
    "find": handlers.FindCommandHandler,
    "bowtie2": handlers.BowtieCommandHandler,
}

filetype_handlers = {
    "bam": handlers.BamFileHandler,
    "vcf": handlers.VcfFileHandler,
    "fa": handlers.FastaFileHandler,
    "fasta": handlers.FastaFileHandler,
    "fq": handlers.FastqFileHandler,
    "fastq": handlers.FastqFileHandler,
    "err": handlers.ErrFileHandler,
}

def attempt_parse_type(path):
    if not can_parse_type(path):
        return []

    t = path.lower().split('.')[-1]
    ret = filetype_handlers[t](path).make_metadata()

    return [
        #TODO Need to support more types
        { "tag": t, "name": key, "type": "str", "value": ret[key] } for key in ret
    ]

def attempt_integrity_type(path):
    for t in filetype_handlers:
        if path.lower().endswith("." + t):
            ret = filetype_handlers[t](path).check_integrity()
            ret["handler"] = t
            return ret
    return {}


def can_parse_type(path):
    return path.lower().split('.')[-1] in filetype_handlers

def can_parse_exec(exec_basename):
    return exec_basename in command_handlers

def attempt_parse_exec(exec_basename, exec_path, cmd_str, stdout, stderr):
    if not can_parse_exec(exec_basename):
        return {}

    #TODO Could check version here with new exec_path variable?
    handled = command_handlers[exec_basename](cmd_str.split(" ")[1:], stdout, stderr)
    return {
            "cmd": handled.handle_command(),
            "stdout": handled.handle_stdout(),
            "stderr": handled.handle_stderr(),
    }

