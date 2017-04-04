import record

node1 = record.Node("default", "default.example.com", "My Node")
record.add_and_commit(node1)

q1 = record.CommandQueue("default", node1)
record.add_and_commit(q1)

print "NODE_NAME='", node1.name, "'"
print "NODE_UUID='", node1.uuid, "'"
