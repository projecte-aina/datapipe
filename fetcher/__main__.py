import os
import shutil
import uuid
from os import getenv, path, makedirs
from urllib.error import HTTPError
from time import sleep

import requests
from pytubefix import YouTube
from pytubefix.innertube import _default_clients
import traceback

from db import get_connection
from utils import GracefulKiller

# Allow Android clients
_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID"]

killer = GracefulKiller()

# ---------- Paths ----------
YT_AUDIO_DOWNLOAD_PATH = getenv("YT_AUDIO_DOWNLOAD_PATH", "./audio/youtube")
YT_CAPTION_DOWNLOAD_PATH = getenv("YT_CAPTION_DOWNLOAD_PATH", "./caption/youtube")
CCMA_AUDIO_DOWNLOAD_PATH = getenv("CCMA_AUDIO_DOWNLOAD_PATH", "./audio/ccma")
CCMA_VIDEO_DOWNLOAD_PATH = getenv("CCMA_VIDEO_DOWNLOAD_PATH", "./tmp/video/ccma")
CCMA_CAPTION_DOWNLOAD_PATH = getenv("CCMA_CAPTION_DOWNLOAD_PATH", "./caption/ccma")

youtube_wait = 5

# Ensure directories exist
for p in (YT_AUDIO_DOWNLOAD_PATH, YT_CAPTION_DOWNLOAD_PATH,
          CCMA_AUDIO_DOWNLOAD_PATH, CCMA_VIDEO_DOWNLOAD_PATH, CCMA_CAPTION_DOWNLOAD_PATH):
    makedirs(p, exist_ok=True)

# ---------- Helper functions ----------
class FilesizeNotMatching(Exception):
    """Filesize of downloaded file does not match"""
    pass


def get_youtube(source_id, url):
    print(f"YT: Fetching {url} (id={source_id})")
    return YouTube(url)


def youtube_download_audio(yt, source_id):
    stream = yt.streams.filter(only_audio=True).order_by("abr").last()
    if not stream:
        return None
    ext = stream.default_filename.split('.')[-1]
    filename = f"{source_id}.{ext}"
    filepath = path.join(YT_AUDIO_DOWNLOAD_PATH, filename)
    filesize = stream.filesize
    stream.download(YT_AUDIO_DOWNLOAD_PATH, filename, None)
    if filesize != path.getsize(filepath):
        os.remove(filepath)
        raise FilesizeNotMatching
    return filepath


def download_yt_captions(yt, source_id):
    filename = f"{source_id}.xml"
    filepath = path.join(YT_CAPTION_DOWNLOAD_PATH, filename)
    try:
        caption = yt.captions.get_by_language_code('ca')
        xml_captions = caption.xml_captions
        with open(filepath, 'w') as f:
            f.write(xml_captions)
        return filepath
    except Exception:
        traceback.print_exc()
        return None


def ccma_download_source(url, source_id):
    print(f"CCMA: Fetching {url} (id={source_id})")
    slited = url.split('/')[-1]
    ext = slited.split('.')[-1]
    filename = f"{source_id}.{ext}"
    filepath = path.join(CCMA_VIDEO_DOWNLOAD_PATH, filename)
    with requests.get(url, stream=True) as r:
        with open(filepath, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    return filepath


def ccma_download_captions(url, source_id):
    filename = f"{source_id}.xml"
    filepath = path.join(CCMA_CAPTION_DOWNLOAD_PATH, filename)
    try:
        with requests.get(url, stream=True) as r:
            with open(filepath, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        return filepath
    except Exception:
        traceback.print_exc()
        return None

# ---------- Main fetcher loop ----------
conn = get_connection()
cur = conn.cursor()

print("Starting fetcher with one-time filesystem processing for local WAV...")
while not killer.kill_now:
    # Attempt to fetch next DB source to download
    cur.execute(
        """
        UPDATE sources SET status='downloading', status_update=now()
         WHERE source_id = (
               SELECT source_id FROM sources
                WHERE status='ready_for_download'
                ORDER BY random() FOR UPDATE SKIP LOCKED LIMIT 1
         ) RETURNING has_captions, subtitlepath, source_id, url, type;
        """
    )
    conn.commit()
    row = cur.fetchone()

    # If none found, check for a single local WAV in the youtube audio folder
    local_wav = path.join(YT_AUDIO_DOWNLOAD_PATH, 'video.wav')
    local_detected = False
    if not row and path.isfile(local_wav):
        local_detected = True
        source_id = str(uuid.uuid4())
        url = local_wav
        has_captions = False
        subtitlepath = None
        source_type = 'youtube'
        print(f"Detected local WAV for one-time processing: {local_wav} -> source {source_id}")
        # Insert as already extracted
        cur.execute(
            "INSERT INTO sources (source_id, url, has_captions, subtitlepath, audiopath, type, status, status_update)"
            " VALUES (%s,%s,%s,%s,%s,%s,'audio_extracted',now())",
            (source_id, url, has_captions, subtitlepath, local_wav, source_type)
        )
        conn.commit()
        row = (has_captions, subtitlepath, source_id, url, source_type)

    # If still nothing, sleep and continue
    if not row:
        print("No work, sleeping for 10s...")
        sleep(10)
        continue

    # Unpack the row for processing
    has_captions, subtitlepath, source_id, url, source_type = row
    try:
        if source_type == "youtube":
            yt = get_youtube(source_id, url) if url.startswith('http') else None
            audiopath = youtube_download_audio(yt, source_id) if yt else url
            if audiopath:
                print("YT: Fetching succeeded")
                cur.execute(
                    "UPDATE sources SET status='audio_extracted', audiopath=%s, status_update=now() WHERE source_id=%s",
                    (audiopath, source_id)
                )
                if has_captions and yt:
                    subtitlepath = download_yt_captions(yt, source_id)
                    if subtitlepath:
                        cur.execute(
                            "UPDATE sources SET subtitlepath=%s, status_update=now() WHERE source_id=%s",
                            (subtitlepath, source_id)
                        )
                        print("YT: Caption fetching succeeded")
            else:
                print("YT: Fetching failed: no audio")
                cur.execute("UPDATE sources SET status='error', status_update=now() WHERE source_id=%s", (source_id,))

        elif source_type == "ccma":
            audiopath = ccma_download_source(url, source_id)
            if audiopath:
                print("CCMA: Fetching succeeded")
                cur.execute(
                    "UPDATE sources SET status='audio_extracted', audiopath=%s, status_update=now() WHERE source_id=%s",
                    (audiopath, source_id)
                )
                if has_captions:
                    subtitles = ccma_download_captions(subtitlepath, source_id)
                    if subtitles:
                        cur.execute(
                            "UPDATE sources SET subtitlepath=%s, status_update=now() WHERE source_id=%s",
                            (subtitles, source_id)
                        )
                        print("CCMA: Caption fetching succeeded")
            else:
                print("CCMA: Fetching failed: no audio")
                cur.execute("UPDATE sources SET status='error', status_update=now() WHERE source_id=%s", (source_id,))

        else:
            print(f"Unknown source type {source_type}!")

    except HTTPError as err:
        print(f"HTTP Error {err}")
        cur.execute(
            "UPDATE sources SET status='ready_for_download', status_update=now() WHERE source_id=%s",
            (source_id,)
        )
        conn.commit()
        if err.code == 429:
            print("Too Many requests, waiting 1 hour")
            sleep(3600)

    except KeyboardInterrupt:
        print("Stopping")
        cur.execute(
            "UPDATE sources SET status='ready_for_download', status_update=now() WHERE source_id=%s",
            (source_id,)
        )
        conn.commit()
        break

    except Exception:
        print(f"Fetching failed for source {source_id}")
        traceback.print_exc()
        cur.execute(
            "UPDATE sources SET status='ready_for_download', status_update=now() WHERE source_id=%s",
            (source_id,)
        )

    finally:
        conn.commit()
        # NOTE: Removed removal of local WAV to preserve the file after processing
        # if local_detected and path.isfile(local_wav):
        #     os.remove(local_wav)
        #     print(f"Removed local WAV: {local_wav}")

cur.close()
conn.close()
print("Fetcher shutdown.")