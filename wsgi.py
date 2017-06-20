import os
import sys

sys.path.append('/home/cake/public/chitin2/chitin')

from chitin.core.database import db
from chitin.core.server import app
from chitin.core import models

db.init_app(app)
with app.app_context():
    db.create_all()

from chitin.core import routes

application = app