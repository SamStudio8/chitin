from flask import Flask

from chitin import conf

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////' + conf.DATABASE_PATH
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
