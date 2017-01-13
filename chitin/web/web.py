from flask import render_template

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
    run = record.Run.query.get_or_404(run)
    return render_template('run.html', run=run)
