import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.server import start_server

if __name__ == "__main__":
    env_port = os.getenv("PORT") or os.getenv("BACKEND_PORT")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else (int(env_port) if env_port else settings.PORT)
    env_host = os.getenv("HOST") or os.getenv("BACKEND_HOST")
    host = env_host if env_host else settings.HOST
    start_server(host=host, port=port)