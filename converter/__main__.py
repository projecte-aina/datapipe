from os import getenv, path, remove, makedirs
import subprocess
from time import sleep
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

AUDIO_16_PATH = getenv("AUDIO_16_PATH", "./audio16")

if not path.exists(AUDIO_16_PATH):
    makedirs(AUDIO_16_PATH)

def convert(source_id, audiopath):
    print(f"Converting {audiopath}")
    audiopath16 = path.join(AUDIO_16_PATH, f"{source_id}.wav")
    sr = 0
    duration = 0
    try:
        sound = AudioSegment.from_file(audiopath)
        sr = sound.frame_rate
        duration = sound.duration_seconds
        sound.export(audiopath16, format="wav", parameters=["-ac", "1", "-ar", "16000"])
    except CouldntDecodeError:
        print("Trying with ffmpeg")
        result = subprocess.run(['ffmpeg', '-i', audiopath, '-ac', '1', '-ar', '16000', '-f', 'wav', audiopath16], capture_output=True)
        if result.returncode != 0:
            print(f"ffmpeg command failed: {result.stderr.decode()}")
            raise Exception
    except Exception as ex:
        if path.isfile(audiopath16):
            remove(audiopath16)
        raise ex
    return (sr, duration, audiopath16)


conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute("UPDATE sources SET status='audio_converting', status_update=now() \
    WHERE source_id = ( \
    SELECT source_id \
    FROM sources \
    WHERE status='audio_extracted' \
    ORDER BY random()  \
    FOR UPDATE SKIP LOCKED \
    LIMIT 1 \
    ) \
    RETURNING source_id, audiopath;")
    conn.commit()
    next = cur.fetchone()

    if next:
        source_id, audiopath = next
        try:
            sr, duration, audiopath16 = convert(source_id, audiopath)
            cur.execute(f"UPDATE sources SET sr='{sr}', duration='{duration}', audiopath_16='{audiopath16}', status='audio_converted', status_update=now() WHERE source_id = '{source_id}'")
        except KeyboardInterrupt:
            print("Stopping")
            cur.execute(f"UPDATE sources SET status='audio_extracted', status_update=now() WHERE source_id = '{source_id}'")
            conn.commit()
            break
        except Exception as ex:
            print(f"Preprocessing failed")
            traceback.print_exc()
            cur.execute(f"UPDATE sources SET status='audio_extracted', status_update=now() WHERE source_id = '{source_id}'")
        finally:
            conn.commit
    else:
        try:
            print("No work, sleeping for 10s...")
            sleep(10)
        except KeyboardInterrupt:
            break

cur.close()
conn.close()