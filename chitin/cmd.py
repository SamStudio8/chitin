import re
import os

import handlers

command_handlers = {
    "find": handlers.FindCommandHandler,
    "bowtie2": handlers.BowtieCommandHandler,
}

filetype_handlers = {
    "bam": handlers.BamFileHandler,
    "vcf": handlers.VcfFileHandler,
    "fq": handlers.FastqFileHandler,
    "fastq": handlers.FastqFileHandler,
}

def attempt_parse_type(path):
    for t in filetype_handlers:
        if path.lower().endswith("." + t):
            ret = filetype_handlers[t](path).make_metadata()
            ret["handler"] = t
            return ret
    return {}

def attempt_integrity_type(path):
    for t in filetype_handlers:
        if path.lower().endswith("." + t):
            ret = filetype_handlers[t](path).check_integrity()
            ret["handler"] = t
            return ret
    return {}


def can_parse(command):
    return command in command_handlers

def attempt_parse(command, cmd_str, stdout, stderr):
    if not can_parse(command):
        return

    handled = command_handlers[command](cmd_str.split(" ")[1:], stdout, stderr)
    return {
            "cmd": handled.handle_command(),
            "stdout": handled.handle_stdout(),
            "stderr": handled.handle_stderr(),
    }

