from os import getenv
from time import sleep
from urllib.error import HTTPError

import json
import requests
import traceback

from db import get_connection
from utils import GracefulKiller

from pytube import YouTube
from pytube.innertube import _default_clients

_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID"]

killer = GracefulKiller()

API_TOKEN = getenv("API_TOKEN")
API_URL = getenv("API_URL", "https://api-inference.huggingface.co/models/ivanlau/language-detection-fine-tuned-on-xlm-roberta-base")
headers = {"Authorization": f"Bearer {API_TOKEN}"}
SKIP_LICENSE_CHECK = getenv("SKIP_LICENSE_CHECK", 'False').lower() in ('true', '1', 't')

youtube_wait = 5

class NoProbsException(Exception):
    """No probabilities returned"""
    pass

def get_highest_prop(probs):
    highest = probs[0]
    for i in range(1, len(probs)):
        if probs[i]['score'] > highest['score']:
            highest = probs[i]
        if highest['score'] > 0.5:
            break
    return highest

def check_language(text):
    data = json.dumps({"inputs":text})
    response = requests.request("POST", API_URL, headers=headers, data=data)
    language_probs = json.loads(response.content.decode("utf-8"))
    if not language_probs or response.status_code != 200:
        raise NoProbsException
    catalan_prob = language_probs[0][3]['score']
    print(f"{language_probs[0][3]['label']}: {catalan_prob}")
    spanish_prob = language_probs[0][38]['score']
    print(f"{language_probs[0][38]['label']}: {spanish_prob}")
    
    if spanish_prob > 0.9:
        return False
    if catalan_prob > 0.5:
        return True
    
    highest_prob = get_highest_prop(language_probs[0])
    print(f"Highest probability for {highest_prob['label']}: {highest_prob['score']}")
    if len(text) > 100 and highest_prob['label'] == "English" and highest_prob['score'] > 0.9: 
        return False

    # We let it through and will check the individual clips
    return True

def get_youtube(source_id, url):
    print(f"YT: Checking language of {url} (id={source_id})")
    return YouTube(url)

def youtube_language_check(yt):
    text = f"{yt.title}. {yt.description}"
    return check_language(text[:1000])


def youtube_license_check(yt):
    metadata = json.dumps(yt.metadata.raw_metadata)
    return "creative commons" in metadata.lower()


conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute("UPDATE sources SET status='checking_language', status_update=now() \
    WHERE source_id = ( \
    SELECT source_id \
    FROM sources \
    WHERE status='new' \
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
                new_status = "ready_for_download" if youtube_language_check(yt) else "bad_language"
                if new_status == "bad_language":
                    print(f"Bad language: {url}")
                license = "CC-BY" if youtube_license_check(yt) else "PROP"
                if license == "PROP" and not SKIP_LICENSE_CHECK:
                    print(f"Bad licence (not CC-BY): {url} ")
                    new_status = "bad_license"
                captions = 'ca' in yt.captions
                cur.execute(f"UPDATE sources SET status='{new_status}', license='{license}', has_captions='{captions}', status_update=now() WHERE source_id = '{source_id}'")
            except HTTPError as err:
                print(f"HTTP Error {err}")
                cur.execute(f"UPDATE sources SET status='new', status_update=now() WHERE source_id = '{source_id}'")
                conn.commit()
                if err.code == 429:
                    print("Too Many requests, waiting 1 hour")
                    youtube_wait += 5
                    sleep(3600)
            except KeyboardInterrupt:
                print("Stopping")
                cur.execute(f"UPDATE sources SET status='new', status_update=now() WHERE source_id = '{source_id}'")
                conn.commit()
                break
            except Exception as ex:
                print(f"Preprocessing failed")
                traceback.print_exc()
                cur.execute(f"UPDATE sources SET status='new', status_update=now() WHERE source_id = '{source_id}'")
            finally:
                conn.commit()
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