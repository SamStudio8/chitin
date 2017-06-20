from datetime import datetime

from flask import render_template, Markup, Response, redirect, url_for, request, abort, jsonify

from chitin.core.database import db
from chitin.core.server import app
from chitin.core import api
from chitin.core import models

@app.route("/")
def home():
    return render_template("test.html")

@app.route("/node/")
def nodes():
    nodes = models.Node.query.all()
    return render_template("list_nodes.html", nodes=nodes)

@app.route("/resource/")
def resource_list():
    resources = models.Resource.query.all()
    return render_template("list_resources.html", resources=resources)

@app.route("/command/")
def command_list():
    commands = models.Command.query.all()
    return render_template("list_commands.html", commands=commands)

@app.route("/resource/<resource>")
def resource_detail(resource):
    resource = models.Resource.query.get_or_404(resource)
    return render_template("detail_resource.html", resource=resource)

@app.route("/command/<command>")
def command_detail(command):
    command = models.Command.query.get_or_404(command)
    return render_template("detail_command.html", command=command)

@app.route("/group/<group>")
def group_detail(group):
    group = models.CommandGroup.query.get_or_404(group)
    return render_template("detail_group.html", group=group)

###############################################################################

# Authenticate
# Vertify all args present (providea list and check?

@app.route("/node/", methods = ['POST'])
def add_node():
    name = request.json.get("name", None)
    node = api.add_node(name)
    if node:
        return jsonify({
            "node_uuid": node.uuid
        }), 201
    else:
        return jsonify({}), 400

@app.route("/resource/", methods = ['POST'])
def add_resource():
    node_uuid = request.json.get("node_uuid")

    node = models.Node.query.get(node_uuid)
    if not node:
        return jsonify({}), 404

    curr_path = request.json.get("curr_path")
    curr_hash = request.json.get("curr_hash")
    res_uuid = request.json.get("res_uuid", None)
    res = api.add_resource(curr_path, curr_hash, node, res_uuid)

    if res:
        return jsonify({
            "res_uuid": res.uuid,
        }), 201
    else:
        return jsonify({}), 400

@app.route("/command/", methods=["POST"])
def add_command():
    group_uuid = request.json.get("group_uuid")
    group = None
    if group_uuid:
        group = models.CommandGroup.query.get(group_uuid)

    if not group:
        group = api.add_command_group(group_uuid=group_uuid)

    cmd_str = request.json.get("cmd_str")
    queued_at = datetime.fromtimestamp(request.json.get("queued_at"))
    cmd = api.add_command(cmd_str, queued_at, group, cmd_uuid=request.json.get("cmd_uuid"))
    if cmd:
        return jsonify({
            "group_uuid": group_uuid,
            "cmd_uuid": cmd.uuid,
        }), 201
    else:
        return jsonify({}), 400

@app.route("/command/<command>/", methods=["POST"])
def update_command(command):
    cmd = models.Command.query.get(command)
    if not cmd:
        return jsonify({}), 404

    # Update other fields (must be a nicer way?)
    started_at = request.json.get("started_at", None)
    if started_at:
        cmd.started_at = datetime.fromtimestamp(started_at)

    finished_at = request.json.get("finished_at", None)
    if finished_at:
        cmd.finished_at = datetime.fromtimestamp(finished_at)

    return_code = request.json.get("return_code", None)
    if return_code is not None:
        cmd.return_code = return_code

    # Commit CMD updates
    db.session.commit()

    #TODO If there are no effects, don't add the command
    # (used to be the job of the client to determine)
    updated_resources = []
    resources = request.json.get("resources", {})
    for resource in resources:
        #TODO How to handle moves again? Is it client or server responsibility?
        #TODO Add warnings to output JSON for skipped resources
        node = models.Node.query.get(resource["node_uuid"])
        if not node:
            # Raise warnings
            continue

        res = api.get_resource_by_path(resource["node_uuid"], resource["path"])
        if not res:
            # It's a new resource!
            effect_code = "C"
            res = api.add_resource(resource["path"], resource["hash"], node, res_uuid=None)
        else:
            if not resource["exists"]:
                # Deleted
                effect_code = "D"
            elif resource["hash"] is not None and res.current_hash != resource["hash"]:
                # Modified
                effect_code = "M"
            else:
                # Used
                # Assume used if the hash hasn't been updated (TODO Is this trouble?)
                effect_code = "U"

        cor = api.add_command_on_resource(cmd, res, resource["hash"], effect_code)
        if cor:
            updated_resources.append({
                "res_uuid": res.uuid,
                "res_path": res.current_path,
                "effect_code": effect_code,
            })

    return jsonify({
        "cmd_uuid": cmd.uuid,
        "resources": updated_resources
    }), 201

