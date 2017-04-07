import signal
import subprocess

from datetime import datetime
from multiprocessing import Process, Queue
from time import sleep

import cmd
import util
import conf

class ChitinDaemon(object):

    @staticmethod
    def handle_post(block, post_q, client_uuid):
        command_r = util.emit('command/get/', {
            'uuid': block["uuid"]
        }, client_uuid)
        cmd_uuid = command_r["uuid"]

        # disgusting
        stdout = block["stdout"]
        stderr = block["stderr"]

        end_clock = block["end_clock"]
        start_clock = block["start_clock"]
        return_code = block["return_code"]
        cmd_str = command_r["cmd_str"]


        if return_code != 0:
            # Should probably still check tokens and such...
            print("[WARN] Command %s exited with non-zero code." % cmd_str)
            block.update({"post": True, "success": False, "removed": False})
            util.emit('command/update/', {
                "uuid": cmd_uuid,
                "text": {
                    "stdout": stdout,
                    "stderr": stderr
                }
            }, client_uuid)
            post_q.put(block)
            return

        run_meta = {"wall": str(end_clock - start_clock)}
        #####################################

        # Update field tokens
        fields = cmd_str.split(" ")
        token_p = util.parse_tokens(fields)
        watched_dirs = token_p["dirs"]
        watched_dirs.add(command_r["job_path"])
        watched_files = token_p["files"]
        cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths

        # Parse the output
        meta = {}
        if cmd.can_parse(fields[0]):
            parsed_meta = cmd.attempt_parse(fields[0], cmd_str, stdout, stderr)
            meta.update(parsed_meta)
        meta["run"] = run_meta

        # Look for changes
        #TODO This is gross
        status = util.check_status_set2(watched_dirs | watched_files)
        if status["codes"]["U"] != sum(status["codes"].values()):
            print("\n".join(["%s\t%s" % (v, k) for k,v in sorted(status["files"].items(), key=lambda s: s[0]) if v!='U']))
            for path, status_code in status["files"].items():
                usage = False
                if status_code == "U":
                    usage = True
                    if path not in fields:
                        continue
                util.emit('resource/update/', {
                    "path": path,
                    "cmd_uuid": cmd_uuid,
                    "status_code": status_code,
                    "path_hash": util.hashfile(path),
                    "node_uuid": conf.NODE_UUID,
                }, client_uuid)
            for orig_path, new_path in status["moves"].items():
                print("*\t%s -> %s" % (orig_path, new_path))
                util.emit('resource/update/', {
                    "path": orig_path,
                    "new_path": new_path,
                    "cmd_uuid": cmd_uuid,
                    "status_code": 'V',
                    "path_hash": util.hashfile(path),
                    "node_uuid": conf.NODE_UUID,
                }, client_uuid)

        # Terrible way to run filetype handlers
        #util.check_integrity_set2(watched_files, skip_check=block["cmd_block"]["skip_integrity"])
        util.check_integrity_set2(watched_files)

        # Pretty hacky way to get the UUID cmd str
        token_p = util.parse_tokens(fields, insert_uuids=True)
        uuid_cmd_str = " ".join(token_p["fields"]) # Replace cmd_str to use abspaths
        util.emit('command/update/', {
            "uuid": cmd_uuid,
            "cmd_uuid_str": uuid_cmd_str,
            "cmd_meta": meta,
        }, client_uuid)
        block.update({"post": True, "success": True, "removed": False})
        post_q.put(block)

    @staticmethod
    def orchestrate(cmd_q, output_q, post_q, result_q, MAX_PROC, RES_PROC, SHELL_MODE, client_uuid):
        try:
            process_dict = {}
            completed_uuid = set()
            uuids_remaining = 0
            WAIT_FOR_DONE = False
            DONE_ANYTHING = False
            while True:
                if not SHELL_MODE and len(process_dict) == 0 and uuids_remaining == 0 and WAIT_FOR_DONE:
                    break

                # Clear all finished post-handle jobs (free any processes)
                while True:
                    block = None
                    try:
                        block = post_q.get(False)
                    except:
                        break

                    cmd_uuid = block["uuid"]

                    if not block["removed"]:
                        process_dict[cmd_uuid].terminate()
                        del process_dict[cmd_uuid]

                    if SHELL_MODE:
                        result_q.put(block)

                    completed_uuid.add(cmd_uuid)
                    DONE_ANYTHING = True

                    if not block["removed"]:
                        command_r = util.emit('command/get/', {
                            'uuid': block["uuid"]
                        }, client_uuid)
                        if command_r["blocked_by"]:
                            completed_uuid.remove(command_r["blocked_by"])
                        uuids_remaining -= 1

                    # Any additional post command duties
                    util.emit('command/update/', {
                        "uuid": cmd_uuid,
                        "return_code": block["return_code"],
                    }, client_uuid)

                # Now try to check whether there's room to run some post-handles
                if len(process_dict) < (MAX_PROC+RES_PROC):
                    block = None
                    try:
                        block = output_q.get(False)
                    except:
                        pass

                    if block:
                        cmd_uuid = block["uuid"]
                        process_dict[cmd_uuid].terminate()
                        process_dict[cmd_uuid] = Process(target=ChitinDaemon.handle_post,
                                args=(block, post_q, client_uuid))
                        process_dict[cmd_uuid].daemon = True
                        process_dict[cmd_uuid].start()

                        # We want to prioritise results processing to prevent
                        # scenarios where future jobs are unqueueable due to
                        # waiting on tasks that are completed but not marked as such
                        continue

                if len(process_dict) < MAX_PROC and not WAIT_FOR_DONE:

                    #TODO FUTURE If this fails, we loop and cannot SIGINT
                    block = util.emit('command/fetch/', {
                        'node': conf.NODE_NAME,
                        'queue': 'default',
                    }, client_uuid)

                    if not block:
                        if DONE_ANYTHING and not SHELL_MODE:
                            WAIT_FOR_DONE = True
                        continue

                    cmd_uuid = block["uuid"]
                    if block["blocked_by"] is not None:
                        if block["blocked_by"] not in completed_uuid:
                            util.emit('command/update/', {
                                "uuid": cmd_uuid,
                                "claimed": False,
                            }, client_uuid)
                            continue

                    process_dict[cmd_uuid] = Process(target=ChitinDaemon.run_command,
                            args=(cmd_uuid, output_q, client_uuid))
                    process_dict[cmd_uuid].daemon = True
                    process_dict[cmd_uuid].start()
                    uuids_remaining += 1
                else:
                    print("zzz")
                    sleep(1)
        except Exception as e:
            print("[DEAD] Fatal error occurred during command orchestration. The daemon has terminated.")
            raise
            return
        finally:
            output_q.close()
            post_q.close()

    @staticmethod
    def run_command(cmd_uuid, output_q, client_uuid):
        block = util.emit('command/get/', {
            'uuid': cmd_uuid
        }, client_uuid)
        def preexec_function():
            # http://stackoverflow.com/questions/5045771/python-how-to-prevent-subprocesses-from-receiving-ctrl-c-control-c-sigint <3
            # Ignore the SIGINT signal by setting the handler to the standard signal handler SIG_IGN
            signal.signal(signal.SIGINT, signal.SIG_IGN)

        # Check whether files have been altered outside of environment before proceeding
        token_p = util.parse_tokens(block["cmd_str"].split(" "))
        #for failed in util.check_integrity_set2(token_p["dirs"] | token_p["files"], skip_check=block["skip_integrity"]):
        for failed in util.check_integrity_set2(token_p["dirs"] | token_p["files"]):
                print("[WARN] '%s' has been modified outside of lab book." % failed)

        start_clock = datetime.now()
        proc = subprocess.Popen(
                block["cmd_str"],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                #env=dict(os.environ).update(block["env_vars"]),
                preexec_fn = preexec_function,
        )
        stdout, stderr = proc.communicate()
        end_clock = datetime.now()

        output_q.put({
            "uuid": block["uuid"],
            "stdout": stdout,
            "stderr": stderr,
            "start_clock": start_clock,
            "end_clock": end_clock,
            "return_code": proc.returncode,
        })



def daemonize(MAX_PROC=8, RES_PROC=2):
    out_q = Queue()
    post_q = Queue()
    result_q = Queue()
    daemon = Process(target=ChitinDaemon.orchestrate,
        args=(None, out_q, post_q, result_q, MAX_PROC, RES_PROC, True, None))
    daemon.start()
