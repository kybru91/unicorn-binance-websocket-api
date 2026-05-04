# AGENTS.md — UNICORN Binance WebSocket API

> **End-user cheatsheet for AI-assisted consumption:** [`llms.txt`](llms.txt) — use that one if you're writing code *against* this library.
> **This file** is for AI agents working *on* this repo itself.

## Planning & Backlog

Open development tasks and decisions are tracked in **[TASKS.md](TASKS.md)**.

---

## Project Overview

Python SDK (MIT License) for connecting to Binance WebSocket streams. Enables multiplexed WebSocket connections, automatic buffering, reconnect handling, and WebSocket API calls (e.g. order placement).

**Current Version:** 2.13.0  
**Python Compatibility:** 3.9 – 3.14  
**Author:** Oliver Zehentleitner  
**PyPI:** `unicorn-binance-websocket-api`

---

## Directory Structure

```
unicorn_binance_websocket_api/     # Main package
    manager.py                     # Core class BinanceWebSocketApiManager (~4800 lines)
    connection.py                  # Individual WebSocket connections (asyncio)
    sockets.py                     # Socket implementation with stream processing
    restclient.py                  # REST client for stream management
    restserver.py                  # Flask REST server for external control
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
| `binance.us` | 1024 |
| `trbinance.com` | 1024 |

---

## Dependencies

Managed in `requirements.txt`, `setup.py`, and `pyproject.toml` — **all three must be kept in sync manually** (IDE find/replace):

- `websocket-client`, `websockets>=14.0` — WebSocket connections
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
- `build_conda.yml` — Conda package build

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
| `BinanceWebSocketApiRestServer` | `restserver.py` | Flask REST server |
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
