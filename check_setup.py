"""Read-only audit of THIS machine. Never installs packages or downloads weights."""
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from app.core.storage import ROOT, atomic_json
from app.services.media import tool
from app.services.ollama import Ollama

PACKAGES = {'openai-whisper': 'whisper', 'numpy': 'numpy', 'requests': 'requests',
    'opencv-python': 'cv2', 'PySide6': 'PySide6', 'torch': 'torch',
    'faster-whisper': 'faster_whisper', 'scenedetect': 'scenedetect', 'mediapipe': 'mediapipe'}


def command(args, timeout=20):
    try:
        r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors='replace', timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return {'ok': r.returncode == 0, 'output': r.stdout[-2_000_000:]}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'ok': False, 'output': str(e)}


def audit():
    report = {'platform': platform.platform(), 'python': sys.version, 'executable': sys.executable,
        'disk_free_gb': round(shutil.disk_usage(ROOT).free / 1024**3, 2), 'packages': {}, 'tools': {}}
    for package, module in PACKAGES.items():
        try:
            report['packages'][package] = {'version': importlib.metadata.version(package), 'import': command([sys.executable, '-c', f'import {module}; print("Import successful")'], 60)}
        except importlib.metadata.PackageNotFoundError:
            report['packages'][package] = {'version': None, 'import': {'ok': False, 'output': 'Not installed'}}
    for name in ['ffmpeg', 'ffprobe']:
        try:
            exe = tool(name)
            report['tools'][name] = {'path': exe, 'version': command([exe, '-version'])}
        except RuntimeError as e:
            report['tools'][name] = {'error': str(e)}
    try:
        ff = tool('ffmpeg')
        enc = command([ff, '-hide_banner', '-encoders'])
        filters = command([ff, '-hide_banner', '-filters'])
        report['ffmpeg_encoders'] = enc
        report['ffmpeg_filters'] = filters
        report['capabilities'] = {name: name in text for name, text in [('libx264', enc['output']), ('h264_nvenc', enc['output']), ('subtitles', filters['output']), ('boxblur', filters['output'])]}
        report['nvenc_execution'] = command([ff, '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:d=0.1', '-c:v', 'h264_nvenc', '-f', 'null', '-'])
    except RuntimeError:
        pass
    report['nvidia'] = command(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv'])
    report['torch_cuda'] = command([sys.executable, '-c', 'import torch,json; print(json.dumps({"version":torch.__version__,"cuda":torch.cuda.is_available(),"device":torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU","total_vram_bytes":torch.cuda.get_device_properties(0).total_memory if torch.cuda.is_available() else 0}))'])
    report['ollama_cli'] = command(['ollama', '--version'])
    try:
        api = Ollama()
        report['ollama_server'] = api.request('/api/version')
        report['ollama_models'] = api.models()
    except Exception as e:
        report['ollama_error'] = str(e)
    report['whisper_cached_models'] = [p.name for p in (Path.home() / '.cache' / 'whisper').glob('*.pt')]
    if importlib.util.find_spec('ctranslate2'):
        report['ctranslate2_cuda_probe'] = command([sys.executable, '-c', 'import ctranslate2; print(ctranslate2.get_supported_compute_types("cuda"))'])
    else:
        report['ctranslate2_cuda_probe'] = {'ok': False, 'output': 'Not installed; faster-whisper GPU execution unverified. Torch CUDA does not establish cuBLAS/cuDNN compatibility.'}
    report['notes'] = ['CTranslate2 requires independent model inference testing before GPU use.',
        'No models were downloaded; no packages or drivers were changed.',
        'These results describe only the machine on which this checker was run.']
    return report


if __name__ == '__main__':
    result = audit()
    target = ROOT / 'Logs' / 'setup_report.json'
    atomic_json(target, result)
    print(json.dumps(result, indent=2))
    print(f'\nSaved setup report: {target}')
