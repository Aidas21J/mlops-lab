import time, json, statistics as st, requests
from concurrent.futures import ThreadPoolExecutor


URL = "http://localhost:8008/predict"


def one(_):
    t = time.perf_counter()
    r = requests.post(URL, json={"message": "a surprisingly moving and funny film"}, timeout=5)
    r.raise_for_status()
    return (time.perf_counter() - t) * 1000


lat = [one(i) for i in range(100)]
p95 = st.quantiles(lat, n=100)[94]
t0 = time.perf_counter()

with ThreadPoolExecutor(10) as ex:
    list(ex.map(one, range(1000)))
    rps = 200 / (time.perf_counter() - t0)
    out = {"n": 100, "p50_ms": st.median(lat), "p95_ms": p95, "throughput_rps": rps}
    json.dump(out, open("docs/loadtest.json", "w"), indent=2); print(out)
