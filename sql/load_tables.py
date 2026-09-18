#!/usr/bin/env python3
"""Load each staged parquet into a UC table via CTAS (read_files)."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import dbsql

CATALOG = os.environ.get("ACC_CATALOG", "deep_test_1_catalog")
VOL = f"/Volumes/{CATALOG}/acc_gold/staging/load"
OUT = Path(__file__).parent.parent / "data_gen" / "out"

pairs = []
for schema_dir in sorted(OUT.iterdir()):
    if not schema_dir.is_dir():
        continue
    for pq in sorted(schema_dir.glob("*.parquet")):
        pairs.append((schema_dir.name, pq.stem))

print(f"Loading {len(pairs)} tables...")
ok = 0
for schema, table in pairs:
    path = f"{VOL}/{schema}/{table}.parquet"
    sql = (
        f"CREATE OR REPLACE TABLE {CATALOG}.{schema}.{table} AS "
        f"SELECT * FROM read_files('{path}', format => 'parquet')"
    )
    try:
        dbsql.run(sql, catalog=CATALOG, quiet=True)
        cnt = dbsql.rows(f"SELECT count(*) FROM {CATALOG}.{schema}.{table}")[0][0]
        print(f"  ok  {schema}.{table}  ({cnt} rows)")
        ok += 1
    except Exception as e:
        print(f"  FAIL {schema}.{table}: {e}")
print(f"\nLoaded {ok}/{len(pairs)} tables.")
