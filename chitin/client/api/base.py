import requests

# This will be a proper Queue
MESSAGES = []

def emit2(base_endpoint, payload, to_uuid=None):
    if to_uuid:
        base_endpoint += ("/%s" % to_uuid)
    r = requests.post("http://localhost:5000/" + base_endpoint + '/', json=payload)
    print r.json()

def emit(msg_type, payload, to_uuid=None):
    ENDPOINTS = {
        "RESOURCE_ADD": "resource",
        "NODE_ADD": "node",
        "COMMAND_ADD": "command",
        "COMMAND_UPDATE": "command",
    }

    endpoint = ENDPOINTS[msg_type]
    if to_uuid:
        endpoint += ("/%s" % to_uuid)
    r = requests.post("http://localhost:5000/" + endpoint + '/', json=payload)
    print r.json()

def emit_messages():
    for m in MESSAGES:
        # Send message
        # If failed, abort and wait until later
        try:
            emit(m[0], m[1], to_uuid=m[2])
        except:
            pass

def queue_emit(msg):
    try:
        MESSAGES.append( (msg[0], msg[1], msg[2]) )
    except:
        MESSAGES.append( (msg[0], msg[1], None) )
    emit_messages()

