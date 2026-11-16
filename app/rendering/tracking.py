"""Conservative sampled OpenCV face tracking; uncertain/multi-person shots use blur."""
import math


def track(source, start, end, job):
    try:
        import cv2
    except ImportError:
        return None, 'OpenCV unavailable; using blurred background.'
    if not hasattr(cv2, 'CascadeClassifier') or not hasattr(cv2, 'data'):
        return None, 'This OpenCV build has no frontal-face cascade backend; using blurred background.'
    cap = cv2.VideoCapture(str(source))
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if not cap.isOpened() or detector.empty():
        cap.release()
        return None, 'Face detector unavailable; using blurred background.'
    result = []
    hits = 0
    previous = None
    width, height = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if width / max(1, height) <= 9 / 16:
        cap.release()
        return None, 'Source is already portrait; preserving the full picture.'
    cropwidth = int(height * 9 / 16) // 2 * 2
    try:
        for i in range(math.ceil(end - start)):
            job.check()
            cap.set(cv2.CAP_PROP_POS_MSEC, (start + i) * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            scale = 480 / width
            small = cv2.resize(frame, (480, max(1, round(height * scale))))
            faces = detector.detectMultiScale(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), 1.12, 5, minSize=(20, 20))
            if len(faces) > 1:
                return None, 'Multiple faces detected; using blur to keep everyone visible.'
            if len(faces) == 1:
                x, y, w, h = faces[0]
                center = (x + w / 2) / scale
                # Do not crop a face wider than the portrait window.
                if w / scale > cropwidth * .8:
                    return None, 'Face too close for a safe portrait crop; using blur.'
                target = max(0, min(width - cropwidth, center - cropwidth / 2))
                current = target if previous is None else .5 * previous + .5 * target
                # Smoothing must not place the detected face outside the crop.
                face_left, face_right = x / scale, (x + w) / scale
                current = max(face_right - cropwidth, min(face_left, current))
                previous = max(0, min(width - cropwidth, current))
                hits += 1
            if previous is not None:
                result.append((i, int(previous) // 2 * 2))
        if hits / max(1, math.ceil(end - start)) < .7 or not result or result[0][0] > 0:
            return None, 'Face tracking confidence low; using blurred background.'
        return {'width': cropwidth, 'positions': result}, 'OpenCV face tracking (one sample per second).'
    finally:
        cap.release()
