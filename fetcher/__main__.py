import os
from os import getenv, path, remove
from urllib.error import HTTPError
from time import sleep
from pytube import YouTube
import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

AUDIO_DOWNLOAD_PATH = getenv("AUDIO_DOWNLOAD_PATH", "./audio")
CAPTION_DOWNLOAD_PATH = getenv("CAPTION_DOWNLOAD_PATH", "./caption")
youtube_wait = 5


class FilesizeNotMatching(Exception):
    """Filesize of downloaded file does not match"""
    pass


def get_youtube(source_id, url):
    print(f"YT: Fetching {url} (id={source_id})")
    return YouTube(url)


def youtube_download_audio(yt):
    stream = yt.streams.filter(only_audio=True).order_by("abr").last()
    if stream:
        ext = stream.default_filename.split('.')[-1]
        filename = f"{source_id}.{ext}"
        filesize = stream.filesize
        filepath = path.join(AUDIO_DOWNLOAD_PATH, filename)
        stream.download(AUDIO_DOWNLOAD_PATH, filename, None)
        if filesize != path.getsize(filepath):
            remove(filepath)
            raise FilesizeNotMatching
        return filepath


def download_captions(yt):
    filename = f"{source_id}.xml"
    filepath = path.join(CAPTION_DOWNLOAD_PATH, filename)

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        captions = yt.captions['ca'].xml_captions

        with open(filepath, 'w') as f:
            f.write(captions)

        if captions:
            return filepath
    except Exception as ex:
        print(f"Downloading caption failed")
        traceback.print_exc()


conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute("UPDATE sources SET status='downloading', status_update=now() \
    WHERE source_id = ( \
    SELECT source_id \
    FROM sources \
    WHERE status='ready_for_download' \
    ORDER BY random()  \
    FOR UPDATE SKIP LOCKED \
    LIMIT 1 \
    ) \
    RETURNING has_captions, source_id, url, type;")
    conn.commit()
    next = cur.fetchone()

    if next:
        has_captions, source_id, url, type = next
        try:
            if type == "youtube":
                yt = get_youtube(source_id, url)
                audiopath = youtube_download_audio(yt)
                if audiopath:
                    print("Fetching succeeded")
                    cur.execute(
                        f"UPDATE sources SET status='audio_extracted', audiopath='{audiopath}', status_update=now() WHERE source_id = '{source_id}'")
                    if has_captions:
                        print(f"YT: Fetching captions {url} (id={source_id})")
                        subtitlepath = download_captions(yt)
                        if subtitlepath:
                            cur.execute(
                                f"UPDATE sources SET subtitlepath='{subtitlepath}', status_update=now() WHERE source_id = '{source_id}'")
                            print("Caption fetching succeeded")
                else:
                    print("Fetching failed: no audio")
                    cur.execute(
                        f"UPDATE sources SET status='error', status_update=now() WHERE source_id = '{source_id}'")

            else:
                print(f"Unknown source type {type}!")
        except HTTPError as err:
            print(f"HTTP Error {err}")
            cur.execute(
                f"UPDATE sources SET status='ready_for_download', status_update=now() WHERE source_id = '{source_id}'")
            conn.commit()
            if err.code == 429:
                print("Too Many requests, waiting 1 hour")
                youtube_wait += 5
                sleep(3600)
        except KeyboardInterrupt:
            print("Stopping")
            cur.execute(
                f"UPDATE sources SET status='ready_for_download', status_update=now() WHERE source_id = '{source_id}'")
            conn.commit()
            break
        except Exception as ex:
            print(f"Preprocessing failed")
            traceback.print_exc()
            cur.execute(
                f"UPDATE sources SET status='ready_for_download', status_update=now() WHERE source_id = '{source_id}'")
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
