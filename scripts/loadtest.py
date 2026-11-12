import json
import statistics as st
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8008"
PAYLOAD = {"message": "a surprisingly moving and funny film"}
SEQUENTIAL, CONCURRENT, WORKERS, WARMUP = 100, 200, 10, 10

session = requests.Session()


def one(_=None) -> float:
    t = time.perf_counter()
    r = session.post(f"{BASE}/predict", json=PAYLOAD, timeout=10)
    r.raise_for_status()
    return (time.perf_counter() - t) * 1000


def pct(values, p):
    return st.quantiles(values, n=100)[p - 1]


for _ in range(WARMUP):  # warm-up, not measured
    one()

lat = [one() for _ in range(SEQUENTIAL)]

t0 = time.perf_counter()
with ThreadPoolExecutor(WORKERS) as ex:
    list(ex.map(one, range(CONCURRENT)))
rps = CONCURRENT / (time.perf_counter() - t0)

result = {
    "model_version": session.get(f"{BASE}/health", timeout=5).json().get("model_version"),
    "sequential_requests": SEQUENTIAL,
    "p50_ms": round(st.median(lat), 2),
    "p95_ms": round(pct(lat, 95), 2),
    "p99_ms": round(pct(lat, 99), 2),
    "max_ms": round(max(lat), 2),
    "concurrent_requests": CONCURRENT,
    "concurrent_workers": WORKERS,
    "throughput_rps": round(rps, 1),
}
with open("docs/loadtest.json", "w") as f:
    json.dump(result, f, indent=2)
print(json.dumps(result, indent=2))
