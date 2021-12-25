from os import getenv, path
from time import sleep
from pytube import YouTube
import traceback

from db import get_connection

DOWLOAD_PATH = getenv("DOWNLOAD_PATH", "./media")

def get_youtube(source_id, url):
    print(f"YT: Fetching {url} (id={source_id})")
    return YouTube(url)

def youtube_download_audio(yt):
    stream = yt.streams.filter(only_audio=True).order_by("abr").last()
    if stream:
        ext = stream.default_filename.split('.')[-1]
        filename = f"{source_id}.{ext}"
        stream.download(DOWLOAD_PATH, filename, None)
        return path.join(DOWLOAD_PATH, filename)





conn = get_connection()

cur = conn.cursor()

print("Starting")
while True:
    cur.execute("UPDATE sources SET status='downloading' \
    WHERE source_id = ( \
    SELECT source_id \
    FROM sources \
    WHERE status='ready_for_download' \
    ORDER BY source_id  \
    FOR UPDATE SKIP LOCKED \
    LIMIT 1 \
    ) \
    RETURNING source_id, url, type;")
    conn.commit()
    next = cur.fetchone()

    if next:
        source_id, url, type = next
        if type == "youtube":
            try:
                yt = get_youtube(source_id, url)
                audiopath = youtube_download_audio(yt)
                if audiopath:
                    print("Fetching succeeded")
                    cur.execute(f"UPDATE sources SET status='audio_extracted', audiopath='{audiopath}' WHERE source_id = '{source_id}'")
                else:
                    print("Fetching failed: no audio")
                    cur.execute(f"UPDATE sources SET status='error' WHERE source_id = '{source_id}'")
            except KeyboardInterrupt:
                print("Stopping")
                cur.execute(f"UPDATE sources SET status='ready_for_download' WHERE source_id = '{source_id}'")
                conn.commit()
                break
            except Exception as ex:
                print(f"Preprocessing failed")
                traceback.print_exc()
                cur.execute(f"UPDATE sources SET status='ready_for_download' WHERE source_id = '{source_id}'")
            finally:
                conn.commit
        else:
            print(f"Unknown source type {type}!")
    else:
        try:
            print("No work, sleeping for 10s...")
            sleep(10)
        except KeyboardInterrupt:
            break

cur.close()
conn.close()