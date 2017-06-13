def add_resource(curr_path, curr_hash, node_uuid):
    return ("RESOURCE_ADD", {
        "node_uuid": node_uuid,
        "curr_path": curr_path,
        "curr_hash": curr_hash
    })
