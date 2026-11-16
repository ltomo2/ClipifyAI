# What has actually been tested

Development checks were run on **2026-11-16** in a Linux cloud workspace using **Python 3.12.14**. The requested Windows PC, original application folder and original 33-minute video were not mounted or remotely accessible. No Windows audit or original-file backup has been claimed.

## Environment used

- Reused FFmpeg/FFprobe **7.1.5** and the available NumPy installation.
- Installed testing dependencies only in a disposable `/tmp/clipify-test-deps` directory: PySide6 **6.12.0**, its Qt component packages, opencv-python **5.0.0.93**, and its NumPy dependency **2.5.5**. These installations did not alter the owner's Windows computer.
- No Ollama, Whisper weights, PyTorch, NVIDIA GPU, faster-whisper, PySceneDetect or MediaPipe were available for real inference tests.
- Downloaded **no AI models**. Changed **no drivers or CUDA components**.
- FFmpeg advertised NVENC but an actual encode failed without an NVIDIA device. This establishes why advertising an encoder is not enough; the app defaults to CPU.
- The temporary OpenCV 5 build lacked CascadeClassifier. The app now checks the backend and falls back to blur. Fresh missing-package installs request OpenCV 4.x; existing cv2 installations are not replaced.

## Automated checks

Run `python -m unittest discover -s Tests -v` from the repository folder. **14 checks passed** in the final run.

| Check | Scope |
|---|---|
| Invalid timings/scores | Reject negative, reversed, out-of-range, infinite and NaN values |
| Word-edge alignment | Snap boundaries while enforcing duration limits |
| Two-hour coverage | Every synthetic transcript second appears in at least one overlapping analysis window |
| Duplicate suppression | Stronger overlapping suggestions retained |
| ASS caption timing/sanitisation | Source-to-clip offset, active-word colour and tag injection removal |
| Atomic project storage | No partial replacement; unknown schema preserved |
| Local-only model tags | Reject cloud tags and remote-style names |
| Cancellation | Real long-running subprocess is terminated promptly |
| Analysis checkpoints | Completed windows reused without a second mocked model request |
| Backup-first migration | Real ZIP restores old source; previous video and analysis files remain byte-for-byte intact |
| Pipeline persistence | Real extraction/rendering; reopen same project without a duplicate render. **Transcription and Llama responses mocked.** |
| Tracking filter and CPU retry | Real FFmpeg crop commands and render; tracking coordinates and NVENC failure supplied as controlled fixtures |
| Framing fallback | Low-confidence tracking produces a real blurred-background MP4 |
| Missing OpenCV detector | Safe blur fallback when the installed cv2 lacks a cascade backend |

These tests do not establish the quality of real AI selection, speech recognition or face tracking.

## Actual 30-second MP4

Run `python -m Tests.render_smoke`. This creates an explicit synthetic fixture: moving test graphics, chirp audio, supplied word timestamps and captions reading “Synthetic caption timing test.” It is not represented as analysed speech or a genuine entertaining clip.

The tested export:

- Duration **30.0 seconds**; source trim **2.0–32.0 seconds**.
- Resolution **1080×1920**, square pixels, H.264 video, AAC audio, MP4 container.
- **60 burned-in word-highlight events**, with a blurred background and unstretched foreground.
- Entire output decoded successfully using FFmpeg.
- Audio compared against the decoded original at two positions, near the beginning and end. Measured lag was **0.0 seconds at both sample points**, at an 8 kHz comparison rate and a 25 ms acceptance threshold. This is a synthetic alignment check, not a human lip-sync review.
- Extracted frames were visually inspected: readable outlined text and active-word highlighting were visible in the vertical frame.

The render and its machine-readable result are retained locally in `Tests/generated/`. Test media are excluded from GitHub and source ZIPs. Anyone can regenerate them with the test command.

## Desktop checks

All four sections opened and navigated under the offscreen Qt platform. A real exported fixture populated My Clips, which only lists files present on disk.

The first native Qt multimedia test **crashed in this Linux environment** while initialising its audio/backend stack. This was fixed by running a disposable subprocess capability check before enabling embedded playback. The repeated UI check survived the subprocess failure and reported:

```text
Native preview unavailable on this machine. Use Open in default player.
```

The UI remained open and the MP4 remained intact. Actual Windows default-player launching and embedded playback still need testing on Windows. Offscreen navigation is not equivalent to a full interactive Windows usability test.

## Not yet verified

- The owner's actual Python 3.11 environment, FFmpeg 9 build, Ollama version, RTX 4060 Ti VRAM and CUDA libraries.
- Successful live Whisper transcription with the owner's existing tiny.en weights.
- Successful live Llama selection or Qwen visual inference.
- faster-whisper CPU inference, independent CTranslate2 GPU compatibility, or PySceneDetect processing.
- Face-tracking accuracy on real people and scene changes; automatic face-aware caption placement is not implemented.
- Windows batch/PowerShell installation and launcher execution.
- The complete original-video acceptance workflow, including human checks of selection quality, speech captions, source framing and lip sync.

**The original test video has not produced verified finished clips in this session.** Only synthetic rendering and controlled pipeline fixtures have. Run the Windows guide on the actual computer before describing the product as fully accepted.

## GitHub publication

Initial automated repository-creation attempts were rejected with **Resource not accessible by integration (HTTP 403)**. The owner subsequently created [the private ClipifyAI repository](https://github.com/ltomo2/ClipifyAI), which the connected account can access and update. The initial repository commit is preserved when integrating the prepared application source. Videos, analysis, models, logs, settings and backups are excluded.

To share this private repository, the owner must invite each collaborator under **Settings → Collaborators → Add people**. Sending the repository URL alone does not grant access. See [the Windows installation guide](../INSTALL_WINDOWS.md) for download and setup steps.
