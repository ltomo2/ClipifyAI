"""Inspect and back up source before overlaying the new app. Standard library only."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import sys
import zipfile

BUNDLE = Path(__file__).resolve().parent
DEFAULT = Path.home() / 'Videos' / 'ClipifyAI'
SKIP_DIRS = {'.venv', '.git', '__pycache__', 'node_modules', 'Backups', 'Projects', 'Exports', 'Logs', '.cache'}
CODE_SUFFIXES = {'.py', '.pyw', '.bat', '.cmd', '.ps1', '.json', '.toml', '.yaml', '.yml', '.ini', '.txt', '.md', '.qss', '.ui', '.qrc', '.sqlite', '.db'}
FILES = ['install_into_existing.py', 'install_into_existing.bat', 'clipify.py', 'check_setup.py', 'install_missing.py', 'run_clipify.bat', 'install_dependencies.bat',
    'setup_visual_ai.py', 'setup_visual_ai.bat', 'requirements.txt', 'README.md', 'INSTALL_WINDOWS.md', '.gitignore', 'publish_github.bat', 'publish_github.ps1']


def files_below(folder):
    import os
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = Path(root) / name
            if path.is_symlink():
                continue
            yield path


def install(target):
    target = Path(target).resolve()
    if target == BUNDLE:
        raise ValueError('This is already the new application folder. Use install_dependencies.bat here, or choose the OLD project folder to migrate.')
    if BUNDLE.is_relative_to(target) or target.is_relative_to(BUNDLE):
        raise ValueError('Keep the downloaded replacement outside the existing project folder before migrating.')
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = target / 'Backups' / stamp
    backup.mkdir(parents=True)
    inventory = []
    # Inventory source/configuration, without reading private video content into the log.
    with zipfile.ZipFile(backup / 'previous_source.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files_below(target):
            rel = path.relative_to(target)
            item = {'path': str(rel), 'bytes': path.stat().st_size}
            if path.suffix.lower() in CODE_SUFFIXES or path.name.startswith('.') or rel.parts[0] in {'app', 'Assets', 'Tests', 'docs'}:
                archive.write(path, str(rel))
                item['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                item['backed_up'] = True
            inventory.append(item)
    (backup / 'inventory.json').write_text(json.dumps(inventory, indent=2), encoding='utf-8')
    # Verify archive before touching the old code.
    with zipfile.ZipFile(backup / 'previous_source.zip') as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Backup integrity check failed. Existing application was not changed.')
    for name in FILES:
        src = BUNDLE / name
        if src.is_file():
            shutil.copy2(src, target / name)
    for directory in ['app', 'Tests', 'docs', 'Assets']:
        src = BUNDLE / directory
        if src.is_dir():
            shutil.copytree(src, target / directory, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'generated'))
    for name in ['Projects', 'Exports', 'Logs']:
        (target / name).mkdir(exist_ok=True)
    print(f'Backup verified: {backup}')
    print(f'Application installed: {target}')
    print('Original media, analysis folders, model caches, .venv and legacy files were preserved.')
    print('Next: double-click install_dependencies.bat in the application folder.')
    return backup


if __name__ == '__main__':
    if sys.version_info[:2] != (3, 11):
        raise SystemExit('Use Python 3.11 via install_into_existing.bat.')
    try:
        text = input(f'Existing Clipify folder [Enter for {DEFAULT}]: ').strip().strip('"')
        install(Path(text) if text else DEFAULT)
    except Exception as e:
        print('Migration stopped:', e)
        raise SystemExit(1)
