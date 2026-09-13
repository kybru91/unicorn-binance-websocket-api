# WebSocket library: `websockets` (default) or `picows`

## Integrated via `picows.websockets`, not via the picows core API

**Type:** decision
**Status:** active
**Evidence:** confirmed
**Source:** maintainer instruction for the feature ("compatibility mode to the websockets API"), branch `feature/websocket-library-picows`, PR #475

`BinanceWebSocketApiManager(websocket_library="picows")` swaps the transport
for the whole manager instance. The integration goes through
`picows.websockets` (picows >= 2.0.0), a drop-in replacement of the
`websockets` client API: same `connect()` signature, same `recv()`/`send()`/
`close()` on the connection object, same exception names. All the selection
logic lives in `unicorn_binance_websocket_api/websocket_library.py`;
`connection.py` only asks it for the `connect()` callable and `manager.py`
catches both exception families. `sockets.py` (the stream loop) is untouched.

**Reason:** the stream loop is written against the `websockets` API -
`await recv()` wrapped in `asyncio.wait_for()`, one coroutine per stream in
its own thread/event loop. Reusing that path means zero duplicated stream
logic and no second code path to keep in sync. Chosen as the first step
explicitly; a native integration was to be *assessed*, not built (next entry).

**Version floor `picows>=2.2.0`**: 2.2.0 is the first release whose
`InvalidStatus.response` is the `websockets`-shaped `Response` with
`status_code` ([tarasko/picows#108](https://github.com/tarasko/picows/issues/108),
fixed 2026-09-11, verified against 2.2.0 by the scenario suite). Before that
the floor was 2.1.0 rather than 2.0.0 (where `picows.websockets` first
appeared) because 2.1.0 completed the compat surface (`open`/`closed`
attributes, `protocol.State`, `WebSocketClientProtocol` alias) - UBWA does
not use those today, the floor bought the complete API in case it does.
Raising to 2.2.0 keeps that and removes the need to handle two response
shapes.

## Native picows core API (`ws_connect()` + `WSListener`) - measured, not built

**Type:** decision
**Status:** active
**Evidence:** confirmed
**Source:** maintainer decision 2026-09-10 after the raw measurement below; benchmark `dev/test_websocket_library_benchmark.py` (`--raw-libs`) plus an ad-hoc core-API listener run against the same replay server
**Revisit when:** picows changes how `picows.websockets` sits on the core API (e.g. a zero-copy or batched `recv()`), or UBWA's own per-message overhead has been cut so far that the transport dominates again

The alternative to the compat layer was a push-model integration on picows'
core API: `ws_connect()` with a `WSListener` whose `on_ws_frame()` does the
dispatch directly, no `recv()` queue, no coroutine wake-up per message.

**Measured, raw (no UBWA), same replay server, median of 3:**

| Scenario | core API | `picows.websockets` | `websockets` |
|---|---|---|---|
| aggTrade 0.2 KB | 485k msgs/s, 2.02 µs | 499k msgs/s, 1.95 µs | 338k msgs/s, 2.96 µs |
| depth20 1 KB | 441k msgs/s, 2.20 µs | 451k msgs/s, 2.18 µs | 294k msgs/s, 3.42 µs |
| depth diff 9 KB | 271k msgs/s, 3.65 µs | 240k msgs/s, 4.04 µs | 149k msgs/s, 6.77 µs |

**Reason:** the core API brings no measurable throughput over
`picows.websockets` for UBWA's pattern - one Python callback per frame costs
the same as one coroutine wake-up out of the Cython queue that
`picows.websockets` uses internally. picows' headline gains are against
`websockets`, not against its own compat layer. Inside UBWA the transport is
~2 of ~6 µs per message, so even the 13 % seen at 9 KB would be under 5 %
end to end. An earlier assumption in this file (1-1.5 µs of wake-up cost
recoverable) was wrong and is superseded by this measurement.

**Rejected alternative:** building it anyway (as a third `websocket_library`
value) for the push model's side benefits - `frame.payload_size` instead of
`sys.getsizeof(str())`, a watchdog task removing the stop latency on idle
streams. Rejected because it means a second connection implementation
(~300-400 lines: frame reassembly, close handling, handshake-error mapping,
own send and watchdog tasks, async-callback bridging) to maintain, and both
side benefits are reachable inside the existing pull loop.

**Consequence:** `websocket_library` stays a two-value switch
(`"websockets"`, `"picows"`). The performance lever, if wanted, is UBWA's own
per-message work - see `stream-loop.md`.

## picows stays opt-in and non-default; 24 h soak before the release

**Type:** decision
**Status:** active
**Evidence:** confirmed
**Source:** maintainer decisions 2026-09-10 (opt-in after the scenario suite of PR #479 and the upstream report [tarasko/picows#108](https://github.com/tarasko/picows/issues/108); soak requested the same day, release only after it)
**Revisit when:** the first opt-in users have reported back in #477 - then decide about promoting picows beyond opt-in (the soak gate below is passed, #108 is fixed in picows 2.2.0 and the floor raised)

picows support ships as an optional extra (`pip install
unicorn-binance-websocket-api[picows]`), selected explicitly per manager,
`websockets` remains the default. The local scenario suite and short live
runs cover the integration; what they do not cover is time: hours against
real Binance maintenance windows and the 24 h connection limit, memory over
time. That gap is closed by a 24 h soak (`dev/test_soak.py`: `!ticker@arr`
+ `!miniTicker@arr`, five channels on the top 50 USDT markets, `depth@100ms`
on 20 of them, both libraries in parallel on the same host, metrics once a
minute) before the release that ships picows support.

**Reason:** the remaining risk sits with users who opt in knowingly, the
default path is untouched, and picows' compat layer itself is still moving
(#108, fixed upstream within a day). Real usage is expected to surface the next issues; the community
channel is [issue #477](https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api/issues/477). The
soak is the minimum evidence for "runs for a day" before telling anyone to
opt in.

**Not covered by the soak:** userData streams and the WebSocket API against
real credentials (no testnet key on the soak host), macOS/Windows.

**Soak result (measured 2026-09-10 22:41 → 2026-09-11 22:41 CEST, 8 cores /
12 GB VM, Python 3.13.5, picows 2.1.3, websockets 16.0):** clean for both
libraries, no picows-specific finding. picows 138.8 M messages (avg 1.6 k/s,
peak 8.3 k/s, 49.9 GB), RSS 62 → 126 MB, CPU avg 9.5 %; websockets 137.9 M
messages, RSS 63 → 149 MB, CPU avg 12.8 %. Zero errors, zero stalls (max
5 s without data), zero unrepairable streams, zero ERROR/WARNING lines.
Reconnects: 2 / 80 / 2 (picows) vs 2 / 88 / 2 (websockets) on the
arr / markets / depth streams, every one back in 5-6 s with subscriptions
re-queued. 90 % of them were `keepalive ping timeout` on the 250-subscription
markets connection during a 14:29-18:21 CEST window in which the rate rose
to 3-8 k msgs/s; both libraries dropped in the same seconds, so the cause is
Binance/network under load against UBWA's `ping_interval=5` /
`ping_timeout=10` defaults, not the library. RSS stepped up at rate peaks and
was flat for the final 4.5 h despite further reconnects - buffer high-water
mark, not a per-reconnect leak (pattern evidence, no tracemalloc). Full
tables in the soak output directory (`REPORT.md`).

## Why the picows exception classes are caught separately

**Type:** constraint
**Status:** active
**Evidence:** confirmed
**Source:** `picows/websockets/exceptions.py` (picows 2.1.3)

`picows.websockets.exceptions.ConnectionClosed` & co. are *not* subclasses of
the `websockets` exception classes, they only share the names. The manager's
restart logic therefore catches tuples
(`CONNECTION_CLOSED_EXCEPTIONS`, ...) built in `websocket_library.py`; the
picows classes are appended only when the package is importable.

## `InvalidStatus.response` differed between the families (picows < 2.2.0)

**Type:** workaround
**Status:** superseded
**Evidence:** confirmed
**Source:** picows 2.1.3 `picows/websockets/asyncio/client.py` (`raise InvalidStatus(exc.response)` with the raw `WSUpgradeResponse`); found by `TestWebSocketLibrary.test_handshake_429_crashes_stream`; superseded by picows 2.2.0 ([tarasko/picows#108](https://github.com/tarasko/picows/issues/108) fixed 2026-09-11) and the version floor `picows>=2.2.0`

Superseded: since the extra requires picows 2.2.0, both families attach a
`Response` with `status_code` and `get_http_status_code()` reads that
attribute only. The helper stays as the single place the manager gets the
code from (returns `None` instead of raising when the shape is unexpected),
the `status` fallback is gone. History below.

The manager decides on a rejected handshake by HTTP status (429 -> crash the
stream, anything else -> restart). `websockets` puts a `Response` with
`status_code` on `InvalidStatus`; `picows.websockets` puts picows' raw
`WSUpgradeResponse` there, which only has `status` (an `HTTPStatus`).
Reading `.status_code` therefore raised `AttributeError` inside the
`except` clause and the stream thread died silently, no status update, no
restart - the exact failure mode the fail-loud rule exists to prevent.
`websocket_library.get_http_status_code()` reads either attribute; the
manager uses it instead of touching the response directly.

**Rejected alternative:** catching the picows exception separately and
mapping it before the shared handler. More code for the same outcome, and
the next attribute difference would need the same treatment again; one
accessor that knows both shapes is the smaller surface.

## Fail loud on `picows` without the package

**Type:** decision
**Status:** active
**Evidence:** confirmed

Selecting `"picows"` without the optional dependency raises `ImportError`,
an unknown value raises `ValueError` - no silent fallback to `websockets`.
Follows the suite-wide "fail loud" rule: a deployment that thinks it runs
picows but silently runs websockets is a hidden configuration bug.

## SOCKS5 proxy path is shared

**Type:** decision
**Status:** active
**Evidence:** confirmed
**Source:** maintainer confirmation 2026-09-10; picows 2.1.3 source (`picows/websockets/asyncio/client.py`, `picows/api.py`); [tarasko/picows#80](https://github.com/tarasko/picows/pull/80); verified locally with a SOCKS5 server + TLS endpoint for both libraries
**Revisit when:** picows' proxy support matures (HTTPS proxies in #80 land, or its SOCKS path is declared stable) - then re-evaluate whether the picows mode should use the native `proxy=` path

Both libraries get the pre-connected PySocks socket via `sock=` +
`server_hostname=` (UBWA's existing SOCKS5 handling). For picows the
`proxy=None` kwarg is passed explicitly on that path, because
`picows.websockets.connect()` defaults to `proxy=True` (environment
`wss_proxy`/`https_proxy` lookup) and would otherwise attempt a second proxy
hop over the already tunneled socket (confirmed by the picows source).

**Reason:** picows is the optional mode; its proxy handling is still moving
(HTTPS proxies are a draft, the approach was being reworked in #80 at the
time of writing). The proxy path in the picows mode is therefore allowed to
evolve with the library instead of being fixed now - sharing UBWA's PySocks
path keeps behaviour, error mapping (`Socks5ProxyConnectionError`) and
configuration identical for both libraries until picows has settled.

**Rejected alternative (for now):** picows' own proxy support
(`proxy="socks5://..."` via python-socks, async, no PySocks). Not rejected
on merit - deferred until picows' proxy support is stable.

## Benchmark results

**Type:** constraint
**Status:** active
**Evidence:** confirmed
**Source:** `dev/test_websocket_library_benchmark.py`, run on the branch 2026-09-10

The numbers below are measured (confirmed). The "Reading" section is the
interpretation and is inferred, not separately measured - see the note there.

Setup: `dev/test_websocket_library_benchmark.py`, Python 3.13.5, x86_64 Linux
(4 cores), websockets 16.0, picows 2.1.3 with aiofastnet 1.1.0 present (a
picows dependency; picows uses it for `create_connection` automatically when
importable, so the picows numbers include it), UBWA 2.15.2.dev. A picows based
replay server in a separate process pushes pre-serialized Binance shaped
messages as fast as it can; "CPU µs/msg" is the client process' CPU time
(`time.process_time()`) divided by messages, so the server's cost is
excluded. 3 runs each, median.

**Libraries driven directly (`async for msg in ws`, no UBWA):**

| Scenario | ~msg size | msgs | websockets msgs/s | picows msgs/s | picows speedup | websockets CPU µs/msg | picows CPU µs/msg |
|---|---|---|---|---|---|---|---|
| small_aggtrade | 0.2 KB | 300,000 | 326,982 | 493,206 | 1.51x | 3.1 | 2.0 |
| medium_kline | 0.3 KB | 150,000 | 316,559 | 491,393 | 1.55x | 3.2 | 2.0 |
| large_depth20 | 1.0 KB | 60,000 | 280,948 | 465,901 | 1.66x | 3.6 | 2.2 |
| xlarge_depth_diff | 9.1 KB | 30,000 | 143,760 | 283,667 | 1.97x | 7.0 | 3.5 |
| huge_ticker_arr | 453.9 KB | 600 | 5,842 | 6,698 | 1.15x | 172.5 | 140.7 |
| multiplex_mix | 0.2 KB | 120,000 | 304,762 | 470,529 | 1.54x | 3.3 | 2.1 |

**Through UBWA, `output_default="raw_data"` (callback receives the JSON string) - before the stream-loop optimization (see `stream-loop.md`):**

| Scenario | ~msg size | msgs | websockets msgs/s | picows msgs/s | picows speedup | websockets CPU µs/msg | picows CPU µs/msg |
|---|---|---|---|---|---|---|---|
| small_aggtrade | 0.2 KB | 300,000 | 116,314 | 163,406 | 1.40x | 8.7 | 6.2 |
| medium_kline | 0.3 KB | 150,000 | 112,815 | 158,541 | 1.41x | 9.0 | 6.4 |
| large_depth20 | 1.0 KB | 60,000 | 96,835 | 135,253 | 1.40x | 10.5 | 7.8 |
| xlarge_depth_diff | 9.1 KB | 30,000 | 50,746 | 51,629 | 1.02x | 20.2 | 20.0 |
| huge_ticker_arr | 453.9 KB | 600 | 1,753 | 1,597 | 0.91x | 615.9 | 676.9 |
| multiplex_mix | 0.2 KB | 120,000 | 110,738 | 153,079 | 1.38x | 9.2 | 6.7 |

**Through UBWA, `output_default="dict"` (plus `orjson.loads()`) - before the stream-loop optimization:**

| Scenario | ~msg size | msgs | websockets msgs/s | picows msgs/s | picows speedup | websockets CPU µs/msg | picows CPU µs/msg |
|---|---|---|---|---|---|---|---|
| small_aggtrade | 0.2 KB | 300,000 | 108,738 | 146,053 | 1.34x | 9.3 | 6.9 |
| medium_kline | 0.3 KB | 150,000 | 101,532 | 135,117 | 1.33x | 10.0 | 7.5 |
| large_depth20 | 1.0 KB | 60,000 | 79,148 | 100,820 | 1.27x | 13.1 | 10.4 |
| xlarge_depth_diff | 9.1 KB | 30,000 | 22,118 | 23,302 | 1.05x | 46.1 | 43.2 |
| huge_ticker_arr | 453.9 KB | 600 | 357 | 397 | 1.11x | 2871.3 | 2617.6 |
| multiplex_mix | 0.2 KB | 120,000 | 86,168 | 113,088 | 1.31x | 11.8 | 9.0 |

**Through UBWA, `output_default="raw_data"` - after the stream-loop optimization (same day, same machine):**

| Scenario | ~msg size | msgs | websockets msgs/s | picows msgs/s | picows speedup | websockets CPU µs/msg | picows CPU µs/msg |
|---|---|---|---|---|---|---|---|
| small_aggtrade | 0.2 KB | 300,000 | 201,912 | 403,316 | 2.00x | 5.1 | 2.5 |
| medium_kline | 0.3 KB | 150,000 | 195,460 | 371,019 | 1.90x | 5.2 | 2.9 |
| large_depth20 | 1.0 KB | 60,000 | 153,187 | 259,960 | 1.70x | 6.8 | 4.1 |
| xlarge_depth_diff | 9.1 KB | 30,000 | 64,172 | 67,972 | 1.06x | 16.3 | 15.4 |
| huge_ticker_arr | 453.9 KB | 600 | 1,768 | 1,662 | 0.94x | 608.7 | 641.0 |
| multiplex_mix | 0.2 KB | 120,000 | 180,406 | 334,188 | 1.85x | 5.7 | 3.2 |

**Through UBWA, `output_default="dict"` - after the stream-loop optimization:**

| Scenario | ~msg size | msgs | websockets msgs/s | picows msgs/s | picows speedup | websockets CPU µs/msg | picows CPU µs/msg |
|---|---|---|---|---|---|---|---|
| small_aggtrade | 0.2 KB | 300,000 | 172,638 | 296,252 | 1.72x | 5.9 | 3.4 |
| medium_kline | 0.3 KB | 150,000 | 153,152 | 248,954 | 1.63x | 6.7 | 4.1 |
| large_depth20 | 1.0 KB | 60,000 | 108,547 | 152,108 | 1.40x | 9.6 | 7.0 |
| xlarge_depth_diff | 9.1 KB | 30,000 | 24,308 | 25,582 | 1.05x | 42.0 | 39.4 |
| huge_ticker_arr | 453.9 KB | 600 | 394 | 421 | 1.07x | 2572.1 | 2465.9 |
| multiplex_mix | 0.2 KB | 120,000 | 134,163 | 202,423 | 1.51x | 7.7 | 5.1 |

**Live binance.com, 20 symbol multiplex + `!ticker@arr`/`!miniTicker@arr` + 10x `depth`, 60 s each, sequential:**

| Library | msgs/s | MB/s | CPU % of one core | CPU µs/msg |
|---|---|---|---|---|
| websockets | 441 | 0.20 | 8.7 | 198.1 |
| picows | 306 | 0.16 | 6.1 | 199.2 |

**Reading (inferred):**

- Small and medium messages (<= ~1 KB, the bulk of Binance traffic): picows
  ~1.4x throughput and ~30 % less CPU per message inside UBWA. Standalone the
  libraries are 1.5x-2x apart.
- >= ~10 KB (full `depth` diffs, `!ticker@arr`): parity inside UBWA (0.9x-1.1x,
  within run-to-run noise). Plausible cause, not profiled: UTF-8 decoding of
  the payload plus UBWA's substring checks (`"error" in ...`,
  `"result" in ...`) over the whole message dominate, and both libraries pay
  the same for that.
- Before the stream-loop optimization UBWA added a constant ~5 µs per
  message on top of either library (3.1 -> 8.7 µs for websockets,
  2.0 -> 6.2 µs for picows). After it (`stream-loop.md`) the overhead is
  ~0.5 µs with picows and ~2 µs with websockets, and the picows advantage
  inside UBWA grew from 1.4x to 1.7x-2x for messages up to 1 KB.
- Live at a few hundred msgs/s the numbers are identical (~198 µs CPU/msg for
  both) because the manager's fixed overhead (monitoring loops, per-stream
  event loops, keepalive) dominates; message rate differs between the two
  windows only because market activity differs. Library choice only matters
  for high-throughput consumers or CPU-bound hosts.

## Benchmark design choices

**Type:** decision
**Status:** active
**Evidence:** confirmed
**Source:** `dev/test_websocket_library_benchmark.py` docstring and code

Three choices a reader of the numbers should know, all deliberate:

- The replay server runs in a **separate process** and uses the **raw picows
  server API**, so the client process' CPU time is the client's alone and the
  sender is faster than either client (a websockets-based server in the same
  process would cap both clients at the same rate and blur the comparison).
- Messages are **pre-serialized** (a pool of 500 per scenario) so the server
  never pays JSON encoding in the hot loop.
- **CPU µs per message** is reported next to msgs/s because in live mode the
  rate is set by the exchange; CPU per message is the only number that is
  comparable across two live windows. Library order alternates per repeat to
  spread scheduling drift. The live figure still contains the manager's fixed
  idle cost (monitoring loops, keepalive), which is why it is ~200 µs/msg at
  a few hundred msgs/s versus ~6-9 µs in the replay - it is not a per-message
  cost of the transport.
