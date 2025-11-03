import os
from .app import create_app


def main():
    app = create_app()
    host = os.getenv("API_HOST", "0.0.0.0")
    try:
        port = int(os.getenv("API_PORT", "8000"))
    except ValueError:
        port = 8000
    debug_env = os.getenv("DEBUG", "1")
    debug = False if debug_env in ("0", "false", "False") else True
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()

