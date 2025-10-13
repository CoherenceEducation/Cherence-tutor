from vercel_wsgi import handle
from app import app as application

def handler(request, response):
    return handle(request, response, application)
