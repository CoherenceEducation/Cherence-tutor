from vercel_wsgi import handle
from app import app as flask_app


def handler(request, response):
    return handle(request, response, flask_app)


