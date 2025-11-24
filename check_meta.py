
import duckdb

con = duckdb.connect()
con.execute("CREATE TABLE test (a INTEGER)")
con.execute("INSERT INTO test VALUES (1), (2), (3)")
print(con.execute("DESCRIBE SELECT * FROM duckdb_tables()").fetchall())
print("-" * 20)
print(con.execute("SELECT * FROM duckdb_tables()").fetchall())
