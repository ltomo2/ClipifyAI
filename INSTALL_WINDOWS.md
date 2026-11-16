# Install Clipify AI on Windows

This guide is for Windows 11 and Python 3.11. You do not need to edit code or enter a list of terminal commands.

## 1. Download the application

On this repository's GitHub page, click the green **Code** button, then **Download ZIP**. You must be signed into a GitHub account with access to this private repository.

Right-click the ZIP and choose **Extract All**. Extract it somewhere separate from your existing Clipify folder, such as Downloads. Open the extracted folder until you can see `README.md` and the `.bat` launcher files. Do not run the app from inside the ZIP.

## 2. Preserve your old Clipify project

Close any running Clipify windows first. If you already have Clipify in `C:\Users\kruz1\Videos\ClipifyAI`, double-click **install_into_existing.bat** in the newly downloaded folder.

Press **Enter** to use the usual `Videos\ClipifyAI` location for your Windows account. If your old project lives elsewhere, paste that folder path instead.

The installer inventories the old folder, makes and verifies a dated source backup under **Backups**, then copies the new application into the old folder. It preserves original videos, generated media, saved analysis folders, AI models, existing virtual environments and leftover legacy files. It does not touch the old `.claude\skills\clipify` helper folder. If backup verification fails, it stops before replacing code.

After it finishes, open your original **Videos\ClipifyAI** folder. Use that folder for the remaining steps.

**Installing on another computer without an old project?** Keep the extracted application in a convenient writable location, such as `Videos\ClipifyAI`, and skip migration. Do not use Program Files or a read-only folder.

## 3. Check your existing software

Double-click **install_dependencies.bat**.

It checks your Python 3.11 installation and creates a small project environment that can use your existing packages. It records a setup report before installing anything. If the required packages are already present, it installs nothing. If packages are missing, it lists them and asks before installing them into the project environment.

Leave the window open until it finishes. Imports of large libraries can take a little time. A report is saved in `Logs\setup_report.json`, and package lists are saved before and after setup.

This step does **not** install FFmpeg, Ollama, GPU drivers, CUDA components or AI models. It does not redownload your existing Whisper model. Missing PyTorch on a fresh computer may require a large download; the setup prompt tells you before proceeding. New installations of PyTorch may be CPU-only: GPU availability is checked rather than assumed.

If Windows displays a downloaded-file warning, inspect the script first and only run it if you trust the source. If your computer's policy blocks scripts, ask the person maintaining the computer to review it.

## 4. Open the app

Double-click **run_clipify.bat**.

In **Settings**, click **Check setup / GPU / models**. The report shows the actual NVIDIA card and VRAM if available, FFmpeg and FFprobe, package import results, Ollama version, installed model tags, cached Whisper weights and processing capabilities.

For your first run, keep:

- Transcript model: `llama3.2:3b`
- Transcription engine: Existing OpenAI Whisper
- Whisper weight: `tiny.en`
- Language: `en`
- Video layout: Blurred background
- Export encoder: CPU H.264
- Visual analysis and scene detection: off

The app requires local Ollama to be running with `llama3.2:3b` already installed. Open **Ollama** from the Windows Start menu if it is not running. The app will explain if a model or Whisper weight is missing; it will not secretly download it.

## 5. Create your first clips

Open **Dashboard**, click **Import video**, and choose your long video. For the existing test, choose the `guess-the-language-vs-world-expert-ytmp4.savetube.vip.mp4` file in Downloads if it is still there.

Keep **30–60 seconds** and start with **3 clips**. Click **Analyse & create clips**. The full video is processed; several hours of footage can take considerable time on a small local model. The app stays responsive and reports the current stage.

Use **Cancel job** if necessary. Completed sections and analysis windows are saved. To resume, import the same unchanged video again, or select it in Projects and use **Resume selected project**. Changing transcription/model settings may require new analysis; old caches are kept.

Open **My Clips** when processing finishes. Select a finished MP4 and click **Play / pause**. If playback is blank or unavailable, click **Open in default player**. **Open folder** reveals the real MP4 file. **Copy MP4…** saves a copy wherever you choose.

In **Projects**, select a moment to read its score, hook and reason. Adjust its source start/end in seconds, choose caption size/colour/position in Settings or layout in Dashboard, then click **Render / regenerate captions**. Each render makes a new MP4 and preserves the previous version.

## Optional visual AI

Once ordinary clipping works, double-click **setup_visual_ai.bat**.

It checks the **local** Ollama server version (must be 0.12.7 or newer), verifies free space near model storage and skips downloading if `qwen3-vl:2b` already exists. It explains the approximately **1.9 GB** download and asks before proceeding. It never deletes Llama or Whisper, changes drivers, or uploads your videos. If Ollama uses a custom server-side model location, verify space on that location too; the helper can only inspect the current Windows user's configured model location.

After setup succeeds, enable **Use installed Qwen3-VL on shortlisted frames** in Settings. Only a few frames from shortlisted moments are analysed. Transcript processing and vision run in sequence to reduce memory pressure.

## If something goes wrong

| What you see | What to do |
|---|---|
| Python 3.11 not found | Install Python 3.11 from python.org with the Windows Python launcher, then rerun setup. Do not uninstall other Python versions. |
| A required module is missing | Run `install_dependencies.bat` again. It checks existing modules first. |
| Ollama unavailable | Open the Ollama application, then run the setup check again. |
| Llama or Whisper model missing | Confirm you are signed into the same Windows account used for your working installation. Model caches belong to that account. Share `Logs\setup_report.json` with your developer if it still fails. |
| FFmpeg / FFprobe missing | Confirm both executables are in your existing `C:\ffmpeg\bin` or `C:\ffmpeg`, or on PATH. Restart Clipify after a PATH correction. |
| NVENC or GPU unavailable | Keep CPU processing and CPU H.264. Your project still supports those fallbacks. |
| No valid moments found | Broaden clip length limits or use another installed local transcript model. Small models sometimes produce invalid or weak suggestions. The app preserves the transcript and does not substitute random clips. |
| Preview will not play | Use **Open in default player**. The exported MP4 is independent of Qt preview. |
| Source video moved or changed | Put it back, or import its new location as a new project. Old results and exports remain saved. |
| Low disk space | Free space in the project and export drives. Keep your source, models and backup files safe. |
| Another error | Open `Logs\clipify.log`. Share the error text and the setup report with your developer. Review reports before sharing: they can contain local file paths. |

## Share this private repository

Sign into GitHub as the repository owner. Open the repository, choose **Settings → Collaborators → Add people**, enter the person's GitHub username, and send the invitation. After they accept, send them the repository link. They can read this guide and download the code. Their computer needs its own local dependencies and models; your private videos and model files are not included.

## Restore your previous code

Close Clipify. Find the dated folder inside **Backups** and open `previous_source.zip`. Extract it into a separate recovery folder first so you can inspect the old files. Copy the needed source files back only after checking them. Existing exports and original videos do not need restoration because migration does not delete them.
