from flask import render_template

from record import app, db
import record

@app.route('/')
def index():
    return render_template('index.html', events=record.Event.query.order_by('timestamp DESC').limit(10))

