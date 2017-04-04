from flask import render_template, Markup, Response, redirect, url_for, request, abort, jsonify

from chitin import record, util

@record.app.route('/')
def project_list():
    return render_template('projects.html', projects=record.Project.query.order_by(record.Project.last_exp_ts.desc()))

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
    ghosts = util.get_ghosts_by_path(resource.current_path, uuid=resource.uuid)
    return render_template('resource.html', resource=resource, ghosts=ghosts)

@record.app.route('/live')
def live():
    current_queue = record.Command.query.filter(record.Command.claimed == True, record.Command.return_code == -1).order_by(record.Command.position)
    waiting = record.Command.query.filter(record.Command.claimed == False, record.Command.return_code == -1).order_by(record.Command.position)
    return render_template('live.html', current_queue=current_queue, waiting=waiting)

@record.app.route('/search')
def search():
    query = request.args.get('search')

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
                resource = util.get_resource_by_path(f)
                if resource:
                    fields[i] = Markup("<a href='/resource/" + resource.uuid  +"'>" + f + "</a>")
        return " ".join(fields)
    except:
        return s

###############################################################################

@record.app.route('/api/command-block/add/', methods = ['GET'])
def create_command_block():
    run = util.get_job_by_uuid(request.args.get("uuid"))

    if run:
        command_block = record.CommandBlock(job_uuid=run)
        record.add_and_commit(command_block)
        return jsonify({
            'uuid': command_block.uuid
        }), 201
    else:
        return jsonify({
        }), 201

@record.app.route('/api/command/get/', methods = ['GET'])
def get_command():
    try:
        cmd = record.Command.query.filter(record.Command.uuid==str(request.args.get("uuid")))[0]
    except IndexError:
        cmd = None

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


@record.app.route('/api/command/add/', methods = ['GET'])
def create_command():
    blocked_by_cmd = None
    if request.args.get('blocked_by'):
        blocked_by_cmd = util.get_command_by_uuid(request.args.get('blocked_by'))
    block = util.get_block_by_uuid(request.args.get("cmd_block"))
    return_code = request.args.get('return_code', -1)

    cmd = record.Command(request.args.get('cmd_str'), block, blocked_by=blocked_by_cmd, return_code=return_code)
    record.add_and_commit(cmd)

    if cmd:
        return jsonify({
            'uuid': cmd.uuid
        }), 201
    else:
        return jsonify({
        }), 201

@record.app.route('/api/command/queue/', methods = ['GET'])
def queue_command():
    bq = util.get_node_queue_by_name(request.args.get('node'), request.args.get('queue'))
    cmd = util.get_command_by_uuid(request.args.get('cmd_uuid'))
    if bq and cmd:
        cmd.queue = bq
        cmd.active = True
        cmd.client = request.args.get('client')
        record.db.session.commit()
        return jsonify({
            'uuid': cmd.uuid
        }), 201
    return jsonify({
    }), 201

@record.app.route('/api/command/fetch/', methods = ['GET'])
def fetch_command():
    bq = util.get_node_queue_by_name(request.args.get('node'), request.args.get('queue'))
    if bq:
        try:
            block = record.Command.query.join(record.CommandQueue).filter(record.CommandQueue.uuid == bq.uuid, record.Command.return_code == -1, record.Command.claimed == False).order_by(record.Command.position)[0]
        except IndexError:
            block = None

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
