from flask import render_template, Markup, Response, redirect, url_for, request, abort

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
    current_queue = record.Command.query.filter(record.Command.return_code == -1)
    return render_template('live.html', current_queue=current_queue)

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

