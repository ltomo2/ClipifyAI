import subprocess
import tempfile
import threading
from pathlib import Path


class Cancelled(Exception):
    pass


class Job:
    def __init__(self, report=lambda stage, percent, message: None):
        self.stop = threading.Event()
        self.report = report

    def check(self):
        if self.stop.is_set():
            raise Cancelled('Cancelled safely. Completed stages have been saved.')

    def run(self, args, cwd=None):
        self.check()
        # File-backed output avoids pipe deadlocks and unbounded RAM use.
        with tempfile.TemporaryFile() as out:
            proc = subprocess.Popen([str(a) for a in args], cwd=cwd,
                stdout=out, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            try:
                while proc.poll() is None:
                    if self.stop.wait(.15):
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                        self.check()
                out.seek(0, 2)
                size = out.tell()
                out.seek(max(0, size - (16000 if proc.returncode else 1_000_000)))
                text = out.read().decode('utf-8', errors='replace')
                if proc.returncode:
                    raise RuntimeError(f'{Path(args[0]).name} failed ({proc.returncode}):\n{text}')
                return text
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
