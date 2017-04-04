"""
WSGI config for sunblock project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os
import sys

sys.path.append('/home/cake/public/chitin/chitin')
from chitin.record import app as application
from chitin.web import web
