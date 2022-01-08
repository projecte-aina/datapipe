from os import getenv, path, remove, makedirs
from subprocess import run
from time import sleep

import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

CLIPS_PATH = getenv("CLIPS_PATH", "./clips")

if not path.exists(CLIPS_PATH):
    makedirs(CLIPS_PATH)

def split(clip_id, audiopath, start, end):
    print(f"Splitting {audiopath} from {start} to {end}")
    clippath = path.join(CLIPS_PATH, f"{clip_id}.wav")
    try:
        result = run(['ffmpeg', '-y', '-i', audiopath, '-ss', str(start), '-to', str(end), '-c', 'copy', clippath], capture_output=True)
        if result.returncode != 0:
            print(f"ffmpeg command failed: {result.stderr.decode()}")
            raise Exception
        return clippath
    except Exception as ex:
        if path.isfile(clippath):
            remove(clippath)
        raise ex


conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute('\
    UPDATE clips \
    SET status = \'splitting\', status_update = now() \
    FROM \
    ( \
        SELECT \
        clip_id, source_id, "start", "end" \
        FROM clips \
        WHERE status = \'new\' \
        ORDER BY random() \
        LIMIT 1 \
        FOR UPDATE SKIP LOCKED \
    ) c \
    JOIN sources s ON s.source_id = c.source_id \
    WHERE clips.clip_id = c.clip_id \
    RETURNING c.clip_id, c.source_id, s.audiopath_16, c."start", c."end";')
    conn.commit()
    clip = cur.fetchone()
    
    if clip:
        clip_id, source_id, audiopath_16, start, end = clip
        try:
            clippath = split(clip_id, audiopath_16, start, end)
            cur.execute(f"UPDATE clips SET filepath='{clippath}', status='split', status_update=now() WHERE clip_id = '{clip_id}'")
        except KeyboardInterrupt:
            print("Stopping")
            cur.execute(f"UPDATE clips SET status='new', status_update=now() WHERE clip_id = '{clip_id}'")
            conn.commit()
            break
        except Exception as ex:
            print(f"Preprocessing failed")
            traceback.print_exc()
            cur.execute(f"UPDATE clips SET status='new', status_update=now() WHERE clip_id = '{clip_id}'")
        finally:
            conn.commit()
    else:
        try:
            print("No work, sleeping for 10s...")
            sleep(10)
        except KeyboardInterrupt:
            break

cur.close()
conn.close()