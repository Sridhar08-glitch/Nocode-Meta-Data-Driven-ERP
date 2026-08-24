"""READ-ONLY observation helper for validation. SELECT statements ONLY."""
import psycopg2
def _conn():
    con = psycopg2.connect(host="localhost", user="postgres", password="holora", dbname="nexus_sim")
    con.set_session(readonly=True, autocommit=True); return con
def q(sql, params=None):
    con=_conn()
    try:
        cur=con.cursor()
        cur.execute(sql, params) if params else cur.execute(sql)
        return cur.fetchall()
    finally: con.close()
def scalar(sql, params=None):
    r=q(sql, params); return r[0][0] if r else None
