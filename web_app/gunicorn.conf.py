
bind = "127.0.0.1:5000"   # only listen on localhost — nginx is the public face
workers = 2
accesslog = "/var/log/gunicorn/access.log"
errorlog  = "/var/log/gunicorn/error.log"
loglevel  = "info"