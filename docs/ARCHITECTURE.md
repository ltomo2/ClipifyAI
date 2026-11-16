# Architecture and tooling decisions

## Processing

The UI uses a background QThread to run one job at a time. FFmpeg subprocess output is file-backed, preventing pipe deadlocks or unbounded log memory. The job polls cancellation and terminates encoders safely. Transcription runs in a spawned process, so native inference can be stopped and GPU memory released without killing the desktop UI. Ollama HTTP calls use streaming, monitored from a cancellable background request. Closing the app requests cancellation and waits for the worker; it does not destroy a running thread.

The source identity includes its absolute path, size, modification time and hashes of sampled bytes from both ends. A changed or moved source creates a separate identity rather than silently reusing old timings. Source videos are read, never rewritten.

Audio is mono 16 kHz PCM, generated once via a partial file then renamed. Speech is processed in 300-second sections with two seconds of context on either side. Ownership by word midpoint and monotonic cleanup remove boundary duplicates. Successful sections are saved individually using a configuration hash. Resume can reconstruct the transcript without loading a model when every section exists.

Transcript windows have overlap longer than the configured maximum clip length, use absolute word timestamps and carry a short prior-window summary. Local Llama sees bounded requests instead of hours of text. The application validates finite values, source bounds, duration, speech presence and score bounds; aligns to nearby word edges; then applies overlap suppression. No random fallback suggestions are produced. Model output is treated as data, not executable code.

Visual inspection samples three 640-pixel frames per shortlisted candidate. Text inference finishes and unloads before Qwen is loaded. A visual-interest estimate contributes 10% of the final score on visually inspected candidates. Uninspected candidates retain text scores; this is a heuristic, not a calibrated predictor. Visual results retain model evidence. Scene-cut counts are saved as supplementary metadata, not treated as entertainment on their own.

## Export

Blur layout splits the video into a scaled/blurred background and an unstretched foreground. Smart layout samples a frontal-face detector at one-second intervals, smooths horizontal positions and applies crop commands before scaling. Multiple subjects and low detection coverage revert to blur. There is no claim of active-speaker recognition, general object tracking or perfect framing between samples.

Actual word timestamps become short ASS dialogue events with a bold phrase and one coloured, enlarged current word. Pauses remain pauses, rather than stretching highlighting over silence. ASS control characters are removed from transcript text. The user can move captions within safe vertical limits; the app does not automatically avoid faces. Font is a standard Arial request with libass fallback; size, highlight colour and position are configurable.

Each render uses an isolated work directory, relative filter filenames and argument lists without a shell. Source/output paths with spaces or Windows drive colons are kept out of filter syntax. Video/audio timestamps reset together, output is 30 fps, 1080×1920 H.264/AAC with fast-start metadata. NVENC is opt-in with CPU retry. A partial output becomes an export only after codec, audio, dimensions and duration verification. Earlier render versions remain available.

## Storage and compatibility

Version 1 JSON projects store source metadata, settings, status, selected moments and render history. Transcript words, per-section checkpoints, analysis windows, visual evidence and render filter/ASS files live in the project directory. Atomic JSON writes use flush/fsync and same-directory replacement. Legacy unknown-schema projects are preserved and skipped. There is no destructive migration of old results.

On-disk state is checkpointed after stages and each export. A sudden crash can leave an unreferenced partial/work file, but does not replace a completed MP4 or corrupt an earlier checkpoint. The app intentionally keeps old caches and render work for diagnosis; it has no automatic deletion policy. A Qt lock file prevents multiple application instances from writing the same project folder concurrently. Standalone developer scripts should also be run one at a time.

## Optional-tool investigation (2026-11-16)

Sources were retrieved during development; requirements must still be checked on the actual Windows computer.

| Tool | Findings | Decision |
|---|---|---|
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper#gpu) | Current CTranslate2 requires CUDA 12 cuBLAS and cuDNN 9. PyTorch CUDA alone does not prove compatibility. Requires CTranslate2 weights, not existing OpenAI `.pt` weights. | Support an existing local model with CPU/int8. Preserve OpenAI Whisper as the default. No model or GPU-runtime download. |
| [PySceneDetect](https://www.scenedetect.com/docs/latest/) / [package metadata](https://pypi.org/pypi/scenedetect/json) | Release metadata reported 0.7.3, depending on click, numpy, opencv-python, platformdirs and tqdm; no need for an alternate OpenCV variant. | Optional full-video ContentDetector and ThresholdDetector integration. Off by default; not installed during development. |
| [MediaPipe](https://developers.google.com/edge/mediapipe/solutions/vision/face_detector/python) / [wheel metadata](https://pypi.org/pypi/mediapipe/json) | Package metadata reported 1.2.3 with a Windows amd64 wheel; dependencies include opencv-contrib-python. A compatible Python/platform wheel alone does not establish safe coexistence with installed cv2. | Do not install over the user's working OpenCV. Use the packaged OpenCV frontal-face cascade. MediaPipe is investigated but not integrated. |
| [Qwen3-VL 2B](https://ollama.com/library/qwen3-vl) | Official library reports approximately 1.9 GB and Ollama 0.12.7 minimum. | Optional local inference integration and checked opt-in setup helper. No download in this environment. |

The production installer deliberately avoids optional bulk installs and model conversions. An optional package can be installed later into `.venv` after checking a pip dry-run for changes to NumPy, OpenCV and Torch. A maintainer should perform that review; it is not required for the default path.

## Remaining validation

Run the audit on Windows 3.11, inspect existing code/media backup, independently test actual local model inference, and run the full original-video acceptance workflow. Test real face-tracking coverage and output framing with human review. Low-resolution inputs cannot gain real detail simply by being exported at 1080×1920.
