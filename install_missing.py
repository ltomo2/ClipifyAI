"""Install only absent required modules into a system-site-packages project venv."""
import importlib.util
import subprocess
import sys
from pathlib import Path

REQUIRED = {'numpy': 'numpy', 'requests': 'requests', 'cv2': 'opencv-python>=4.8,<5',
    'PySide6': 'PySide6', 'torch': 'torch', 'whisper': 'openai-whisper'}


def main():
    if sys.version_info[:2] != (3, 11):
        raise SystemExit('Please use Python 3.11. Run install_dependencies.bat.')
    if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != (Path(__file__).resolve().parent / '.venv').resolve():
        raise SystemExit('Installation is allowed only inside this project’s .venv.')
    missing = [package for module, package in REQUIRED.items() if importlib.util.find_spec(module) is None]
    if not missing:
        print('All required modules already available. Nothing was installed.')
        return
    print('Missing packages:', ', '.join(missing))
    if 'torch' in missing:
        print('PyTorch is missing here. Its default download can be large and does not ensure NVIDIA acceleration.')
    answer = input('Install only these missing packages into the project environment? [y/N] ')
    if answer.lower() != 'y':
        raise SystemExit('Installation skipped. Existing installations unchanged.')
    for package in missing:
        # One at a time so that Whisper's dependencies are noticed before installing another package.
        module = next(k for k, v in REQUIRED.items() if v == package)
        if importlib.util.find_spec(module) is None:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
    print('Missing-package installation finished. No optional models were downloaded.')


if __name__ == '__main__':
    main()
