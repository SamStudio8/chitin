from functools import wraps

from flask import render_template, Markup, Response, redirect, url_for, request, abort, jsonify

from itsdangerous import (JSONWebSignatureSerializer as Serializer, BadSignature, SignatureExpired)

from chitin import web_util, record, web_conf
from chitin.cmd import attempt_parse_type

def require_token(fn):
    """Authorisation decorator, checks for a 'token' key in the request JSON
    and ensures the token belongs to an authorised client."""

    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not request.json:
            abort(400)
            return None #???

        elif 'token' not in request.json:
            abort(400)
            return None

        client = record.Client.validate_token(web_conf.SERVER_SECRET, request.json['token'])
        if client is None:
            abort(401)
            return None

        #return fn(client_uuid=client.uuid, *args, **kwargs)
        return fn(*args, **kwargs)
    return _wrap

def require_userpass(fn):
    """Authorisation decorator, checks for 'user' and 'pass' keys in the request JSON
    and ensures the User is authorised."""

    @wraps(fn)
    def _wrap(*args, **kwargs):
        if not request.json:
            abort(400)
            return None #???

        elif 'username' not in request.json or 'password' not in request.json:
            abort(400)
            return None

        user = record.User.validate_user(request.json['username'], request.json['password'])
        if user is None:
            abort(401)
            return None

        return fn(user=user, *args, **kwargs)
    return _wrap

###############################################################################
@record.app.route('/')
def project_list():
    return render_template('projects.html', projects=record.Project.query.order_by(record.Project.last_exp_ts.desc()))

@record.app.route('/nodes/')
def node_list():
    nodes = record.Node.query.all()
    return render_template('node_list.html', nodes=nodes)

@record.app.route('/project/<project>')
def project_detail(project):
    project = record.Project.query.get_or_404(project)
    return render_template('project.html', project=project)

@record.app.route('/experiment/<experiment>')
def experiment_detail(experiment):
    exp = record.Experiment.query.get_or_404(experiment)
    return render_template('experiment.html', exp=exp)

@record.app.route('/run/<run>')
def run_detail(run):
    run = record.Job.query.get_or_404(run)
    return render_template('run.html', run=run)

@record.app.route('/text/<text>')
def text_detail(text):
    text = record.CommandText.query.get_or_404(text)
    return Response(text.text, mimetype="text/plain")

@record.app.route('/resource/<resource>')
def resource_detail(resource):
    resource = record.Resource.query.get_or_404(resource)
    ghosts = web_util.get_ghosts_by_path(resource.current_path, uuid=resource.uuid)
    return render_template('resource.html', resource=resource, ghosts=ghosts)

@record.app.route('/live')
def live():
    current_queue = record.Command.query.filter(record.Command.claimed == True, record.Command.return_code == -1).order_by(record.Command.position)
    waiting = record.Command.query.filter(record.Command.claimed == False, record.Command.return_code == -1).order_by(record.Command.position)
    return render_template('live.html', current_queue=current_queue, waiting=waiting)

@record.app.route('/search')
def search():
    query = request.json.get('search')

    if record.Resource.query.get(query):
        return redirect(url_for('resource_detail', resource=query))
    elif record.Experiment.query.get(query):
        return redirect(url_for('experiment_detail', experiment=query))
    elif record.Job.query.get(query):
        return redirect(url_for('run_detail', run=query))
    elif record.Project.query.get(query):
        return redirect(url_for('project_detail', project=query))
    else:
        #return redirect(url_for('project_list'))
        abort(404)


#todo url_for
@record.app.template_filter('chitin')
def chitin_filter(s):
    try:
        fields = s.split(" ")
        for i, f in enumerate(fields):
            if f.startswith("chitin://"):
                fields[i] = Markup("<a href='/resource/" + f.replace("chitin://", "") +"'>" + f + "</a>")
            else:
                resource = web_util.get_resource_by_path(f)
                if resource:
                    fields[i] = Markup("<a href='/resource/" + resource.uuid  +"'>" + f + "</a>")
        return " ".join(fields)
    except:
        return s

###############################################################################
#TODO Need to sanity check these interfaces, do they have the right params?
@record.app.route('/api/project/add/', methods = ['POST'])
@require_token
def create_project():
    name = request.json.get("name")
    project = record.Project.query.filter(record.Project.name == name).first()
    if not project:
        project = record.Project(name)
        record.add_and_commit(project)

    return jsonify({
        'uuid': project.uuid
    }), 201


@record.app.route('/api/experiment/add/', methods = ['POST'])
@require_token
def create_experiment():
    path = request.json.get("path")
    project = web_util.get_project_by_uuid(request.json.get("project_uuid"))
    params = request.json.get("params", {})
    name = request.json.get("name", None)
    shell = request.json.get("shell", False)

    exp = record.Experiment(path, project, name=name, shell=shell)
    record.add_and_commit(exp)

    #TODO Would be nice to check whether params[p] is a Resource?
    if params:
        for i, p in enumerate(params):
            p = record.ExperimentParameter(exp, p, params[p])
            record.db.session.add(p)

    record.db.session.commit()
    return jsonify({
        'uuid': exp.uuid,
        'path': exp.get_path(),
    }), 201

@record.app.route('/api/experiment/get/', methods = ['POST'])
@require_token
def get_experiment():
    exp = web_util.get_experiment_by_uuid(request.json.get("uuid"))

    if not exp:
        return jsonify({
        }), 400
    else:
        return jsonify({
            'uuid': exp.uuid,
            'path': exp.get_path(),
        }), 201

@record.app.route('/api/job/add/', methods = ['POST'])
@require_token
def create_job():
    exp = web_util.get_experiment_by_uuid(request.json.get("exp_uuid"))

    if not exp:
        return jsonify({
        }), 400

    job = record.Job(exp)
    record.add_and_commit(job)

    job_params = exp.make_params()
    job_params["exp_uuid"] = exp.uuid
    job_params["job_uuid"] = job.uuid
    job_params["job_dir"] = job.get_path()

    return jsonify({
        'uuid': job.uuid,
        'path': job.get_path(),
        'params': job_params,
    }), 201

@record.app.route('/api/job/update/', methods = ['POST'])
@require_token
def update_job():
    job = web_util.get_job_by_uuid(request.json.get("job_uuid"))

    if not job:
        return jsonify({
        }), 400

    job_params = request.json.get("params", {})
    for key in job_params:
        p = record.ExperimentParameter.query.join(record.Experiment).filter(record.ExperimentParameter.key==key, record.Experiment.uuid == job.exp.uuid).first()
        if p:
            jm = record.JobMeta(job, p, job_params[key])
            record.db.session.add(jm)


    record.db.session.commit()
    return jsonify({
        'uuid': job.uuid,
    }), 201

@record.app.route('/api/resource/get/', methods = ['POST'])
@require_token
def get_resource():
    uuid = request.json.get("uuid")
    path = request.json.get("path")

    if uuid:
        res = web_util.get_resource_by_uuid(uuid)
    elif path:
        res = web_util.get_resource_by_path(path)

    if res:
        return jsonify({
            'uuid': res.uuid,
            'current_hash': res.current_hash,
            'current_path': res.current_path,
        }), 201
    else:
        return jsonify({
        }), 400


@record.app.route('/api/command-block/add/', methods = ['POST'])
@require_token
def create_command_block():
    run = web_util.get_job_by_uuid(request.json.get("uuid"))

    if run:
        command_block = record.CommandBlock(job_uuid=run)
        record.add_and_commit(command_block)
        return jsonify({
            'uuid': command_block.uuid,
        }), 201
    else:
        return jsonify({
        }), 201

@record.app.route('/api/command/get/', methods = ['POST'])
@require_token
def get_command():
    cmd = record.Command.query.filter(record.Command.uuid==str(request.json.get("uuid"))).first()
    if cmd:
        res = {
            "uuid": cmd.uuid,
            "cmd_str": cmd.cmd,
            "job_path": cmd.block.job.get_path(),
        }
        if cmd.blocked_by:
            res["blocked_by"] = cmd.blocked_by.uuid
        else:
            res["blocked_by"] = None
        return jsonify(res), 201
    return jsonify({
    }), 201


@record.app.route('/api/command/add/', methods = ['POST'])
@require_token
def create_command():
    blocked_by_cmd = None
    if request.json.get('blocked_by'):
        blocked_by_cmd = web_util.get_command_by_uuid(request.json.get('blocked_by'))
    block = web_util.get_block_by_uuid(request.json.get("cmd_block"))
    return_code = request.json.get('return_code', -1)

    cmd = record.Command(request.json.get('cmd_str'), block, blocked_by=blocked_by_cmd, return_code=return_code)
    record.add_and_commit(cmd)

    if cmd:
        return jsonify({
            'uuid': cmd.uuid
        }), 201
    else:
        return jsonify({
        }), 201

@record.app.route('/api/command/queue/', methods = ['POST'])
@require_token
def queue_command():
    bq = web_util.get_node_queue_by_name(request.json.get('node'), request.json.get('queue'))
    cmd = web_util.get_command_by_uuid(request.json.get('cmd_uuid'))
    if bq and cmd:
        cmd.queue = bq
        cmd.active = True
        cmd.client = request.json.get('client')
        record.db.session.commit()
        return jsonify({
            'uuid': cmd.uuid
        }), 201
    return jsonify({
    }), 201

@record.app.route('/api/command/fetch/', methods = ['POST'])
@require_token
def fetch_command():
    bq = web_util.get_node_queue_by_name(request.json.get('node'), request.json.get('queue'))
    if bq:
        block = record.Command.query.join(record.CommandQueue).filter(record.CommandQueue.uuid == bq.uuid, record.Command.return_code == -1, record.Command.claimed == False).order_by(record.Command.position).first()
        if block:
            block.claimed = True
            record.db.session.commit()

            res = {"uuid": block.uuid}
            if block.blocked_by:
                res["blocked_by"] = block.blocked_by.uuid
            else:
                res["blocked_by"] = None
            return jsonify(res), 201
    return jsonify({
    }), 201

@record.app.route('/api/command/purge/', methods = ['POST'])
@require_token
def purge_command():
    bq = web_util.get_node_queue_by_name(request.json.get('node'), request.json.get('queue'))
    client_uuid = request.json.get("client")
    if bq and client_uuid:
        count = 0
        for command in record.Command.query.join(record.CommandQueue).filter(record.CommandQueue.uuid == bq.uuid, record.Command.client == client_uuid, record.Command.claimed == False, record.Command.return_code == -1):
            command.return_code = 128
            command.active = False
            record.db.session.commit()
            count += 1
        return jsonify({
            'count': count,
        }), 201
    return jsonify({
    }), 400


@record.app.route('/api/command/update/', methods = ['POST'])
@require_token
def update_command():
    cmd = web_util.get_command_by_uuid(request.json.get("uuid"))

    if not cmd:
        return jsonify({
        }), 400

    text = request.json.get("text")
    if text and len(text) > 0:
        for key in text:
            if len(text[key]) > 0:
                ctxt = record.CommandText(cmd, key, text[key])
                record.add_and_commit(ctxt)

    cmd_uuid_str = request.json.get("cmd_uuid_str")
    if cmd_uuid_str:
        cmd.cmd_uuid_str = cmd_uuid_str

    meta_d = request.json.get("cmd_meta")
    if meta_d:
        for meta_cat in meta_d:
            for key, value in meta_d[meta_cat].items():
                record.add_and_commit(record.CommandMeta(cmd, meta_cat, key, value))

    rc = request.json.get("return_code")
    if rc is not None:
        # Heh, "if rc" evaluated False for 0 exit status. Durrrr
        cmd.return_code = rc

    claimed = request.json.get("claimed")
    if claimed is not None:
        if claimed is False:
            cmd.position += 1
        cmd.claimed = claimed

    # Should return the changed stuff for checking
    record.db.session.commit()
    return jsonify({
        "uuid": cmd.uuid
    }), 201


@record.app.route('/api/resource/update/', methods = ['POST'])
@require_token
def add_or_update_resource():
    path = request.json.get("path")
    path_hash = request.json.get("path_hash", None)
    cmd_str = request.json.get("cmd_str")
    node_uuid = request.json.get("node_uuid")
    status = request.json.get("status_code")
    cmd_uuid = request.json.get("cmd_uuid", None)
    new_path = request.json.get("new_path", None)
    metacommand = request.json.get("metacommand", False)

    resource = web_util.get_resource_by_path(path)
    if not resource:
        resource = record.Resource(web_util.get_node_by_uuid(node_uuid), path, path_hash)
        record.add_and_commit(resource)

    if cmd_uuid:
        # There is always one, except for (?)
        cmd = web_util.get_command_by_uuid(cmd_uuid)
    else:
        return_code = None
        if metacommand:
            return_code = 0

        # Dummy block
        block = record.CommandBlock(None)
        record.add_and_commit(block)

        cmd = record.Command(cmd_str, block, return_code=return_code)
        record.add_and_commit(cmd)

    if cmd:
        resource_command = record.ResourceCommand(resource, cmd, status, h=path_hash, new_path=new_path)
        record.db.session.add(resource_command)

        meta = attempt_parse_type(path)
        if meta:
            for key, value in meta.items():
                record.db.session.add(record.ResourceCommandMeta(resource_command, "handler", key, value))

    # Should return the changed stuff for checking
    record.db.session.commit()
    return jsonify({
        "uuid": resource.uuid
    }), 201

###############################################################################
@record.app.route('/api/client/add/', methods = ['POST'])
@require_userpass
def create_client(user):
    client = record.Client(user)
    record.add_and_commit(client)
    return jsonify({
        'user_uuid': user.uuid,
        'client_uuid': client.uuid,
        'client_token': client.generate_token(web_conf.SERVER_SECRET),
    }), 201

