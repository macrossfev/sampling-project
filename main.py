import subprocess
import sys

if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "gunicorn",
        "backend.app:app",
        "-w", "1",
        "-k", "uvicorn.workers.UvicornWorker",
        "-b", "0.0.0.0:5002",
        "--timeout", "120",
        "--access-logfile", "-",
    ])
