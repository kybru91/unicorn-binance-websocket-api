# TASKS.md — Development Backlog

Tasks collected from codebase analysis (2026-04-01). Ordered by priority within each group.

---

## High Priority

### [x] Remove DEX support
- Remove `binance.org` and `binance.org-testnet` from `connection_settings.py` (`Exchanges` enum, `DEX_EXCHANGES`, `CONNECTION_SETTINGS`)
- Remove all `if self.exchange == "binance.org"` branches in `sockets.py`, `manager.py`, `restclient.py`
- Remove `dex_user_address` from manager and `stream_list` dict
- Update `AGENTS.md` supported exchanges table
- Bump version

### [ ] Rebuild listen key handling — remove REST-based approach
- Current REST-based listen key ping (`_ping_listen_key` in `manager.py`) is obsolete
- Rebuild using the WebSocket-native approach
- Remove `restclient.keepalive_listen_key()` call path
- Affects: `manager.py:_ping_listen_key()`, `restclient.py`

### [x] Remove check_lucit_collector + Icinga support
- Removed `get_latest_release_info_check_command()`, `get_latest_version_check_command()`,
  `is_update_available_check_command()`, `get_monitoring_status_icinga()`,
  `start_monitoring_api()`, `stop_monitoring_api()`, `_start_monitoring_api_thread()`
- Removed `restserver.py` entirely
- Removed `flask`, `flask_restful`, `cheroot` dependencies
- Cleaned `get_monitoring_status_plain()` of all check_lucit references; method retained for programmatic use

### [x] Upgrade websockets + Python 3.14 support (GIL only — no-GIL in PR 3)
- Upgraded `websockets==11.0.3` → `>=14.0`
- Updated exception handling: `InvalidStatusCode` → `websockets.exceptions.InvalidStatus` with `.response.status_code`
- Added Python 3.14 to CI (`unit-tests.yml`) and wheel builds (`build_wheels.yml`)
- Dropped Python 3.8 (EOL), minimum is now 3.9
- Updated `setup.py`, `pyproject.toml`, `requirements.txt`, `environment.yml`, `meta.yaml`

### [ ] Add rate-limit backoff strategy (429 handling)
- Currently: 429 response from Binance crashes the stream (`manager.py:_run_socket()`)
- Implement exponential backoff before restart on 429
- Log clearly how long the backoff will be
- Consider a global rate-limit state shared across streams

---

## Medium Priority

### [ ] Replace stream_list dict entries with @dataclass
- `manager.py:_add_stream_to_stream_list()` — 30+ key raw dict per stream
- Create `StreamState` dataclass in new file `stream_state.py`
- Gives: type safety, IDE autocomplete, typo protection, easier refactoring
- No behavioral change required

### [ ] Fix linear request_id scan in sockets.py
- `sockets.py:174–186` — scans raw JSON string for each pending request_id as substring
- O(n×m), false-positive-prone, runs on every received message for WS API streams
- Fix: parse JSON once, extract `id` field directly, use dict lookup

### [ ] Modernize SOCKS5 proxy using websockets native support
- Current implementation in `connection.py` manually creates a `socks.socksocket()` (PySocks) and passes it
  via `sock=` to `websockets.connect()` — a low-level workaround
- websockets 14 supports proxies natively via the `proxy` parameter in `connect()`
- Replace the manual PySocks socket setup with `proxy="socks5://user:pass@host:port"` (or similar)
- Allows removing the manual `netloc` parsing, `host:port` split, and `socks.socksocket` setup in `__aenter__`
- May allow simplifying or removing the PySocks (`socks`) dependency

### [ ] Remove wildcard imports
- `from .exceptions import *` in `manager.py`, `connection.py`, `sockets.py`
- Replace with explicit imports
- Enables proper static analysis with mypy/pyright

---

## To Discuss

### [ ] GitHub update check — make async or lazy
- `__init__` currently makes a synchronous HTTP request to `api.github.com` on every instantiation
- Options: (a) move to background thread, (b) make lazy (only on first explicit call), (c) remove entirely
- Decision needed before implementing

---

## Done / Accepted as-is

- **Thread-per-stream model** — intentional design. Isolation allows killing a thread+loop atomically. Works well in practice.
- **API secrets in stream_list** — acceptable for a developer-facing library
- **SSL verification flag** — acceptable for a developer-facing library
