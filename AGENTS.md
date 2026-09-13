# AGENTS.md — UNICORN Binance WebSocket API

> **End-user cheatsheet for AI-assisted consumption:** [`llms.txt`](llms.txt) — use that one if you're writing code *against* this library.
> **This file** is for AI agents working *on* this repo itself.

## Why things are the way they are

See [`context/index.md`](context/index.md) before making non-trivial changes — it points to the reasoning behind design decisions, rejected alternatives, and constraints that aren't visible in the code. If `AGENTS.local.md` exists in this repo, that's personal/local notes, not relevant to anyone else.

## Planning & Backlog

Open development tasks and decisions are tracked in **[TASKS.md](TASKS.md)**.

---

## Project Overview

Python SDK (MIT License) for connecting to Binance WebSocket streams. Enables multiplexed WebSocket connections, automatic buffering, reconnect handling, and WebSocket API calls (e.g. order placement).

**Current Version:** 2.15.2  
**Python Compatibility:** 3.9 – 3.14  
**Author:** Oliver Zehentleitner  
**PyPI:** `unicorn-binance-websocket-api`

---

## Directory Structure

```
unicorn_binance_websocket_api/     # Main package
    manager.py                     # Core class BinanceWebSocketApiManager (~4800 lines)
    connection.py                  # Individual WebSocket connections (asyncio)
    websocket_library.py           # websockets (default) vs. picows selection + exception families
    sockets.py                     # Socket implementation with stream processing
    restclient.py                  # REST client for stream management
    connection_settings.py         # Exchanges enum + connection parameters
    exceptions.py                  # Custom exceptions
    api/                           # WebSocket API (trading) for Spot & Futures

unittest_binance_websocket_api.py  # Unit tests (main test file, run in CI)
dev/                               # Local dev/integration tests — NOT run in CI
examples/                          # Usage examples (14 directories)
docs/                              # Pre-built HTML documentation (Sphinx)
```

---

## Supported Exchanges

Defined in `unicorn_binance_websocket_api/connection_settings.py` as the `Exchanges` enum:

| Exchange String | Max Subscriptions/Stream |
|---|---|
| `binance.com` | 1024 |
| `binance.com-testnet` | 1024 |
| `binance.com-margin` | 1024 |
| `binance.com-isolated_margin` | 1024 |
| `binance.com-futures` | 200 |
| `binance.com-coin_futures` | 200 |
| `binance.com-portfolio_margin` | 200 (listenKey/user-data streams only, see below) |
| `binance.us` | 1024 |
| `trbinance.com` | 1024 |

Portfolio Margin (`binance.com-portfolio_margin`) is scoped to the user data
stream lifecycle: `wss://fstream.binance.com/pm/ws/<listenKey>`, with the
listenKey acquired/kept-alive/closed via UBRA's PAPI methods
(`portfolio_margin_stream_get_listen_key()` etc.). Why it's scoped this way
and deliberately not part of `BINANCE_FUTURES_EXCHANGES`:
[`context/portfolio-margin.md`](context/portfolio-margin.md). See also
[issue #452](https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api/issues/452).

---

## Dependencies

Managed in `requirements.txt`, `setup.py`, and `pyproject.toml` — **all three must be kept in sync manually** (IDE find/replace):

- `websocket-client`, `websockets>=14.0` — WebSocket connections
- `picows>=2.2.0` — **optional** (extra `picows`), alternative WebSocket library via its
  `websockets`-compatible API; selected with `BinanceWebSocketApiManager(websocket_library="picows")`,
  see [`context/websocket-library.md`](context/websocket-library.md). Benchmark:
  `dev/test_websocket_library_benchmark.py`, profile of the stream thread:
  `dev/profile_stream_loop.py` (per-message cost of the loop itself, see
  [`context/stream-loop.md`](context/stream-loop.md)), 24 h soak against live Binance:
  `dev/test_soak.py`
- `requests>=2.31.0` — HTTP
- `orjson` — fast JSON serialization
- `unicorn-fy>=0.15.0` — stream data normalization
- `unicorn-binance-rest-api>=2.7.0` — REST API support
- `Cython` — C extension compilation (performance, release builds only)
- `PySocks` — SOCKS5 proxy support
- `psutil` — system info

---

## Running Tests

```bash
# Unit tests with coverage (this is what CI runs)
coverage run --source unicorn_binance_websocket_api unittest_binance_websocket_api.py

# Unit tests without coverage
python -m unittest unittest_binance_websocket_api.py
```

Tests in `dev/` are local integration tests that require a live Binance connection — they are **not run in CI**.

`TestWebSocketLibrary` in the unittest file runs its scenarios (reconnect, fragmentation, max_size, ping/pong,
rejected handshakes, WS API roundtrip, keepalive timeout) against a local stand-in server for both
`websocket_library` values; no internet needed, picows scenarios skip if picows isn't installed.

**Coverage config:** `.coveragerc` — excludes ~40 platform-specific and hard-to-test lines.

---

## Build & Packaging

Development and testing use **plain Python** — no Cython compilation needed during development.

Cython compilation only happens for **release builds**:

```bash
# Release: build wheel with Cython compilation
python setup.py bdist_wheel
```

**Version bump** — done **manually** before each release. Update the version string in all three locations:
1. `setup.py`
2. `pyproject.toml`
3. `unicorn_binance_websocket_api/__init__.py`

**CI/CD:** GitHub Actions in `.github/workflows/`
- `unit-tests.yml` — Python 3.8–3.13 on Ubuntu, Codecov upload
- `build_wheels.yml` — Manual trigger, builds wheels for Linux/macOS/Windows, PyPI release
- `codeql-analysis.yml` — Security scanning

No in-repo conda build — conda-forge's own feedstock is the only conda source (same as the rest of the suite; see `context/history.md`).

---

## Code Conventions

- **File header:** Always include the full MIT license block with author/copyright (2019-2026)
- **Encoding:** UTF-8, UNIX line endings
- **Logging:** `logging.getLogger("unicorn_binance_websocket_api")`
- **Type hints:** Present in key methods; `typing_extensions` for Python < 3.9
- **Cython:** Core modules compile to C extensions — no `#cython:` directives needed in source
- **Versioning:** Keep version in sync across `setup.py`, `pyproject.toml`, and `__init__.py` manually

---

## Key Classes

| Class | File | Purpose |
|---|---|---|
| `BinanceWebSocketApiManager` | `manager.py` | Main class, inherits from `threading.Thread` |
| `BinanceWebSocketApiConnection` | `connection.py` | Individual WS connection (asyncio) |
| `BinanceWebSocketApiSocket` | `sockets.py` | Stream processing |
| `BinanceWebSocketApiRestclient` | `restclient.py` | REST client |
| `WsApi` | `api/api.py` | Trading via WebSocket (Spot & Futures) |
| `Exchanges` | `connection_settings.py` | Enum of all supported exchanges |

---

## Usage Patterns (Quick Reference)

```python
from unicorn_binance_websocket_api import BinanceWebSocketApiManager

# Stream buffer pattern
ubwa = BinanceWebSocketApiManager(exchange="binance.com")
ubwa.create_stream(channels=['trade', 'kline_1m'], markets=['btcusdt'])
while True:
    data = ubwa.pop_stream_data_from_stream_buffer()

# Callback pattern
def process_data(stream_data):
    print(stream_data)
ubwa.create_stream(channels=['trade'], markets=['btcusdt'], process_stream_data=process_data)

# Asyncio queue pattern
async def main():
    stream_id = ubwa.create_stream(channels=['trade'], markets=['btcusdt'])
    async with ubwa.get_stream_data_from_asyncio_queue(stream_id) as data:
        print(data)
```

Keep the Why's config for this project migrated to .keep-the-why on
2026-09-04 — requires skill version 0.10.0 or later to read it.
