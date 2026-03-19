import importlib.metadata
import sys

APP_DIR   = "/app"
VENV_DIR  = f"{APP_DIR}/venv"
SERVICE   = "miles-challenge"


def _version():
    try:
        return importlib.metadata.version("miles-challenge")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


SERVICE_FILE = f"""\
[Unit]
Description=Miles DevOps Case Study — Gunicorn ({_version()})
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory={APP_DIR}
EnvironmentFile=-{APP_DIR}/.env
ExecStartPre={VENV_DIR}/bin/python -c "from miles_challenge.app import init_db; init_db()"
ExecStart={VENV_DIR}/bin/gunicorn -c {APP_DIR}/gunicorn.conf.py miles_challenge.app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
"""

GUNICORN_CONF = f"""\
bind        = "0.0.0.0:5000"
workers     = 2
accesslog   = "/var/log/gunicorn/access.log"
errorlog    = "/var/log/gunicorn/error.log"
loglevel    = "info"
"""


def print_service_file():
    sys.stdout.write(SERVICE_FILE)


def print_gunicorn_conf():
    sys.stdout.write(GUNICORN_CONF)