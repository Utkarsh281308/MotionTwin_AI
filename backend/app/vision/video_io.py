"""Video helpers: browser-playable copies and single frames."""
import subprocess

import cv2
import imageio_ffmpeg


def to_browser_mp4(src: str, dst: str) -> None:
    """Re-encode to H.264 + faststart so every browser can play it (phones often record HEVC)."""
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-i", src,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "23",
         "-movflags", "+faststart", "-an", dst],
        check=True,
    )


def read_frame_jpeg(video_path: str, index: int = 0, quality: int = 90) -> bytes:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise ValueError(f"Cannot read frame {index} of {video_path}")
    return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()
