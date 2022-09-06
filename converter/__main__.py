import json
from os import getenv, path, remove, makedirs
from subprocess import Popen, PIPE, run
from time import sleep

import traceback
import sys

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

AUDIO_16_PATH = getenv("AUDIO_16_PATH", "./audio16")
CCMA_AUDIO_DOWNLOAD_PATH = getenv("CCMA_AUDIO_DOWNLOAD_PATH", "./audio/ccma")

if not path.exists(AUDIO_16_PATH):
    makedirs(AUDIO_16_PATH)

if not path.exists(CCMA_AUDIO_DOWNLOAD_PATH):
    makedirs(CCMA_AUDIO_DOWNLOAD_PATH)
def get_duration_and_sr(audiopath):
    cmd = ['ffprobe', '-i', audiopath, '-show_streams', '-show_format', '-v', 'quiet', '-of', 'json']
    p = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    if stderr:
        raise Exception(stderr)
    result = json.loads(stdout)
    duration = result['format']['duration']
    sr = result['streams'][0]['sample_rate']
    return duration, sr


def convert(source_id, audiopath):
    print(f"CCMA: Converting {audiopath}")
    audiopath16 = path.join(AUDIO_16_PATH, f"{source_id}.wav")
    try:
        duration, sr = get_duration_and_sr(audiopath)
        result = run(['ffmpeg', '-y', '-i', audiopath, '-ac', '1', '-ar', '16000', '-f', 'wav', audiopath16],
                     capture_output=True)
        if result.returncode != 0:
            print(f"ffmpeg command failed: {result.stderr.decode()}")
            raise Exception
        return (sr, duration, audiopath16)
    except Exception as ex:
        if path.isfile(audiopath16):
            remove(audiopath16)
        raise ex


def ccma_convert(source_id, audiopath):
    print(f"Converting {audiopath}")
    convertedpath = path.join(CCMA_AUDIO_DOWNLOAD_PATH, f"{source_id}.mp4")
    try:
        # duration, sr = get_duration_and_sr(audiopath)
        result = run(['ffmpeg', '-i', audiopath, '-vn', '-acodec', 'copy', '-y', convertedpath], capture_output=True)
        if result.returncode != 0:
            print(f"ffmpeg command failed: {result.stderr.decode()}")
            raise Exception
        return convertedpath
    except Exception as ex:
        remove_file(convertedpath)
        raise ex


def remove_file(filepath):
    if path.isfile(filepath):
        remove(filepath)


conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.close()
    cur = conn.cursor()
    cur.execute("UPDATE sources SET status='audio_converting', status_update=now() \
    WHERE source_id = ( \
    SELECT source_id \
    FROM sources \
    WHERE status='audio_extracted' \
    ORDER BY random()  \
    FOR UPDATE SKIP LOCKED \
    LIMIT 1 \
    ) \
    RETURNING source_id, audiopath, type;")
    conn.commit()
    next = cur.fetchone()
    if next:
        source_id, audiopath, type = next
        try:
            if type == "youtube":
                sr, duration, audiopath16 = convert(source_id, audiopath)
                cur.execute(
                    f"UPDATE sources SET sr='{sr}', duration='{duration}', audiopath_16='{audiopath16}', status='audio_converted', status_update=now() WHERE source_id = '{source_id}'")
            if type == "ccma":
                convertedpath = ccma_convert(source_id, audiopath)
                if convertedpath:
                    print(f"CCMA: Converting succeeded")
                    cur.execute(
                        f"UPDATE sources SET audiopath='{convertedpath}',status='audio_converted', status_update=now() WHERE source_id = '{source_id}'")
                    remove_file(audiopath)
                else:
                    print("CCMA: Converting failed: no audio")
                    cur.execute(
                        f"UPDATE sources SET status='error', status_update=now() WHERE source_id = '{source_id}'")
        except KeyboardInterrupt:
            print("Stopping")
            cur.execute(
                f"UPDATE sources SET status='audio_extracted', status_update=now() WHERE source_id = '{source_id}'")
            conn.commit()
            break
        except Exception as ex:
            print(f"Preprocessing failed")
            traceback.print_exc()
            cur.execute(
                f"UPDATE sources SET status='audio_extracted', status_update=now() WHERE source_id = '{source_id}'")
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
