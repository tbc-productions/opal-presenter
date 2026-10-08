"""Cached browser-compatible playback copies; portable designs retain their originals."""
from pathlib import Path
from tempfile import NamedTemporaryFile

from PySide6 import QtCore

from openlp.core.lib.designmedia import ASSET, asset_root, cache_media, materialise_media


def video_playback_path(source):
    """Prepare a silent WebM once, including when the original uses a proprietary codec."""
    source = materialise_media(source)
    source = Path(source)
    if source.suffix.lower() in ('.webm', '.ogv'):
        return source
    reference = 'assets/' + source.name
    if source.parent != asset_root() / 'assets' or not ASSET.fullmatch(reference):
        reference = cache_media(source)
    destination = asset_root() / 'playback' / (Path(reference).stem + '.webm')
    if destination.is_file():
        return destination
    import imageio_ffmpeg
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=destination.parent, suffix='.webm', delete=False) as temporary_file:
        temporary = Path(temporary_file.name)
    process = QtCore.QProcess()
    process.setProcessChannelMode(QtCore.QProcess.ProcessChannelMode.MergedChannels)
    scaling = "scale=w='min(iw,1920)':h='min(ih,1080)':force_original_aspect_ratio=decrease:force_divisible_by=2"
    arguments = ['-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source), '-an', '-vf', scaling,
                 '-c:v', 'libvpx', '-deadline', 'realtime', '-cpu-used', '6', '-crf', '12', '-b:v', '0',
                 '-threads', '2', '-f', 'webm', str(temporary)]
    try:
        application = QtCore.QCoreApplication.instance()
        loop = None
        if application is not None and QtCore.QThread.currentThread() == application.thread():
            loop = QtCore.QEventLoop()
            process.finished.connect(loop.quit)
        process.start(imageio_ffmpeg.get_ffmpeg_exe(), arguments)
        if not process.waitForStarted(5000):
            raise ValueError('The video converter could not be started.')
        # Keep the GUI responsive on first use; service extraction can also run this in a worker.
        if loop is not None:
            if process.state() != QtCore.QProcess.ProcessState.NotRunning:
                loop.exec()
        else:
            process.waitForFinished(-1)
        if process.exitStatus() != QtCore.QProcess.ExitStatus.NormalExit or process.exitCode() != 0:
            raise ValueError('This video could not be prepared for the designer.')
        temporary.replace(destination)
        return destination
    finally:
        if process.state() != QtCore.QProcess.ProcessState.NotRunning:
            process.kill()
            process.waitForFinished(5000)
        temporary.unlink(missing_ok=True)
