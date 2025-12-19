import sqlite3

conn = sqlite3.connect("partyservice.db")
cur = conn.cursor()

for row in cur.execute("SELECT id, event_date, event_time FROM orders"):
    print(row)

conn.close()
