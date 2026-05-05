# asgi.py
from asgiref.wsgi import WsgiToAsgi
from wsgi import app as flask_app  # ajuste o import para onde seu Flask app existe

app = WsgiToAsgi(flask_app)