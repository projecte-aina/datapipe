from os import getenv
import sys
import json
from time import sleep
import requests
import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

API_URL = getenv("API_URL", "http://wav2vec2-catala/recognize")

def transcribe(clippath):
    print(f"Transcribing {clippath}")
    with open(clippath, 'rb') as f:
        response = requests.post(API_URL, files={'file': f})
    transcription = json.loads(response.content.decode("utf-8"))

    return transcription['text']

conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute("\
        SELECT c.clip_id, c.filepath \
        FROM transcripts t, clips c \
        WHERE t.transcriber != 'wav2vec2' AND t.clip_id = c.clip_id AND c.filepath IS NOT NULL\
        ORDER BY random() \
        LIMIT 1;")
    next = cur.fetchone()

    if next:
        clip_id, filepath = next
        try:
            text = transcribe(filepath)
            cur.execute('INSERT INTO transcripts ("text", transcriber, clip_id) VALUES (%s, %s, %s) RETURNING transcript_id;', (text, "wav2vec2", clip_id))
            conn.commit()
        except KeyboardInterrupt:
            print("Stopping")
            break
        except Exception as ex:
            print(f"Transcription failed")
            traceback.print_exc()
    else:
        try:
            print("No work, sleeping for 10s...")
            sleep(10)
        except KeyboardInterrupt:
            break

cur.close()
conn.close()