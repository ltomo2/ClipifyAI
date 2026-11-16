# Clipify AI

A local desktop application that turns long videos into vertical, captioned MP4 clips using your own computer. Built with PySide6, Whisper, Ollama and FFmpeg. No paid keys, subscriptions or mandatory cloud processing.

**Start here: [Easy Windows installation guide](INSTALL_WINDOWS.md).**

> Development status: the desktop UI and real FFmpeg rendering have been tested in Linux. Windows installation, local Whisper/Ollama inference and the owner's original 33-minute video have **not** been tested in this environment. This is a substantial working implementation ready for Windows validation, not a claim of a completed end-to-end Windows acceptance test. See [test evidence](docs/TESTING.md).

## What it does

- Reads the full source, extracts all its audio and transcribes in five-minute sections with overlapping context and actual word timestamps.
- Reuses your existing OpenAI Whisper weights. Uses PyTorch CUDA when available and retries on CPU if GPU inference fails.
- Reasons over the entire transcript through overlapping local Llama windows. Overlap exceeds the maximum clip length so boundary moments fit inside a window.
- Ranks moments with hooks, reasons and estimated potential scores. Invalid timings and near-duplicate clips are rejected.
- Optionally checks three frames from shortlisted moments with installed local Qwen3-VL. Models unload after requests to conserve memory.
- Optionally detects cuts and fades with an existing PySceneDetect installation.
- Creates actual **1080×1920, H.264/AAC MP4s**, with blurred backgrounds or conservative face-based portrait cropping.
- Burns bold captions into the picture, highlighting and slightly enlarging the active word at its actual timestamp.
- Saves projects, transcript sections, analysis windows, visual evidence, thumbnails and render settings. Reopening the same unchanged video reuses completed work.
- Offers four desktop sections: Dashboard, Projects, My Clips and Settings. My Clips contains only exports that exist on disk.
- Includes preview with a default-player fallback, source start/end adjustment, caption styling, re-rendering and MP4 copying.

## Quick start after installation

1. Double-click **run_clipify.bat**.
2. In **Settings**, click **Check setup / GPU / models**. Keep the standard Whisper and blurred-background settings for your first run.
3. In **Dashboard**, import a video. Choose clip lengths and number of exports.
4. Click **Analyse & create clips**. Keep Ollama running.
5. Review the selected moments in **Projects** and the finished files in **My Clips**.

The source file is never changed. Keep it in the same location if you want to resume or re-render.

## Existing installations

The Windows setup uses **Python 3.11** explicitly and creates `.venv` with `--system-site-packages`. It audits imports before offering to install only missing required packages. Your existing `tiny.en` and `llama3.2:3b` models are reused. No drivers, CUDA libraries, AI weights or optional packages are downloaded by normal setup.

FFmpeg and FFprobe are discovered on PATH, then in `C:\ffmpeg\bin` or `C:\ffmpeg`. The setup checker records encoders, filters, a real NVENC execution check, NVIDIA VRAM, PyTorch CUDA and the local Ollama version/model list.

## Storage

```text
ClipifyAI/
  clipify.py                    Desktop launcher
  run_clipify.bat               Everyday Windows launcher
  install_dependencies.bat     Audit and install only missing packages
  install_into_existing.bat    Back up old code, then install replacement
  check_setup.py               Read-only machine audit
  setup_visual_ai.bat          Optional checked Qwen download
  app/
    core/                      Atomic storage, job control, pipeline
    services/                  Local Ollama, media, transcription
    analysis/                  Context windows, ranking, visuals, scenes
    rendering/                 ASS captions, tracking, MP4 export
    ui/                        PySide6 interface
  Projects/                    Local analysis and checkpoints (not committed)
  Exports/                     Finished MP4s (not committed)
  Logs/                        Errors and machine audits (not committed)
  Backups/                     Recoverable old source (not committed)
  Tests/                       Automated checks and rendering fixture
```

Projects use schema version 1 with atomic JSON replacement. Unknown project schemas are preserved and skipped, rather than guessed or overwritten. Older loose analysis files are preserved by migration but are not automatically imported into the new schema.

## Honest limits

Small local language models can miss good moments or return unusable suggestions. Scores estimate potential and cannot guarantee virality. Whisper tiny.en is English-only and can mishear speech; review captions. For other languages, select an **already available** multilingual Whisper weight and language in Settings.

Face framing uses sampled OpenCV frontal-face detection, not speaker identification or object recognition. It falls back to blur for multiple faces or low confidence; it cannot guarantee that it always identifies the important subject. Caption position is adjustable, not automatically face-aware. Automatic sentence choices come from the model; final boundaries snap to word edges and may need review.

faster-whisper CPU/int8 is supported **only with an existing local CTranslate2 model directory**. OpenAI `.pt` weights cannot be reused as CTranslate2 weights. Its GPU mode is intentionally not enabled until independent inference tests establish CUDA 12/cuBLAS/cuDNN 9 compatibility. MediaPipe is not installed by default because its OpenCV variant dependency can conflict with an existing `cv2` installation.

## Privacy and sharing

Inference calls go only to `127.0.0.1:11434`, bypassing HTTP proxies. Cloud model tags and remote model paths are rejected. No analytics, video uploads or paid services are included. Normal processing uses pre-existing weights only. Optional model setup contacts the official Ollama library **only to download a model after you choose to**.

The repository excludes videos, audio, transcripts, projects, exports, backups, settings and logs. Share the private repository by inviting a collaborator in GitHub **Settings → Collaborators → Add people**. Sending its URL alone does not grant private-repository access.

## Developer checks

From the project folder, using the configured project Python:

```powershell
.venv\Scripts\python.exe -m unittest discover -s Tests -v
.venv\Scripts\python.exe -m Tests.render_smoke
```

The second command renders a real 30-second synthetic test MP4 and verifies its streams, full decoding and audio alignment. It does not call Whisper or Ollama and does not establish end-to-end AI quality.

Read [architecture and optional tooling](docs/ARCHITECTURE.md) and [testing evidence](docs/TESTING.md) for more detail.
