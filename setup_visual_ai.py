"""Optional Qwen setup: local Ollama only, version/storage checks, explicit download choice."""
import os
from pathlib import Path
import re
import shutil
import subprocess
from app.services.ollama import Ollama


def main():
    api = Ollama()
    version = api.request('/api/version')['version']
    match = re.match(r'(\d+)\.(\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (0, 12, 7):
        raise RuntimeError(f'Ollama {version} is not confirmed compatible. Qwen3-VL requires 0.12.7 or newer. Update Ollama through its official installer yourself; no driver changes are needed here.')
    tag = 'qwen3-vl:2b'
    if tag in api.models():
        print('Qwen3-VL 2B already exists. Nothing downloaded.')
        return
    model_dir = Path(os.environ.get('OLLAMA_MODELS', Path.home() / '.ollama' / 'models'))
    parent = model_dir
    while not parent.exists() and parent.parent != parent:
        parent = parent.parent
    free = shutil.disk_usage(parent).free / 1024**3
    print(f'Local Ollama server: {version}. Free space near model storage: {free:.1f} GB.')
    if free < 5:
        raise RuntimeError('Please free at least 5 GB near the Ollama model storage before this optional download.')
    print('This optional download adds qwen3-vl:2b (about 1.9 GB) for checking selected frames.')
    print('Your Llama and Whisper models will be kept. Videos are not uploaded.')
    if input('Download this one model from the official Ollama library now? [y/N] ').lower() != 'y':
        print('Skipped. Transcript analysis and MP4 rendering work without vision AI.')
        return
    executable = shutil.which('ollama')
    if not executable:
        raise RuntimeError('Ollama CLI was not found on PATH. Existing models were preserved.')
    env = dict(os.environ, OLLAMA_HOST='127.0.0.1:11434')
    subprocess.check_call([executable, 'pull', tag], env=env)
    api.require(tag)
    print('Verified local model. Enable visual analysis in Clipify Settings when you want it.')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('Optional visual setup stopped:', e)
        raise SystemExit(1)
