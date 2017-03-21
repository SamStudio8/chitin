import re
import os

class CommandHandler(object):

    def __init__(self, command_tokens, stdout, stderr):
        self.cmd_tokens = command_tokens
        self.cmd_str = " ".join(command_tokens)
        self.stdout = [l.strip() for l in stdout.split("\n") if len(l.strip()) > 0]
        self.stderr = [l.strip() for l in stderr.split("\n") if len(l.strip()) > 0]

    def handle_stderr(self):
        return {}

    def handle_stdout(self):
        return {}

    def handle_command(self):
        return {}

    def get_version(self):
        return {}


class FiletypeHandler(object):

    def __init__(self, path):
        self.path = path

    def check_integrity(self):
        return {}

    def make_metadata(self):
        return {}


################################################################################

class FindCommandHandler(CommandHandler):

    def handle_command(self):
        try:
            s = re.search(r'.* -name (.*)$|\s.*', self.cmd_str, re.M|re.I)
            return {
                "name": s.group(1)
            }
        except:
            return {}

    def handle_stdout(self):
        import os

        results = 0
        lengths = {}

        for line in self.stdout:
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

class BowtieCommandHandler(CommandHandler):

    def handle_command(self):
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
        fields = self.cmd_tokens
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

    def handle_stderr(self):
        try:
            return {
                "alignment": float(self.stderr[-1].split("%")[0].strip())
            }
        except IndexError:
            return {}

################################################################################

class BamFileHandler(FiletypeHandler):

    def check_integrity(self):
        from subprocess import check_output
        reads = 0
        try:
            p = check_output("samtools view -c %s" % self.path, shell=True)
            reads = int(p.split("\n")[0].strip())
        except Exception as e:
            print e
            pass

        has_index = False
        has_indate_index = None
        if os.path.exists(self.path + ".bai"):
            has_index = True
            if os.path.getmtime(self.path) <= os.path.getmtime(self.path + ".bai"):
                has_indate_index = True
            else:
                has_indate_index = False

        return {
            ("has_reads", "has 0 reads"): reads > 0,
            ("has_index", "has no BAI"): has_index,
            ("has_indate_index", "has a BAI older than itself"): has_indate_index,
        }

    def make_metadata(self):
        from subprocess import check_output
        try:
            p = check_output("samtools view -c %s" % self.path, shell=True)
            return {"read_n": p.split("\n")[0].strip()}
        except:
            return {}

class VcfFileHandler(FiletypeHandler):

    def check_integrity(self):
        from subprocess import check_output
        variants = 0
        try:
            p = check_output("grep -vc '^#' %s" % self.path, shell=True)
            variants = p.split("\n")[0].strip()
        except Exception as e:
            pass

        return {
            ("has_variants", "has 0 variants"): variants > 0,
        }

    def make_metadata(self):
        from subprocess import check_output
        try:
            p = check_output("grep -vc '^#' %s" % self.path, shell=True)
            return {"snp_n": p.split("\n")[0].strip()}
        except:
            return {}

class FastqFileHandler(FiletypeHandler):

    def check_integrity(self):
        return {
            ("not_empty", "is empty"): os.path.getsize(self.path) > 0,
        }

    def make_metadata(self):
        return {}


class ErrFileHandler(FiletypeHandler):

    def check_integrity(self):
        return {
            ("empty", "is not empty"): os.path.getsize(self.path) == 0,
        }

    def make_metadata(self):
        return {}
