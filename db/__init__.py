from os import getenv
import psycopg2

PG_HOST = getenv("PG_HOST", "localhost")
PG_DATABASE = getenv("PG_DATABASE", "datapipe")
PG_USERNAME = getenv("PG_USERNAME", "datapipe")
PG_PASSWORD = getenv("PG_PASSWORD")

def get_connection():
 return psycopg2.connect(f"host={PG_HOST} port=5432 dbname={PG_DATABASE} user={PG_USERNAME} password={PG_PASSWORD}")