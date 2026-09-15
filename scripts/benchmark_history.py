"""Repeatable synthetic SQL benchmark. Only writes to a temporary directory."""
import json
import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from electrical_mcp.store import Store

QUERY = '''SELECT payload FROM readings
WHERE company=? AND device=? AND metric=? AND timestamp>=? AND timestamp<=?
ORDER BY timestamp DESC, id DESC LIMIT ?'''
PARAMS = ('bench', 'meter', 'temperature', '2020', '2100', 20)


def main():
    with tempfile.TemporaryDirectory() as directory:
        store = Store(str(Path(directory)/'benchmark.db'))
        epoch = datetime(2026,1,1,tzinfo=timezone.utc)
        samples = [{'metric':'temperature' if i % 1000 == 0 else 'power', 'value':float(i),
                    'timestamp':(epoch+timedelta(seconds=i)).isoformat()} for i in range(30000)]
        store.save_readings('bench','meter',samples)
        with store.connect() as db:
            def timing():
                timings = []
                for _ in range(30):
                    start = time.perf_counter()
                    result = db.execute(QUERY,PARAMS).fetchall()
                    timings.append((time.perf_counter()-start)*1000)
                return statistics.median(timings), [r['payload'] for r in result]
            db.execute('DROP INDEX readings_metric_lookup')
            before, expected = timing()
            db.execute('CREATE INDEX readings_metric_lookup ON readings(company,device,metric,timestamp DESC,id DESC)')
            after, actual = timing()
            assert expected == actual
            print(json.dumps({'rows':30000,'repetitions':30,'returned_samples':len(actual),
                'baseline_median_ms':round(before,4),'indexed_median_ms':round(after,4),
                'query_plan':[r['detail'] for r in db.execute('EXPLAIN QUERY PLAN '+QUERY,PARAMS)],
                'note':'Synthetic warm-cache single-query benchmark; not end-to-end factory performance.'},indent=2))

if __name__ == '__main__':
    main()
