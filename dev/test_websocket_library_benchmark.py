#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: dev/test_websocket_library_benchmark.py
#
# Part of ‘UNICORN Binance WebSocket API’
# Project website: https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api
# Github: https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api
# Documentation: https://oliver-zehentleitner.github.io/unicorn-binance-websocket-api
# PyPI: https://pypi.org/project/unicorn-binance-websocket-api
#
# Author: Oliver Zehentleitner
#
# Copyright (c) 2019-2026, Oliver Zehentleitner (https://about.me/oliver-zehentleitner)
# All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish, dis-
# tribute, sublicense, and/or sell copies of the Software, and to permit
# persons to whom the Software is furnished to do so, subject to the fol-
# lowing conditions:
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

"""
Benchmark: `websockets` vs. `picows` as UBWA's WebSocket client library.

Not part of CI (dev/ only). Two modes:

1. Local replay (default) - deterministic, measures the raw receive path
   through the whole UBWA stack (connection -> sockets -> callback). A picows
   based server in a *separate process* pushes pre-serialized Binance-style
   messages as fast as it can, so the client process' CPU time is the client's
   alone. Scenarios differ in message size (aggTrade ~200 B ... !ticker@arr
   ~500 KB) plus a multiplex mix, each repeated `--repeat` times, median is
   reported.

2. Live (`--live SECONDS`) - both libraries subscribe to the same heavy
   multiplex on binance.com one after the other. Message rate is dictated by
   the exchange, so the comparable number is CPU time per received message.

3. Raw libraries (`--raw-libs`) - same local replay, but `websockets` /
   `picows.websockets` are driven directly (`async for msg in ws`) without
   UBWA. The gap between this and mode 1 is UBWA's own per-message overhead.

Known artifact of the local replay (see context/websocket-library.md,
"Benchmark results"): the server is a firehose on loopback, it never paces.
Once the client is slower than the wire (UBWA with messages >= ~32 KB), the
kernel receive buffer autotunes into the megabytes and picows drains it in
one multi-MB recv per loop iteration into its ever-growing read buffer,
while websockets reads at most 256 KB per recv. That per-byte penalty makes
picows 4-12 % slower than websockets through UBWA for big messages even
though picows wins standalone at every size. `--rcvbuf BYTES` caps
SO_RCVBUF on the client socket (both libraries) to approximate a WAN link
where the socket buffer never fills like that; with 131072 picows is ahead
at every size. The default stays the firehose so numbers remain comparable
with earlier runs.

Usage:
    python3 dev/test_websocket_library_benchmark.py
    python3 dev/test_websocket_library_benchmark.py --output dict --repeat 5
    python3 dev/test_websocket_library_benchmark.py --raw-libs
    python3 dev/test_websocket_library_benchmark.py --rcvbuf 131072
    python3 dev/test_websocket_library_benchmark.py --live 120
    python3 dev/test_websocket_library_benchmark.py --markdown results.md
"""

import os
import sys

# Prefer the repo checkout over an installed (possibly Cython compiled) UBWA
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unicorn_binance_websocket_api.manager import (
    BinanceWebSocketApiManager,
)  # noqa: E402
import argparse
import asyncio
import logging
import multiprocessing
import random
import socket
import statistics
import threading
import time
import urllib.parse

import orjson

import unicorn_binance_websocket_api.connection as ubwa_connection  # noqa: E402

logging.getLogger("unicorn_binance_websocket_api").setLevel(logging.ERROR)

LIBRARIES = ("websockets", "picows")
PORT = 18766


# --------------------------------------------------------------------------- #
# Message generators (Binance shaped JSON)
# --------------------------------------------------------------------------- #
def _price():
    return f"{random.uniform(20000, 70000):.2f}"


def _qty():
    return f"{random.uniform(0.0001, 5):.5f}"


def _ts():
    return int(time.time() * 1000)


def msg_aggtrade(i):
    return {
        "stream": "btcusdt@aggTrade",
        "data": {
            "e": "aggTrade",
            "E": _ts(),
            "s": "BTCUSDT",
            "a": 1000000 + i,
            "p": _price(),
            "q": _qty(),
            "f": 2000000 + i,
            "l": 2000000 + i,
            "T": _ts(),
            "m": bool(i % 2),
            "M": True,
        },
    }


def msg_kline(i):
    return {
        "stream": "btcusdt@kline_1m",
        "data": {
            "e": "kline",
            "E": _ts(),
            "s": "BTCUSDT",
            "k": {
                "t": _ts(),
                "T": _ts() + 59999,
                "s": "BTCUSDT",
                "i": "1m",
                "f": 100 + i,
                "L": 200 + i,
                "o": _price(),
                "c": _price(),
                "h": _price(),
                "l": _price(),
                "v": _qty(),
                "n": 100 + i,
                "x": False,
                "q": _qty(),
                "V": _qty(),
                "Q": _qty(),
                "B": "0",
            },
        },
    }


def msg_depth20(i):
    return {
        "stream": "btcusdt@depth20@100ms",
        "data": {
            "lastUpdateId": 5000000000 + i,
            "bids": [[_price(), _qty()] for _ in range(20)],
            "asks": [[_price(), _qty()] for _ in range(20)],
        },
    }


def msg_depth_diff(i, levels=200):
    return {
        "stream": "btcusdt@depth",
        "data": {
            "e": "depthUpdate",
            "E": _ts(),
            "s": "BTCUSDT",
            "U": 5000000000 + i,
            "u": 5000000000 + i + levels,
            "b": [[_price(), _qty()] for _ in range(levels)],
            "a": [[_price(), _qty()] for _ in range(levels)],
        },
    }


def msg_ticker_arr(i, symbols=1400):
    return {
        "stream": "!ticker@arr",
        "data": [
            {
                "e": "24hrTicker",
                "E": _ts(),
                "s": f"SYM{n:04d}USDT",
                "p": _price(),
                "P": "1.234",
                "w": _price(),
                "x": _price(),
                "c": _price(),
                "Q": _qty(),
                "b": _price(),
                "B": _qty(),
                "a": _price(),
                "A": _qty(),
                "o": _price(),
                "h": _price(),
                "l": _price(),
                "v": _qty(),
                "q": _qty(),
                "O": _ts(),
                "C": _ts(),
                "F": 1 + i,
                "L": 2 + i,
                "n": 3 + i,
            }
            for n in range(symbols)
        ],
    }


# name -> (generator, number of messages per run)
SCENARIOS = {
    "small_aggtrade": (msg_aggtrade, 300_000),
    "medium_kline": (msg_kline, 150_000),
    "large_depth20": (msg_depth20, 60_000),
    "xlarge_depth_diff": (msg_depth_diff, 30_000),
    "huge_ticker_arr": (msg_ticker_arr, 600),
    "multiplex_mix": (None, 120_000),
}
MULTIPLEX_WEIGHTS = (
    (msg_aggtrade, 60),
    (msg_kline, 20),
    (msg_depth20, 18),
    (msg_depth_diff, 2),
)
POOL_SIZE = 500  # distinct pre-serialized messages per scenario
RCVBUF = None  # `--rcvbuf`: SO_RCVBUF for the client socket, None = kernel default


def client_socket(port):
    """Connected, non-blocking client socket with SO_RCVBUF set before connect
    (after connect the kernel keeps autotuning). Passed as `sock=` to either
    library's `connect()`."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RCVBUF)
    sock.connect(("127.0.0.1", port))
    sock.setblocking(False)
    return sock


def install_rcvbuf_hook(port):
    """Make UBWA's connections use `client_socket()`: the manager has no socket
    hook, so the library `connect()` UBWA resolves via `get_connect()` is
    wrapped here (dev script only)."""
    original_get_connect = ubwa_connection.get_connect

    def get_connect(websocket_library):
        connect = original_get_connect(websocket_library)

        def connect_with_rcvbuf(uri, **kwargs):
            return connect(uri, sock=client_socket(port), **kwargs)

        return connect_with_rcvbuf

    ubwa_connection.get_connect = get_connect


def build_pool(scenario):
    random.seed(42)
    generator, _ = SCENARIOS[scenario]
    pool = []
    for i in range(POOL_SIZE):
        if generator is None:
            gen = random.choices(
                [g for g, _ in MULTIPLEX_WEIGHTS], [w for _, w in MULTIPLEX_WEIGHTS]
            )[0]
        else:
            gen = generator
        pool.append(orjson.dumps(gen(i)))
    return pool


# --------------------------------------------------------------------------- #
# Replay server (separate process, picows raw API = fastest sender available)
# --------------------------------------------------------------------------- #
def server_process(port, ready):
    import picows

    pools = {}

    class Listener(picows.WSListener):
        def __init__(self, request):
            path = (
                request.path.decode()
                if isinstance(request.path, bytes)
                else request.path
            )
            query = urllib.parse.urlparse(path).query
            streams = urllib.parse.parse_qs(query).get("streams", [""])[0]
            # UBWA URI: /stream?streams=<market>@<channel> -> market = scenario
            self.scenario = streams.split("@")[0].split("/")[0]
            self.transport = None
            self.task = None

        def on_ws_connected(self, transport):
            self.transport = transport
            self.task = asyncio.get_running_loop().create_task(self.pump())

        async def pump(self):
            if self.scenario not in SCENARIOS:
                return
            if self.scenario not in pools:
                pools[self.scenario] = build_pool(self.scenario)
            pool = pools[self.scenario]
            _, count = SCENARIOS[self.scenario]
            transport = self.transport
            n = len(pool)
            for i in range(count):
                if transport.is_disconnected:
                    return
                transport.send(picows.WSMsgType.TEXT, pool[i % n])
                if i % 200 == 0:
                    # let the transport flush, keep the socket buffer honest
                    await asyncio.sleep(0)
            # keep the connection open until the client leaves

        def on_ws_frame(self, transport, frame):
            if frame.msg_type == picows.WSMsgType.TEXT:
                # answer subscribe/unsubscribe payloads like Binance does
                try:
                    request_id = orjson.loads(frame.get_payload_as_bytes())["id"]
                    transport.send(
                        picows.WSMsgType.TEXT,
                        orjson.dumps({"result": None, "id": request_id}),
                    )
                except (KeyError, ValueError, TypeError):
                    pass
            elif frame.msg_type == picows.WSMsgType.CLOSE:
                transport.send_close(frame.get_close_code(), frame.get_close_message())
                transport.disconnect()

        def on_ws_disconnected(self, transport):
            if self.task is not None:
                self.task.cancel()

    async def main():
        server = await picows.ws_create_server(
            lambda request: Listener(request), "127.0.0.1", port, enable_auto_pong=True
        )
        ready.set()
        async with server:
            await server.serve_forever()

    asyncio.run(main())


# --------------------------------------------------------------------------- #
# Client side measurement
# --------------------------------------------------------------------------- #
class Counter:
    def __init__(self, target):
        self.target = target
        self.count = 0
        self.bytes = 0
        self.first = None
        self.last = None
        self.done = threading.Event()

    def __call__(self, data):
        now = time.perf_counter()
        if self.first is None:
            self.first = now
        self.count += 1
        if isinstance(data, (str, bytes)):
            self.bytes += len(data)
        if self.count >= self.target:
            self.last = now
            self.done.set()


def run_local(library, scenario, output, port):
    """One measurement: returns dict with wall/cpu/msgs/bytes."""
    _, count = SCENARIOS[scenario]
    counter = Counter(count)
    ubwa = BinanceWebSocketApiManager(
        exchange="binance.com",
        websocket_library=library,
        websocket_base_uri=f"ws://127.0.0.1:{port}/",
        output_default=output,
        process_stream_data=counter,
        warn_on_update=False,
        disable_colorama=True,
        # the local server never pings back -> disable keepalive noise
        ping_interval_default=None,
        ping_timeout_default=None,
    )
    cpu_start = time.process_time()
    ubwa.create_stream(["bench"], [scenario])
    finished = counter.done.wait(timeout=600)
    cpu = time.process_time() - cpu_start
    ubwa.stop_manager()
    if not finished:
        raise RuntimeError(
            f"{library}/{scenario}: only {counter.count}/{count} messages"
        )
    wall = counter.last - counter.first
    return {
        "library": library,
        "scenario": scenario,
        "output": output,
        "messages": counter.count,
        "wall_s": wall,
        "cpu_s": cpu,
        "msgs_per_s": counter.count / wall,
        "cpu_us_per_msg": cpu / counter.count * 1e6,
    }


def run_raw_library(library, scenario, port):
    """Same replay without UBWA: the library's own receive loop."""
    _, count = SCENARIOS[scenario]
    if library == "picows":
        from picows.websockets import connect
    else:
        from websockets import connect
    uri = f"ws://127.0.0.1:{port}/stream?streams={scenario}@bench"

    connect_kwargs = {}
    if RCVBUF is not None:
        connect_kwargs["sock"] = client_socket(port)

    async def consume():
        received = 0
        first = None
        async with connect(uri, ping_interval=None, **connect_kwargs) as ws:
            async for _ in ws:
                if first is None:
                    first = time.perf_counter()
                received += 1
                if received >= count:
                    return received, time.perf_counter() - first

    cpu_start = time.process_time()
    received, wall = asyncio.run(consume())
    cpu = time.process_time() - cpu_start
    return {
        "library": library,
        "scenario": scenario,
        "output": "raw library, no UBWA",
        "messages": received,
        "wall_s": wall,
        "cpu_s": cpu,
        "msgs_per_s": received / wall,
        "cpu_us_per_msg": cpu / received * 1e6,
    }


def run_live(library, seconds, output):
    """Live binance.com multiplex: rate is exchange-driven, compare CPU/msg."""
    counter = Counter(target=sys.maxsize)
    ubwa = BinanceWebSocketApiManager(
        exchange="binance.com",
        websocket_library=library,
        output_default=output,
        process_stream_data=counter,
        warn_on_update=False,
        disable_colorama=True,
    )
    markets = [
        "btcusdt",
        "ethusdt",
        "bnbusdt",
        "solusdt",
        "xrpusdt",
        "dogeusdt",
        "adausdt",
        "avaxusdt",
        "linkusdt",
        "dotusdt",
        "maticusdt",
        "ltcusdt",
        "trxusdt",
        "shibusdt",
        "uniusdt",
        "atomusdt",
        "etcusdt",
        "xlmusdt",
        "nearusdt",
        "aptusdt",
    ]
    ubwa.create_stream(
        ["aggTrade", "trade", "bookTicker", "depth20@100ms", "kline_1m"], markets
    )
    ubwa.create_stream(["arr"], ["!ticker", "!miniTicker"])
    ubwa.create_stream(["depth"], markets[:10])
    # let all streams connect before measuring
    time.sleep(10)
    count0, bytes0 = counter.count, counter.bytes
    cpu0 = time.process_time()
    t0 = time.perf_counter()
    time.sleep(seconds)
    wall = time.perf_counter() - t0
    cpu = time.process_time() - cpu0
    messages = counter.count - count0
    received_bytes = counter.bytes - bytes0
    ubwa.stop_manager()
    return {
        "library": library,
        "scenario": f"live_{seconds}s",
        "output": output,
        "messages": messages,
        "wall_s": wall,
        "cpu_s": cpu,
        "msgs_per_s": messages / wall,
        "cpu_us_per_msg": cpu / max(messages, 1) * 1e6,
        "mb_per_s": received_bytes / wall / 1e6,
        "cpu_pct": cpu / wall * 100,
    }


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def median_of(results, key):
    return statistics.median(r[key] for r in results)


def report_local(all_results, output, title="Local replay"):
    lines = []
    lines.append(f"### {title} (`{output}`, median of repeats)")
    lines.append("")
    lines.append(
        "| Scenario | ~msg size | msgs | websockets msgs/s | picows msgs/s | picows speedup | websockets CPU µs/msg | picows CPU µs/msg |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for scenario in SCENARIOS:
        rows = {
            lib: [
                r
                for r in all_results
                if r["library"] == lib and r["scenario"] == scenario
            ]
            for lib in LIBRARIES
        }
        if not all(rows.values()):
            continue
        pool = build_pool(scenario)
        size = statistics.median(len(m) for m in pool)
        ws_rate = median_of(rows["websockets"], "msgs_per_s")
        pw_rate = median_of(rows["picows"], "msgs_per_s")
        ws_cpu = median_of(rows["websockets"], "cpu_us_per_msg")
        pw_cpu = median_of(rows["picows"], "cpu_us_per_msg")
        lines.append(
            f"| {scenario} | {size/1024:.1f} KB | {SCENARIOS[scenario][1]:,} | {ws_rate:,.0f} | {pw_rate:,.0f} | "
            f"{pw_rate/ws_rate:.2f}x | {ws_cpu:.1f} | {pw_cpu:.1f} |"
        )
    return "\n".join(lines)


def report_live(results, output):
    lines = [f"### Live binance.com multiplex (`output_default='{output}'`)", ""]
    lines.append("| Library | msgs/s | MB/s | CPU % of one core | CPU µs/msg |")
    lines.append("|---|---|---|---|---|")
    for r in results:
        lines.append(
            f"| {r['library']} | {r['msgs_per_s']:,.0f} | {r['mb_per_s']:.2f} | {r['cpu_pct']:.1f} | {r['cpu_us_per_msg']:.1f} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--output", default="raw_data", choices=["raw_data", "dict"])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--scenarios", nargs="*", default=list(SCENARIOS))
    parser.add_argument("--live", type=int, default=0, metavar="SECONDS")
    parser.add_argument(
        "--raw-libs",
        action="store_true",
        help="drive the libraries directly, without UBWA",
    )
    parser.add_argument("--markdown", metavar="FILE", help="append the report to FILE")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--rcvbuf",
        type=int,
        metavar="BYTES",
        help="SO_RCVBUF of the client socket (local replay only), e.g. 131072; "
        "see the module docstring for why",
    )
    args = parser.parse_args()
    if args.rcvbuf:
        global RCVBUF
        RCVBUF = args.rcvbuf
        install_rcvbuf_hook(args.port)

    import platform, websockets, picows
    from unicorn_binance_websocket_api.manager import __version__ as ubwa_version

    header = (
        f"Python {platform.python_version()} on {platform.system()} {platform.machine()}, "
        f"websockets {websockets.__version__}, picows {picows.__version__}, "
        f"UBWA {ubwa_version}"
        + (f", client SO_RCVBUF {args.rcvbuf}" if args.rcvbuf else "")
    )
    print(header)
    reports = [header, ""]

    if args.live:
        live_results = []
        for library in LIBRARIES:
            print(f"live {library} for {args.live}s ...", flush=True)
            r = run_live(library, args.live, args.output)
            print(
                f"  {r['messages']} msgs, {r['msgs_per_s']:.0f} msgs/s, CPU {r['cpu_pct']:.1f}%, {r['cpu_us_per_msg']:.1f} µs/msg"
            )
            live_results.append(r)
        reports.append(report_live(live_results, args.output))
    else:
        ready = multiprocessing.Event()
        server = multiprocessing.Process(
            target=server_process, args=(args.port, ready), daemon=True
        )
        server.start()
        ready.wait(10)
        all_results = []
        try:
            for scenario in args.scenarios:
                for repeat in range(args.repeat):
                    # alternate libraries within a repeat to spread thermal/scheduling drift
                    for library in (
                        LIBRARIES if repeat % 2 == 0 else reversed(LIBRARIES)
                    ):
                        if args.raw_libs:
                            r = run_raw_library(library, scenario, args.port)
                        else:
                            r = run_local(library, scenario, args.output, args.port)
                        all_results.append(r)
                        print(
                            f"{scenario:18s} {library:10s} run {repeat+1}: {r['msgs_per_s']:>10,.0f} msgs/s  "
                            f"{r['cpu_us_per_msg']:6.1f} µs CPU/msg  wall {r['wall_s']:.2f}s",
                            flush=True,
                        )
        finally:
            server.terminate()
        if args.raw_libs:
            reports.append(
                report_local(
                    all_results,
                    "raw library, no UBWA",
                    title="Local replay, libraries only",
                )
            )
        else:
            reports.append(report_local(all_results, f"output_default='{args.output}'"))

    report = "\n".join(reports)
    print("\n" + report)
    if args.markdown:
        with open(args.markdown, "a") as f:
            f.write(report + "\n\n")


if __name__ == "__main__":
    main()
