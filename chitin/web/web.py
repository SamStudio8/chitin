from flask import render_template

from chitin import record

@record.app.route('/')
def index():
    return render_template('index.html', events=record.Event.query.order_by('timestamp DESC').limit(10))
