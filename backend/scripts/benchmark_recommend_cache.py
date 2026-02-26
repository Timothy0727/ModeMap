"""
Benchmark /recommend: forced uncached (cache=0) vs cached (cache=1) across multiple locations.
"""

import statistics
import time

import requests

URL = "http://localhost:8000/recommend"
BASE_PARAMS = {
    "mode": "work",
    "radius": 2000,
    "open_now": "false",
    "max_results": 60,
}

LOCATIONS = [
    {"lat": 32.7157, "lng": -117.1611, "label": "San Diego"},
    {"lat": 37.7749, "lng": -122.4194, "label": "San Francisco"},
    {"lat": 40.7128, "lng": -74.0060, "label": "New York"},
    {"lat": 34.0522, "lng": -118.2437, "label": "Los Angeles"},
]

N = 20
TIMEOUT = 30


def measure(params: dict, n: int) -> tuple[list[float], dict[str, int]]:
    """Run n requests, return (list of latencies ms, X-Cache counts)."""
    times = []
    xcache: dict[str, int] = {"HIT": 0, "MISS": 0, "BYPASS": 0, "OTHER": 0}
    for _ in range(n):
        t0 = time.perf_counter()
        r = requests.get(URL, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        dt_ms = (time.perf_counter() - t0) * 1000
        times.append(dt_ms)
        val = r.headers.get("X-Cache", "OTHER")
        xcache[val] = xcache.get(val, 0) + 1
    return times, xcache


def summarize(xs: list[float]) -> dict:
    xs_sorted = sorted(xs)

    def pct(p: float) -> float:
        i = int(round((p / 100) * (len(xs_sorted) - 1)))
        return xs_sorted[i]

    return {
        "n": len(xs),
        "median_ms": statistics.median(xs),
        "mean_ms": statistics.mean(xs),
        "p95_ms": pct(95),
        "min_ms": min(xs),
        "max_ms": max(xs),
    }


def reduction(a: float, b: float) -> float:
    if a <= 0:
        return 0.0
    return (a - b) / a * 100.0


def main() -> None:
    print("=" * 60)
    print("RECOMMEND CACHE BENCHMARK")
    print("=" * 60)

    all_uncached: list[float] = []
    all_cached: list[float] = []
    xcache_uncached: dict[str, int] = {"HIT": 0, "MISS": 0, "BYPASS": 0, "OTHER": 0}
    xcache_cached: dict[str, int] = {"HIT": 0, "MISS": 0, "BYPASS": 0, "OTHER": 0}

    for loc in LOCATIONS:
        label = loc["label"]
        params_base = {**BASE_PARAMS, "lat": loc["lat"], "lng": loc["lng"]}

        # 1) Uncached block (cache=0)
        uncached_params = {**params_base, "cache": 0}
        uncached_times, unc_x = measure(uncached_params, N)
        unc = summarize(uncached_times)
        for k, v in unc_x.items():
            xcache_uncached[k] = xcache_uncached.get(k, 0) + v
        all_uncached.extend(uncached_times)

        # 2) Warm-up (fill cache for this location)
        warm_params = {**params_base, "cache": 1}
        requests.get(URL, params=warm_params, timeout=TIMEOUT).raise_for_status()

        # 3) Cached block (cache=1)
        cached_params = {**params_base, "cache": 1}
        cached_times, c_x = measure(cached_params, N)
        c = summarize(cached_times)
        for k, v in c_x.items():
            xcache_cached[k] = xcache_cached.get(k, 0) + v
        all_cached.extend(cached_times)

        # Per-location table
        red_med = reduction(unc["median_ms"], c["median_ms"])
        red_p95 = reduction(unc["p95_ms"], c["p95_ms"])
        print(f"\n--- {label} ---")
        print(f"  UNCACHED (cache=0)  {unc}  X-Cache: {unc_x}")
        print(f"  CACHED   (cache=1)  {c}  X-Cache: {c_x}")
        print(f"  Reduction median: {red_med:.1f}%  p95: {red_p95:.1f}%")

    # Pooled summary
    pool_unc = summarize(all_uncached)
    pool_c = summarize(all_cached)
    red_med_pool = reduction(pool_unc["median_ms"], pool_c["median_ms"])
    red_p95_pool = reduction(pool_unc["p95_ms"], pool_c["p95_ms"])

    print("\n" + "=" * 60)
    print("POOLED (all locations)")
    print("=" * 60)
    print(f"UNCACHED  n={pool_unc['n']}  median_ms={pool_unc['median_ms']:.1f}  p95_ms={pool_unc['p95_ms']:.1f}  X-Cache: {xcache_uncached}")
    print(f"CACHED    n={pool_c['n']}  median_ms={pool_c['median_ms']:.1f}  p95_ms={pool_c['p95_ms']:.1f}  X-Cache: {xcache_cached}")
    print(f"REDUCTION (median): {red_med_pool:.1f}%")
    print(f"REDUCTION (p95):    {red_p95_pool:.1f}%")


if __name__ == "__main__":
    main()
