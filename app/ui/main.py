from pathlib import Path
import json
import logging
from PySide6.QtCore import Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QColor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QListWidget, QStackedWidget, QFileDialog, QSpinBox, QDoubleSpinBox,
    QComboBox, QFormLayout, QProgressBar, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QLineEdit, QCheckBox, QColorDialog, QSplitter)
from app.core.storage import ROOT, settings, atomic_json, projects, Project
from app.core.jobs import Job, Cancelled
from app.core.pipeline import run_pipeline, rerender

STYLE = '''
QWidget { background: #18191F; color: #ECECF5; font-family: "Segoe UI", Arial; font-size: 14px; }
QMainWindow { background: #18191F; }
QListWidget { background: #20212A; border: none; padding: 14px; font-size: 17px; }
QListWidget::item { padding: 18px 12px; border-radius: 8px; margin-bottom: 8px; }
QListWidget::item:selected { background: #574074; color: white; }
QPushButton { background: #8155C9; color: white; border: none; border-radius: 7px; padding: 10px 17px; }
QPushButton:hover { background: #976BDD; }
QPushButton:disabled { background: #38333F; color: #97919F; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit { background: #242630; border: 1px solid #40424F; border-radius: 5px; padding: 6px; }
QTableWidget { background: #20212A; border: 1px solid #363842; gridline-color: #363842; }
QHeaderView::section { background: #30313E; color: #DDD; padding: 8px; border: none; }
QProgressBar { background: #30313A; border: none; border-radius: 6px; text-align: center; min-height: 22px; }
QProgressBar::chunk { background: #9561D9; border-radius: 6px; }
QLabel#title { font-size: 27px; font-weight: 700; padding-bottom: 8px; }
QLabel#muted { color: #B5B4C6; }
'''


class Worker(QThread):
    progress = Signal(str, int, str)
    result = Signal(object)
    failure = Signal(str)

    def __init__(self, action, parent):
        super().__init__(parent)
        self.job = Job(lambda s, n, m: self.progress.emit(s, n, m))
        self.action = action

    def run(self):
        try:
            self.result.emit(self.action(self.job))
        except Exception as e:
            logging.exception('Background operation stopped')
            self.failure.emit(str(e))


def button(text, action):
    b = QPushButton(text)
    b.clicked.connect(action)
    return b


def number(low, high, value, fractional=False):
    w = QDoubleSpinBox() if fractional else QSpinBox()
    w.setRange(low, high)
    if fractional:
        w.setDecimals(2)
        w.setSingleStep(.1)
    w.setValue(value)
    return w


def heading(layout, title, description):
    label = QLabel(title)
    label.setObjectName('title')
    layout.addWidget(label)
    label = QLabel(description)
    label.setWordWrap(True)
    label.setObjectName('muted')
    layout.addWidget(label)


def table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    return t


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Clipify AI · Local video clipping')
        self.resize(1360, 940)
        self.setMinimumSize(1050, 760)
        self.options = settings()
        self.source = ''
        self.current_project = None
        self.edit_candidate = None
        self.clip_path = ''
        self.worker = None
        self.closing = False
        self.player = None
        self.preview_capable = None
        self.busy_buttons = []
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setFixedWidth(215)
        self.nav.addItems(['Dashboard', 'Projects', 'My Clips', 'Settings'])
        root.addWidget(self.nav)
        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(28, 22, 28, 18)
        self.pages = QStackedWidget()
        column.addWidget(self.pages)
        self.stage = QLabel('Ready · Import a video to begin')
        self.stage.setWordWrap(True)
        self.progress = QProgressBar()
        column.addWidget(self.stage)
        column.addWidget(self.progress)
        root.addWidget(right, 1)
        self.make_dashboard()
        self.make_projects()
        self.make_clips()
        self.make_settings()
        self.nav.currentRowChanged.connect(self.navigate)
        self.nav.setCurrentRow(0)
        self.refresh()

    def add_page(self):
        page = QWidget()
        self.pages.addWidget(page)
        return QVBoxLayout(page)

    def guard(self, title, action):
        try:
            return action()
        except Exception as e:
            QMessageBox.warning(self, title, str(e))

    def make_dashboard(self):
        layout = self.add_page()
        heading(layout, 'Turn long videos into short stories.', 'Local AI finds moments. You review the results. Finished captioned MP4s appear in My Clips.')
        self.import_button = button('Import video', self.import_video)
        self.busy_buttons.append(self.import_button)
        layout.addWidget(self.import_button)
        self.source_label = QLabel('No video selected')
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)
        form = QFormLayout()
        self.minimum = number(5, 180, self.options['min_duration'])
        self.maximum = number(5, 180, self.options['max_duration'])
        self.count = number(1, 30, self.options['count'])
        self.layout_choice = QComboBox()
        self.layout_choice.addItem('Blurred background · preserves the full picture', 'blur')
        self.layout_choice.addItem('Automatic face reframing · blur fallback', 'auto')
        self.layout_choice.setCurrentIndex(max(0, self.layout_choice.findData(self.options['layout'])))
        form.addRow('Minimum clip length (seconds)', self.minimum)
        form.addRow('Maximum clip length (seconds)', self.maximum)
        form.addRow('Maximum clips to render', self.count)
        form.addRow('Video layout', self.layout_choice)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.start_button = button('Analyse & create clips', self.start_analysis)
        self.cancel_button = button('Cancel job', self.cancel)
        self.cancel_button.setEnabled(False)
        self.busy_buttons.append(self.start_button)
        row.addWidget(self.start_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setPlaceholderText('Progress and helpful error messages will appear here.\nExisting projects resume saved work when you import the same unchanged source.')
        layout.addWidget(self.messages, 1)

    def import_video(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Import source video', '', 'Videos (*.mp4 *.mkv *.mov *.avi *.webm *.m4v);;All files (*)')
        if path:
            self.source = path
            self.source_label.setText(path)
            from app.services.media import probe
            self.start_work(lambda job: probe(path, job), self.show_media)

    def show_media(self, info):
        self.source_label.setText(f'{self.source}\n{info["duration"] / 60:.1f} minutes · {info["width"]} × {info["height"]} · {info["video_codec"]} · audio {"present" if info["audio"] else "missing"}')

    def get_options(self):
        o = dict(self.options)
        o.update(min_duration=self.minimum.value(), max_duration=self.maximum.value(), count=self.count.value(), layout=self.layout_choice.currentData(),
            font_size=self.font_size.value(), caption_y=self.caption_y.value(), highlight=self.highlight,
            language=self.language.text().strip(), whisper_model=self.whisper_model.text().strip(),
            transcriber=self.transcriber.currentData(), device=self.device.currentData(),
            faster_model_path=self.faster_path.text().strip(), exports=self.export_path.text().strip(),
            text_model=self.text_model.text().strip(), vision_model=self.vision_model.text().strip(), visual=self.visual.isChecked(), use_scenes=self.use_scenes.isChecked(), encoder=self.encoder.currentData())
        if not o['exports']:
            raise ValueError('Choose an export folder in Settings.')
        if o['min_duration'] > o['max_duration']:
            raise ValueError('Minimum duration must be no greater than maximum duration.')
        return o

    def start_analysis(self):
        if not self.source:
            QMessageBox.information(self, 'Import a video', 'Choose Import video first.')
            return
        def start():
            options = self.get_options()
            source = self.source
            self.start_work(lambda job: run_pipeline(source, options, job), self.completed_project)
        self.guard('Check settings', start)

    def start_work(self, action, success):
        if self.worker and self.worker.isRunning():
            return
        self.worker = Worker(action, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.result.connect(success)
        self.worker.failure.connect(self.failed)
        self.worker.finished.connect(self.finished)
        for b in self.busy_buttons:
            b.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setValue(0)
        self.stage.setText('Working…')
        self.worker.start()

    def on_progress(self, stage, value, message):
        self.stage.setText(f'{stage} · {message}')
        self.progress.setValue(value)
        self.messages.appendPlainText(f'{stage}: {message}')

    def cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.job.stop.set()
            self.stage.setText('Cancellation requested · waiting for the current model call to return; completed work is saved.')
            self.cancel_button.setEnabled(False)

    def failed(self, message):
        self.stage.setText('Job stopped · saved work can be resumed')
        self.messages.appendPlainText(message)
        if not self.closing:
            QMessageBox.warning(self, 'Clipify stopped this job', message)

    def finished(self):
        for b in self.busy_buttons:
            b.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.refresh()
        if self.closing:
            self.close()

    def completed_project(self, folder):
        self.current_project = Project(folder)
        self.load_project(self.current_project)
        self.nav.setCurrentRow(1)

    def make_projects(self):
        layout = self.add_page()
        heading(layout, 'Your projects', 'Reopen saved analysis, inspect why moments were chosen, and adjust a clip before rendering.')
        self.project_table = table(['Project / source', 'Analysed', 'Suggestions', 'Exports', 'Status'])
        self.project_table.itemSelectionChanged.connect(self.select_project)
        layout.addWidget(self.project_table, 1)
        self.candidate_table = table(['Potential / 100', 'Hook', 'Source seconds', 'Reason'])
        self.candidate_table.itemSelectionChanged.connect(self.select_candidate)
        layout.addWidget(self.candidate_table, 1)
        self.reason = QLabel('Select a project, then a moment to edit.')
        self.reason.setWordWrap(True)
        layout.addWidget(self.reason)
        editor = QHBoxLayout()
        self.edit_start = number(0, 360000, 0, True)
        self.edit_end = number(0, 360000, 30, True)
        editor.addWidget(QLabel('Start (seconds)'))
        editor.addWidget(self.edit_start)
        editor.addWidget(QLabel('End (seconds)'))
        editor.addWidget(self.edit_end)
        self.rerender_button = button('Render / regenerate captions', self.render_edit)
        self.busy_buttons.append(self.rerender_button)
        editor.addWidget(self.rerender_button)
        layout.addLayout(editor)
        self.resume_button = button('Resume selected project with current settings', self.resume)
        self.busy_buttons.append(self.resume_button)
        layout.addWidget(self.resume_button)
        layout.addWidget(QLabel('Render uses the layout on Dashboard and caption styling in Settings. Previous exports are preserved.'))

    def refresh(self):
        self.project_list = projects()
        self.project_table.blockSignals(True)
        self.project_table.setRowCount(len(self.project_list))
        for i, p in enumerate(self.project_list):
            d = p.data
            for j, text in enumerate([d['name'] + '\n' + d['source'], d['created'], len(d['candidates']), len(d['renders']), d['status']]):
                self.project_table.setItem(i, j, QTableWidgetItem(str(text)))
        self.project_table.blockSignals(False)
        self.render_list = [(p, r) for p in self.project_list for r in p.data['renders'] if Path(r['path']).is_file() and not r['path'].endswith('.partial.mp4')]
        self.clips_table.blockSignals(True)
        self.clips_table.setRowCount(len(self.render_list))
        for i, (p, r) in enumerate(self.render_list):
            for j, text in enumerate([r['hook'], r['score'], f'{r["start"]:.2f}–{r["end"]:.2f}', r['captions'], r['path']]):
                self.clips_table.setItem(i, j, QTableWidgetItem(str(text)))
        self.clips_table.blockSignals(False)

    def select_project(self):
        row = self.project_table.currentRow()
        if 0 <= row < len(self.project_list):
            self.load_project(self.project_list[row])

    def load_project(self, project):
        self.current_project = project
        self.edit_candidate = None
        self.candidate_table.blockSignals(True)
        self.candidate_table.setRowCount(len(project.data['candidates']))
        for i, c in enumerate(project.data['candidates']):
            for j, text in enumerate([c['score'], c['hook'], f'{c["start"]:.2f}–{c["end"]:.2f}', c['reason']]):
                self.candidate_table.setItem(i, j, QTableWidgetItem(str(text)))
        self.candidate_table.blockSignals(False)
        self.reason.setText(f'{project.data["name"]} · {project.data["status"]}. Scores estimate potential, not guaranteed virality.')

    def select_candidate(self):
        row = self.candidate_table.currentRow()
        if self.current_project and 0 <= row < len(self.current_project.data['candidates']):
            c = self.current_project.data['candidates'][row]
            self.edit_candidate = dict(c)
            self.edit_start.setValue(c['start'])
            self.edit_end.setValue(c['end'])
            self.reason.setText(c['reason'] + ('\nVisual evidence: ' + str(c['visual'].get('description', '')) if 'visual' in c else ''))

    def resume(self):
        if not self.current_project:
            QMessageBox.information(self, 'Choose a project', 'Select a project from the table first.')
            return
        if self.current_project:
            self.source = self.current_project.data['source']
            self.source_label.setText(self.source)
            self.start_analysis()

    def render_edit(self):
        if not self.current_project or not self.edit_candidate:
            QMessageBox.information(self, 'Choose a moment', 'Select a project and a suggested moment first.')
            return
        def start():
            candidate = dict(self.edit_candidate, start=self.edit_start.value(), end=self.edit_end.value())
            options = self.get_options()
            folder = self.current_project.folder
            self.start_work(lambda job: rerender(folder, candidate, options, job), self.completed_project)
        self.guard('Check render settings', start)

    def make_clips(self):
        layout = self.add_page()
        heading(layout, 'Finished clips', 'Only MP4 files that exist on disk appear here. Select one to preview, copy, or adjust its source boundaries.')
        self.clips_table = table(['Clip', 'Potential', 'Source seconds', 'Captions', 'File'])
        self.clips_table.itemSelectionChanged.connect(self.select_clip)
        layout.addWidget(self.clips_table, 1)
        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_container.setMinimumHeight(170)
        self.preview_container.setMaximumHeight(290)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.addWidget(QLabel('Select an export to preview. The system player is always available.'))
        layout.addWidget(self.preview_container, 1)
        row = QHBoxLayout()
        for title, action in [('Play / pause', self.play_pause), ('Open in default player', self.open_clip), ('Open folder', self.open_clip_folder), ('Copy MP4…', self.copy_clip), ('Adjust / render again', self.edit_clip)]:
            b = button(title, action)
            row.addWidget(b)
            self.busy_buttons.append(b)
        layout.addLayout(row)

    def select_clip(self):
        row = self.clips_table.currentRow()
        if not 0 <= row < len(self.render_list):
            return
        p, r = self.render_list[row]
        self.clip_path = r['path']
        if self.preview_capable is None:
            if self.worker and self.worker.isRunning():
                return
            import sys
            path = self.clip_path
            def probe(job):
                try:
                    job.run([sys.executable, ROOT / 'app' / 'services' / 'playback_probe.py', path])
                    return True
                except RuntimeError:
                    return False
            self.start_work(probe, self.preview_checked)
            return
        if self.preview_capable:
            self.load_preview()

    def preview_checked(self, capable):
        self.preview_capable = capable
        if capable:
            self.load_preview()
            self.stage.setText('Preview ready. Use Play / pause to view the clip.')
        else:
            self.stage.setText('Native preview unavailable on this machine. Use Open in default player.')

    def load_preview(self):
        if self.player is None:
            try:
                from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
                from PySide6.QtMultimediaWidgets import QVideoWidget
                while self.preview_layout.count():
                    item = self.preview_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                self.video = QVideoWidget()
                self.preview_layout.addWidget(self.video)
                self.audio = QAudioOutput(self)
                self.player = QMediaPlayer(self)
                self.player.setAudioOutput(self.audio)
                self.player.setVideoOutput(self.video)
                self.player.errorOccurred.connect(lambda *args: self.stage.setText('Preview unavailable here. Use Open in default player.'))
            except ImportError:
                self.stage.setText('Qt playback is unavailable. Use Open in default player.')
                return
        self.player.setSource(QUrl.fromLocalFile(self.clip_path))

    def play_pause(self):
        if self.player and self.clip_path:
            from PySide6.QtMultimedia import QMediaPlayer
            self.player.pause() if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState else self.player.play()
        else:
            self.open_clip()

    def open_path(self, path):
        if path and Path(path).exists():
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))):
                QMessageBox.warning(self, 'Could not open', str(path))

    def open_clip(self):
        if not self.clip_path:
            QMessageBox.information(self, 'Choose a clip', 'Select a finished MP4 from the table first.')
            return
        self.open_path(self.clip_path)

    def open_clip_folder(self):
        if not self.clip_path:
            QMessageBox.information(self, 'Choose a clip', 'Select a finished MP4 from the table first.')
            return
        if self.clip_path:
            self.open_path(Path(self.clip_path).parent)

    def copy_clip(self):
        if not self.clip_path:
            QMessageBox.information(self, 'Choose a clip', 'Select a finished MP4 from the table first.')
            return
        target, _ = QFileDialog.getSaveFileName(self, 'Copy finished MP4', Path(self.clip_path).name, 'MP4 video (*.mp4)')
        if target:
            import shutil
            self.guard('Copy export', lambda: shutil.copy2(self.clip_path, target))

    def edit_clip(self):
        row = self.clips_table.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Choose a clip', 'Select a finished MP4 from the table first.')
            return
        if 0 <= row < len(self.render_list):
            p, r = self.render_list[row]
            self.load_project(p)
            self.edit_candidate = {k: r[k] for k in ['start','end','score','hook','reason']}
            self.edit_candidate['id'] = r['candidate_id']
            self.edit_start.setValue(r['start'])
            self.edit_end.setValue(r['end'])
            self.nav.setCurrentRow(1)
            self.reason.setText('Editing export: ' + r['hook'])

    def make_settings(self):
        layout = self.add_page()
        heading(layout, 'Local processing settings', 'No API keys. Ollama requests go only to 127.0.0.1. Existing model weights are reused; the app never downloads models.')
        form = QFormLayout()
        o = self.options
        self.text_model = QLineEdit(o['text_model'])
        self.vision_model = QLineEdit(o['vision_model'])
        self.visual = QCheckBox('Use installed Qwen3-VL on shortlisted frames')
        self.visual.setChecked(o['visual'])
        self.use_scenes = QCheckBox('Scan cuts and fades with installed PySceneDetect')
        self.use_scenes.setChecked(o.get('use_scenes', False))
        self.language = QLineEdit(o['language'])
        self.whisper_model = QLineEdit(o['whisper_model'])
        self.transcriber = QComboBox()
        self.transcriber.addItem('Existing OpenAI Whisper', 'whisper')
        self.transcriber.addItem('faster-whisper · local model, CPU/int8', 'faster')
        self.transcriber.setCurrentIndex(max(0, self.transcriber.findData(o['transcriber'])))
        self.faster_path = QLineEdit(o['faster_model_path'])
        self.device = QComboBox()
        self.device.addItem('Automatic · PyTorch CUDA with CPU fallback', 'auto')
        self.device.addItem('CPU', 'cpu')
        self.device.setCurrentIndex(max(0, self.device.findData(o['device'])))
        self.encoder = QComboBox()
        self.encoder.addItem('CPU H.264 · reliable default', 'libx264')
        self.encoder.addItem('NVIDIA NVENC · CPU retry if unavailable', 'h264_nvenc')
        self.encoder.setCurrentIndex(max(0, self.encoder.findData(o['encoder'])))
        self.font_size = number(28, 110, o['font_size'])
        self.caption_y = number(250, 1580, o['caption_y'])
        self.highlight = o['highlight']
        self.colour_button = button('Choose highlight colour', self.choose_colour)
        self.export_path = QLineEdit(o['exports'])
        exports_row = QHBoxLayout()
        exports_row.addWidget(self.export_path)
        exports_row.addWidget(button('Browse…', self.browse_exports))
        for title, widget in [('Transcript model tag', self.text_model), ('Vision model tag', self.vision_model), ('Visual analysis', self.visual), ('Scene detection', self.use_scenes),
            ('Transcription engine', self.transcriber), ('Whisper weight name', self.whisper_model), ('faster-whisper model folder', self.faster_path),
            ('Language (blank = detect)', self.language), ('Speech processing', self.device), ('Export encoder', self.encoder),
            ('Caption font size', self.font_size), ('Caption vertical position', self.caption_y), ('Active word colour', self.colour_button)]:
            form.addRow(title, widget)
        form.addRow('Export folder', exports_row)
        layout.addLayout(form)
        layout.addWidget(QLabel('Projects: ' + str(ROOT / 'Projects')))
        row = QHBoxLayout()
        row.addWidget(button('Save defaults', self.save_settings))
        self.audit_button = button('Check setup / GPU / models', self.run_audit)
        self.busy_buttons.append(self.audit_button)
        row.addWidget(self.audit_button)
        row.addWidget(button('Open project folder', lambda: self.open_path(ROOT / 'Projects')))
        row.addWidget(button('Installation guide', lambda: self.open_path(ROOT / 'INSTALL_WINDOWS.md')))
        layout.addLayout(row)
        self.audit_text = QPlainTextEdit()
        self.audit_text.setReadOnly(True)
        self.audit_text.setPlaceholderText('Click Check setup to inspect this machine, available models, FFmpeg, GPU VRAM and imports. This does not install anything.')
        layout.addWidget(self.audit_text, 1)

    def choose_colour(self):
        c = QColorDialog.getColor(QColor(self.highlight), self, 'Active word colour')
        if c.isValid():
            self.highlight = c.name()
            self.colour_button.setText('Highlight: ' + c.name())

    def browse_exports(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose export folder', self.export_path.text())
        if path:
            self.export_path.setText(path)

    def save_settings(self):
        def save():
            self.options = self.get_options()
            atomic_json(ROOT / 'settings.json', self.options)
            self.stage.setText('Defaults saved. Existing exports are preserved.')
        self.guard('Settings', save)

    def run_audit(self):
        from check_setup import audit
        self.start_work(lambda job: audit(), self.audit_done)

    def audit_done(self, report):
        atomic_json(ROOT / 'Logs' / 'setup_report.json', report)
        required = ['openai-whisper', 'numpy', 'requests', 'opencv-python', 'PySide6', 'torch']
        missing = [name for name in required if not report['packages'][name]['import']['ok']]
        lines = ['SETUP SUMMARY', 'Python: ' + report['python'].splitlines()[0],
            'Required packages: ' + ('READY' if not missing else 'NEEDS ATTENTION: ' + ', '.join(missing)),
            'FFmpeg: ' + ('READY' if 'path' in report['tools'].get('ffmpeg', {}) else 'MISSING'),
            'FFprobe: ' + ('READY' if 'path' in report['tools'].get('ffprobe', {}) else 'MISSING'),
            'H.264 / caption filters: ' + str(report.get('capabilities', {})),
            'Ollama: ' + (str(report.get('ollama_server', {}).get('version', '')) if 'ollama_server' in report else report.get('ollama_error', 'unavailable')),
            'Local models: ' + (', '.join(report.get('ollama_models', [])) or 'none found'),
            'Whisper weights: ' + (', '.join(report['whisper_cached_models']) or 'none found in this account cache'),
            'NVIDIA / actual VRAM: ' + report['nvidia']['output'].strip(),
            'PyTorch GPU check: ' + report['torch_cuda']['output'].strip(),
            'NVENC execution: ' + ('READY' if report.get('nvenc_execution', {}).get('ok') else 'Unavailable; CPU H.264 remains supported'),
            'Optional faster-whisper: ' + str(report['packages']['faster-whisper']['version']),
            'Optional PySceneDetect: ' + str(report['packages']['scenedetect']['version']),
            'Free space on project drive: ' + str(report['disk_free_gb']) + ' GB',
            '', 'Detailed diagnostic evidence:', json.dumps(report, indent=2)]
        self.audit_text.setPlainText('\n'.join(lines))
        self.stage.setText('Setup checked. Read the summary below; no software or models were installed.')

    def navigate(self, row):
        self.pages.setCurrentIndex(row)
        if row in (1, 2):
            self.refresh()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.closing = True
            self.cancel()
            event.ignore()
            return
        if self.player:
            self.player.stop()
        event.accept()
