from os import getenv
from time import sleep
import psycopg2
from pytube import YouTube

PG_HOST = getenv("PG_HOST", "localhost")
PG_DATABASE = getenv("PG_DATABASE", "datapipe")
PG_USERNAME = getenv("PG_USERNAME", "datapipe")
PG_PASSWORD = getenv("PG_PASSWORD")

def youtube_download(source_id, url):
    try:
        print(f"YT: Fetching {url} (id={source_id})")
        yt = YouTube(url)
        stream = yt.streams.filter(only_audio=True).order_by("abr").last()
        ext = stream.default_filename.split('.')[-1]
        stream.download("./media", f"{source_id}.{ext}", None)
    except Exception as ex:
        print("Failed to fetch")


conn = psycopg2.connect(f"host={PG_HOST} port=5432 dbname={PG_DATABASE} user={PG_USERNAME} password={PG_PASSWORD}")

cur = conn.cursor()

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

while True:
    next = cur.fetchone()

    if next:
        source_id, url, type = next
        if type == "youtube":
            youtube_download(source_id, url)
        else:
            print(f"Unknown source type {type}!")
    else:
        break

cur.close()
conn.close()