from time import sleep
from pytube import YouTube

import traceback

from db import get_connection
from utils import GracefulKiller

killer = GracefulKiller()

def get_youtube(source_id, url):
    print(f"YT: Checking language of {url} (id={source_id})")
    return YouTube(url)

conn = get_connection()

cur = conn.cursor()

print("Starting")
while not killer.kill_now:
    cur.execute("SELECT source_id, url \
    FROM sources \
    WHERE has_captions is null \
    ORDER BY random()  \
    LIMIT 1;")
    conn.commit()
    next = cur.fetchone()

    if next:
        source_id, url = next
        try:
            yt = get_youtube(source_id, url)
            captions = 'ca' in yt.captions
            print(f"Source {source_id} has captions? {captions}")
            cur.execute(f"UPDATE sources SET has_captions='{captions}' WHERE source_id = '{source_id}'")
        except Exception as ex:
            print(f"Preprocessing failed")
            traceback.print_exc()
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