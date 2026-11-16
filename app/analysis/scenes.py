"""Optional full-video cuts/fades detection without installing another cv2 variant."""
from app.core.storage import atomic_json, read_json


def detect(project, job):
    cache = project.folder / 'scenes.json'
    if cache.exists():
        return read_json(cache)
    try:
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector, ThresholdDetector
    except ImportError as e:
        raise RuntimeError('Scene analysis was enabled, but PySceneDetect is missing. Turn it off in Settings or install the optional package in the project venv.') from e
    video = open_video(project.data['source'])
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27))
    manager.add_detector(ThresholdDetector(threshold=12))
    job.report('Analysing content', 48, 'Scanning the entire video for cuts and fades…')
    try:
        manager.detect_scenes(video=video, show_progress=False, callback=lambda *args: job.check())
        job.check()
        cuts = [{'start': a.get_seconds(), 'end': b.get_seconds()} for a, b in manager.get_scene_list(start_in_scene=True)]
        result = {'scenes': cuts, 'method': 'PySceneDetect content and threshold detectors'}
        atomic_json(cache, result)
        return result
    finally:
        # VideoStreamCv2 does not expose a public close method on every release.
        if hasattr(video, 'close'):
            video.close()
