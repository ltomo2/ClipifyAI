"""Probe native Qt multimedia in a disposable process before loading it in the UI."""
import sys


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PySide6.QtMultimediaWidgets import QVideoWidget
    app = QApplication([])
    audio = QAudioOutput()
    audio.setVolume(0)
    video = QVideoWidget()
    player = QMediaPlayer()
    player.setAudioOutput(audio)
    player.setVideoOutput(video)
    player.setSource(QUrl.fromLocalFile(sys.argv[1]))
    player.play()
    def finished():
        status = player.mediaStatus()
        valid = player.error() == QMediaPlayer.Error.NoError and status in (
            QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia,
            QMediaPlayer.MediaStatus.BufferingMedia, QMediaPlayer.MediaStatus.EndOfMedia)
        player.stop()
        app.exit(0 if valid else 1)
    QTimer.singleShot(1500, finished)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
