from flask import render_template, Markup

from chitin import record

@record.app.route('/')
def experiment_list():
    return render_template('experiments.html', experiments=record.Experiment.query.all())

@record.app.route('/experiment/<experiment>')
def experiment_detail(experiment):
    exp = record.Experiment.query.get_or_404(experiment)
    return render_template('experiment.html', exp=exp)

@record.app.route('/run/<run>')
def run_detail(run):
    run = record.Job.query.get_or_404(run)
    return render_template('run.html', run=run)

@record.app.route('/resource/<resource>')
def resource_detail(resource):
    resource = record.Resource.query.get_or_404(resource)
    return render_template('resource.html', resource=resource)

@record.app.template_filter('chitin')
def chitin_filter(s):
    try:
        fields = s.split(" ")
        for i, f in enumerate(fields):
            if f.startswith("chitin://"):
                fields[i] = Markup("<a href='/resource/" + f.replace("chitin://", "") +"'>" + f + "</a>")
        return " ".join(fields)
    except:
        return s

