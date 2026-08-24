import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

conn = psycopg2.connect(host="localhost", port=5432, user="postgres", password="holora", dbname="postgres")
conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname='erp_sim'")
if cur.fetchone():
    cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='erp_sim' AND pid<>pg_backend_pid()")
    cur.execute("DROP DATABASE erp_sim")
    print("dropped existing erp_sim")
cur.execute("CREATE DATABASE erp_sim")
print("created erp_sim")
cur.close()
conn.close()
