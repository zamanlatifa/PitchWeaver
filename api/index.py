import os
import sys
from urllib.parse import parse_qsl, urlencode

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend")
sys.path.insert(0, os.path.abspath(BACKEND))

from app import app as flask_app  # noqa: E402


class RestorePath:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        params = parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True)
        real = [v for k, v in params if k == "__path"]
        if real:
            environ["PATH_INFO"] = "/api/" + real[0].lstrip("/")
            environ["QUERY_STRING"] = urlencode([(k, v) for k, v in params if k != "__path"])
        return self.wsgi_app(environ, start_response)


flask_app.wsgi_app = RestorePath(flask_app.wsgi_app)
app = flask_app
