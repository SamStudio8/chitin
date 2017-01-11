from flask import render_template

from chitin import record

@record.app.route('/')
def index():
    return render_template('index.html', events=record.Event.query.order_by('timestamp DESC').limit(10))

@record.app.route('/experiments')
def experiment_list():
    return render_template('experiments.html', experiments=record.Experiment.query.all())

@record.app.route('/runs/<experiment>')
def experiment_detail(experiment):
    exp = record.Experiment.query.get_or_404(experiment)
    return render_template('experiment.html', exp=exp)
