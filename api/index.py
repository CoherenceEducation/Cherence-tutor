from app import app as application

def handler(request, response):
    return application(request.environ, lambda *args: None)
