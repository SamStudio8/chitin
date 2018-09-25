from datetime import datetime

def add_command(cmd_str):
    return ("COMMAND_ADD", {
        "cmd_str": cmd_str,
        "queued_at": int(datetime.now().strftime("%s")),
    })

def update_command(cmd_uuid, return_code):
    return ("COMMAND_UPDATE", {
        "cmd_uuid": cmd_uuid,
        "finished_at": int(datetime.now().strftime("%s")),
        "return_code": return_code,
    }, cmd_uuid)

#def add_command_on_resource(cmd_uuid, node_uuid, res_path, new_hash):
#    return ("COMMAND_UPDATE", {
#        "cmd_uuid": cmd_uuid,
#        "resources": {
#            node_uuid: {
#                res_path: {
#                    "hash": new_hash,
#                }
#            }
#        }
#    }, cmd_uuid)

