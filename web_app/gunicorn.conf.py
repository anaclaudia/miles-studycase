
bind = "10.10.10.15:5000"   # only listen on local network — nginx is the public face
workers = 2
accesslog = "/var/log/gunicorn/access.log"
errorlog  = "/var/log/gunicorn/error.log"
loglevel  = "info"