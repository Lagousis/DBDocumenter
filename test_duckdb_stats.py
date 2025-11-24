import duckdb

con = duckdb.connect(":memory:")
con.execute("CREATE TABLE t1 AS SELECT * FROM range(1000)")
con.execute("CREATE TABLE t2 AS SELECT * FROM range(500)")

print("Tables:")
print(con.execute("SELECT * FROM duckdb_tables()").fetchall())
print("Columns:")
print(con.execute("PRAGMA table_info('t1')").fetchall())

try:
    print("Storage info:")
    print(con.execute("PRAGMA storage_info('t1')").fetchall())
except Exception as e:
    print(e)
