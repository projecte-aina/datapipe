import os
import shutil
from os import getenv, path, remove
from urllib.error import HTTPError
from time import sleep

import requests
from pytubefix import YouTube
from pytubefix.innertube import _default_clients

_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID"]

import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

YT_AUDIO_DOWNLOAD_PATH = getenv("YT_AUDIO_DOWNLOAD_PATH", "./audio/youtube")
YT_CAPTION_DOWNLOAD_PATH = getenv("YT_CAPTION_DOWNLOAD_PATH", "./caption/youtube")
CCMA_AUDIO_DOWNLOAD_PATH = getenv("CCMA_AUDIO_DOWNLOAD_PATH", "./audio/ccma")
CCMA_VIDEO_DOWNLOAD_PATH = getenv("CCMA_VIDEO_DOWNLOAD_PATH", "./tmp/video/ccma")
CCMA_CAPTION_DOWNLOAD_PATH = getenv("CCMA_CAPTION_DOWNLOAD_PATH", "./caption/ccma")

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
        filepath = path.join(YT_AUDIO_DOWNLOAD_PATH, filename)
        stream.download(YT_AUDIO_DOWNLOAD_PATH, filename, None)
        if filesize != path.getsize(filepath):
            remove(filepath)
            raise FilesizeNotMatching
        return filepath

def ccma_download_source(url, source_id):
    print(f"CCMA: Fetching {url} (id={source_id})")
    slited_filename = url.split('/')[-1]
    ext = slited_filename.split('.')[-1]
    filename = f"{source_id}.{ext}"

    filepath = path.join(CCMA_VIDEO_DOWNLOAD_PATH, filename)

    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with requests.get(url, stream=True) as r:
        with open(filepath, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

    # with open(filepath, 'wb') as f:
    #     for chunk in r.iter_content(chunk_size=1024 * 1024):
    #         if chunk:
    #             f.write(chunk)

    return filepath


def download_yt_captions(yt):
    filename = f"{source_id}.xml"
    filepath = path.join(YT_CAPTION_DOWNLOAD_PATH, filename)

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        caption = yt.captions.get_by_language_code('ca')
        xml_captions = caption.xml_captions

        with open(filepath, 'w') as f:
            f.write(xml_captions)

        if caption:
            return filepath
    except Exception as ex:
        print(f"Downloading caption failed")
        traceback.print_exc()


def ccma_download_captions(url, source_id):
    filename = f"{source_id}.xml"
    filepath = path.join(CCMA_CAPTION_DOWNLOAD_PATH, filename)
    try:

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with requests.get(url, stream=True) as r:
            with open(filepath, 'wb') as f:
                shutil.copyfileobj(r.raw, f)

        # r = requests.get(url, stream=True)
        # with open(filepath, "wb") as xml:
        #     for chunk in r.iter_content(chunk_size=8192):
        #         if chunk:
        #             xml.write(chunk)
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
    RETURNING has_captions, subtitlepath, source_id, url, type;")
    conn.commit()
    next = cur.fetchone()

    if next:
        has_captions, subtitlepath, source_id, url, type = next
        try:
            if type == "youtube":
                yt = get_youtube(source_id, url)
                audiopath = youtube_download_audio(yt)
                if audiopath:
                    print("YT: Fetching succeeded")
                    cur.execute(
                        f"UPDATE sources SET status='audio_extracted', audiopath='{audiopath}', status_update=now() WHERE source_id = '{source_id}'")
                    if has_captions:
                        print(f"YT: Fetching captions {url} (id={source_id})")
                        subtitlepath = download_yt_captions(yt)
                        if subtitlepath:
                            cur.execute(
                                f"UPDATE sources SET subtitlepath='{subtitlepath}', status_update=now() WHERE source_id = '{source_id}'")
                            print("YT: Caption fetching succeeded")
                else:
                    print("YT: Fetching failed: no audio")
                    cur.execute(
                        f"UPDATE sources SET status='error', status_update=now() WHERE source_id = '{source_id}'")
            elif type == "ccma":
                audiopath = ccma_download_source(url, source_id)
                if audiopath:
                    print("CCMA: Fetching succeeded")
                    cur.execute(
                        f"UPDATE sources SET status='audio_extracted', audiopath='{audiopath}', status_update=now() WHERE source_id = '{source_id}'")
                    if has_captions:
                        print(f"CCMA: Fetching captions {subtitlepath} (id={source_id})")
                        subtitles = ccma_download_captions(subtitlepath, source_id)
                        if subtitles:
                            cur.execute(
                                f"UPDATE sources SET subtitlepath='{subtitles}', status_update=now() WHERE source_id = '{source_id}'")
                            print("CCMA: Caption fetching succeeded")
                else:
                    print("CCMA: Fetching failed: no audio")
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
        except KeyError as ke:
            print(f"YT: Fetching failed")
            if yt.age_restricted:
                print("YT: Fetching failed video with age restriction")
                cur.execute(f"UPDATE sources SET status='age_restricted', status_update=now() WHERE source_id = '{source_id}'")
            traceback.print_exc()
        except Exception as ex:
            print(f"Fetching failed")
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
