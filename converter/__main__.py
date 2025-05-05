import json
from os import getenv, path, remove, makedirs
from subprocess import Popen, PIPE, run
from time import sleep
import traceback
import sys

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

# ---------- Paths ----------
AUDIO_16_PATH = getenv("AUDIO_16_PATH", "./audio16")
CCMA_AUDIO_DOWNLOAD_PATH = getenv(
    "CCMA_AUDIO_DOWNLOAD_PATH", "./audio/ccma")

if not path.exists(AUDIO_16_PATH):
    makedirs(AUDIO_16_PATH)

if not path.exists(CCMA_AUDIO_DOWNLOAD_PATH):
    makedirs(CCMA_AUDIO_DOWNLOAD_PATH)

# ---------- Helpers ----------
def get_duration_and_sr(audiopath: str):
    """Return (sample_rate, duration) using ffprobe."""
    cmd = [
        "ffprobe", "-i", audiopath,
        "-show_streams", "-show_format",
        "-v", "quiet", "-of", "json",
    ]
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    if stderr:
        raise RuntimeError(stderr.decode())
    info = json.loads(stdout)
    duration = info["format"]["duration"]
    sr = info["streams"][0]["sample_rate"]
    return int(sr), float(duration)


def convert(source_id: str, audiopath: str):
    """
    Down‑sample *audiopath* to 16 kHz mono WAV.

    Returns (sample_rate, duration, converted_path).
    """
    print(f"YT: Converting {audiopath}")
    converted_path = path.join(AUDIO_16_PATH, f"{source_id}.wav")

    # remove a stale file, if any
    if path.isfile(converted_path):
        remove(converted_path)

    try:
        result = run(
            [
                "ffmpeg", "-y",
                "-i", audiopath,
                "-ac", "1",                 # mono
                "-ar", "16000",             # 16 kHz
                "-f", "wav", converted_path
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())

        # probe the converted file – that is what matters downstream
        sr, duration = get_duration_and_sr(converted_path)
        return sr, duration, converted_path

    except Exception:
        if path.isfile(converted_path):
            remove(converted_path)
        raise


def ccma_convert(source_id: str, audiopath: str):
    """
    CCMA items are already 16 kHz mono AAC. We keep them in MP4
    and write the path to `sources.audiopath_16` for consistency.
    """
    print(f"CCMA: Converting {audiopath}")
    converted_path = path.join(
        CCMA_AUDIO_DOWNLOAD_PATH, f"{source_id}.mp4")

    # remove stale file
    if path.isfile(converted_path):
        remove(converted_path)

    try:
        result = run(
            ["ffmpeg", "-i", audiopath, "-vn",
             "-acodec", "copy", "-y", converted_path],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode())
        return converted_path
    except Exception:
        if path.isfile(converted_path):
            remove(converted_path)
        raise


# ---------- Main worker loop ----------
conn = get_connection()
cur = conn.cursor()

print("Starting converter")
while not killer.kill_now:
    cur.close()
    cur = conn.cursor()

    # Pop one item that still needs audio conversion
    cur.execute(
        """
        UPDATE sources
           SET status='audio_converting',
               status_update = now()
         WHERE source_id = (
               SELECT source_id
                 FROM sources
                WHERE status='audio_extracted'
                ORDER BY random()
                FOR UPDATE SKIP LOCKED
                LIMIT 1)
       RETURNING source_id, audiopath, type;
        """
    )
    conn.commit()

    row = cur.fetchone()
    if not row:
        try:
            print("No work, sleeping for 10 s …")
            sleep(10)
        except KeyboardInterrupt:
            break
        continue

    source_id, audiopath, source_type = row

    try:
        # ---------- YouTube ----------
        if source_type == "youtube":
            sr, duration, converted = convert(source_id, audiopath)
            cur.execute(
                """
                UPDATE sources
                   SET sr            = %s,
                       duration      = %s,
                       audiopath_16  = %s,
                       status        = 'audio_converted',
                       status_update = now()
                 WHERE source_id = %s;
                """,
                (sr, duration, converted, source_id),
            )
            print(f"YT: Converting succeeded ({converted})")

        # ---------- CCMA ----------
        elif source_type == "ccma":
            converted = ccma_convert(source_id, audiopath)
            cur.execute(
                """
                UPDATE sources
                   SET audiopath_16 = %s,
                       status       = 'audio_converted',
                       status_update = now()
                 WHERE source_id = %s;
                """,
                (converted, source_id),
            )
            # free space
            if path.isfile(audiopath):
                remove(audiopath)
            print("CCMA: Converting succeeded")

        else:
            print(f"Unknown source type '{source_type}' – skipping")

    except KeyboardInterrupt:
        print("Stopping gracefully")
        cur.execute(
            """
            UPDATE sources
               SET status='audio_extracted',
                   status_update = now()
             WHERE source_id = %s;
            """,
            (source_id,),
        )
        conn.commit()
        break

    except Exception:
        print("Converting failed – will retry")
        traceback.print_exc()
        cur.execute(
            """
            UPDATE sources
               SET status='audio_extracted',
                   status_update = now()
             WHERE source_id = %s;
            """,
            (source_id,),
        )

    finally:
        conn.commit()

cur.close()
conn.close()