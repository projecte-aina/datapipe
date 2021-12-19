from os import getenv
from youtubesearchpython import CustomSearch

import psycopg2
from psycopg2.extras import Json

PG_HOST = getenv("PG_HOST", "localhost")
PG_DATABASE = getenv("PG_DATABASE", "datapipe")
PG_USERNAME = getenv("PG_USERNAME", "datapipe")
PG_PASSWORD = getenv("PG_PASSWORD")

conn = psycopg2.connect(f"host={PG_HOST} port=5432 dbname={PG_DATABASE} user={PG_USERNAME} password={PG_PASSWORD}")

cur = conn.cursor()

cs = CustomSearch("ple ordinari", "EgIwAQ%3D%3D", 50, 'ca', 'ES')

res = cs.result()

counter = 0

while True:
    for video in res['result']:
        link = video['link']
        print(video['title'])
        print(f"Checking if source {link} exists in DB")
        cur.execute(f"SELECT 1 FROM sources WHERE url='{link}'")
        db_result = cur.fetchone()
        if db_result:
            print("Source exists, skipping")
        else:
            print("Source does not exist, adding")
            cur.execute("INSERT INTO sources (url, type, metadata) VALUES (%s,%s, %s)", (link, "youtube", Json(video)))
    conn.commit()
    next = cs._next() or False
    if not next or counter > 50:
        break
    res = cs.result()
    counter += 1

cur.close()
conn.close()