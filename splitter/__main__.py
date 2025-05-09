#!/usr/bin/env python3
import os
import traceback
from os import getenv, path, remove, makedirs
from subprocess import run
from time import sleep
from threading import Thread

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from db import get_connection
from utils import GracefulKiller

#─── Configuration ──────────────────────────────────────────────────────────────
# Environment variables set by Docker Compose:
#   - AUDIO_16_PATH: directory to watch for incoming .wav files
#   - CLIPS_PATH:   directory to write clip outputs
#   - PG_HOST, PG_PASSWORD, etc. consumed by db.get_connection()

AUDIO_16_PATH = getenv("AUDIO_16_PATH", "/datapipe/audio16")
CLIPS_PATH    = getenv("CLIPS_PATH", "/datapipe/clips")

for p in (AUDIO_16_PATH, CLIPS_PATH):
    if not path.exists(p):
        makedirs(p)

killer = GracefulKiller()
conn   = get_connection()

#─── Helper: split one clip via ffmpeg ────────────────────────────────────────────

def split(clip_id, audiopath, start, end):
    """Extract a segment [start,end) from audiopath into CLIPS_PATH/clip_id.wav."""
    print(f"Splitting {audiopath} from {start}s to {end}s → clip {clip_id}")
    clippath = path.join(CLIPS_PATH, f"{clip_id}.wav")
    cmd = [
        "ffmpeg", "-y",
        "-i", audiopath,
        "-ss", str(start),
        "-to", str(end),
        "-c", "copy",
        clippath
    ]
    result = run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"ERROR: ffmpeg failed for clip {clip_id}: {result.stderr.decode().strip()}")
        if path.isfile(clippath):
            remove(clippath)
        raise RuntimeError("ffmpeg split failed")
    return clippath

#─── Stub: determine segments for a new file ────────────────────────────────────

def get_segments(audiopath):
    """
    Return a list of (start_seconds, end_seconds) tuples for this file.
    Implement your own logic: e.g. load a JSON of timestamps,
    or split every N seconds.
    """
    # EXAMPLE: split into 10-second chunks (replace with your logic)
    total_duration = 60  # ← you could probe with ffprobe here
    chunk = 10
    segments = []
    for t in range(0, total_duration, chunk):
        segments.append((t, min(t + chunk, total_duration)))
    return segments

#─── Database enqueue: when a new wav appears ───────────────────────────────────

def enqueue_file(audiopath):
    """
    Inserts a new source row + its clips into the DB.
    Relies on tables:
      - sources(source_id, audiopath_16, status, status_update)
      - clips(clip_id, source_id, start, end, status, status_update, filepath)
    """
    with conn, conn.cursor() as cur:
        # 1) create new source
        cur.execute(
            "INSERT INTO sources (audiopath_16, status, status_update) "
            "VALUES (%s, 'new', now()) RETURNING source_id",
            (audiopath,)
        )
        source_id, = cur.fetchone()

        # 2) insert one clip per segment
        segments = get_segments(audiopath)
        for start, end in segments:
            cur.execute(
                "INSERT INTO clips (source_id, start, end, status, status_update) "
                "VALUES (%s, %s, %s, 'new', now())",
                (source_id, start, end)
            )

    print(f"Enqueued {audiopath} → source {source_id} ({len(segments)} clips)")

#─── Watchdog handler: fire enqueue on file creation ────────────────────────────

class WavHandler(PatternMatchingEventHandler):
    patterns = ["*.wav"]

    def on_created(self, event):
        print(f"Detected new file: {event.src_path}")
        Thread(target=enqueue_file, args=(event.src_path,), daemon=True).start()


def start_watcher():
    observer = Observer()
    observer.schedule(WavHandler(), path=AUDIO_16_PATH, recursive=False)
    observer.start()
    return observer

#─── Main worker loop: pick & split clips ───────────────────────────────────────

def worker_loop():
    print("Worker started, waiting for clips…")
    cur = conn.cursor()

    while not killer.kill_now:
        # 1) claim one 'new' clip
        cur.execute("""
            UPDATE clips
            SET status = 'splitting', status_update = now()
            FROM (
                SELECT clip_id, source_id, start, end
                FROM clips
                WHERE status = 'new'
                ORDER BY random()
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            ) c
            JOIN sources s ON s.source_id = c.source_id
            WHERE clips.clip_id = c.clip_id
            RETURNING
                c.clip_id,
                c.source_id,
                c.start,
                c.end,
                s.audiopath_16
        """
        )
        conn.commit()
        row = cur.fetchone()

        if not row:
            sleep(1)
            continue

        clip_id, source_id, start, end, audiopath = row
        try:
            clippath = split(clip_id, audiopath, start, end)
            cur.execute(
                "UPDATE clips SET filepath=%s, status='split', status_update=now() "
                "WHERE clip_id=%s",
                (clippath, clip_id)
            )
        except KeyboardInterrupt:
            cur.execute(
                "UPDATE clips SET status='new', status_update=now() WHERE clip_id=%s",
                (clip_id,)
            )
            conn.commit()
            print("Interrupted: resetting clip and exiting worker.")
            break
        except Exception:
            traceback.print_exc()
            cur.execute(
                "UPDATE clips SET status='new', status_update=now() WHERE clip_id=%s",
                (clip_id,)
            )
        finally:
            conn.commit()

        # 2) if that was the last clip for this source, delete the .wav
        cur.execute("""
            SELECT COUNT(*) FROM clips
            WHERE source_id=%s AND status!='split'
        """, (source_id,))
        remaining, = cur.fetchone()
        if remaining == 0:
            print(f"All clips done for source {source_id}; deleting {audiopath}")
            try:
                remove(audiopath)
            except OSError as e:
                print(f"Failed to delete source file: {e}")
            cur.execute(
                "UPDATE sources SET status='processed', status_update=now() "
                "WHERE source_id=%s",
                (source_id,)
            )
            conn.commit()

    cur.close()

#─── Entry point & graceful shutdown ────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting service…")
    observer = start_watcher()
    try:
        worker_loop()
    finally:
        print("Shutting down watcher & DB…")
        observer.stop()
        observer.join()
        conn.close()
        print("Stopped cleanly.")