from .app import create_app

# WSGI entrypoint for production servers (gunicorn/uwsgi)
app = create_app()

