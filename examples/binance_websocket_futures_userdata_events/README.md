# Binance USDⓈ-M Futures userData with Event Filter
## Overview
This example opens two USDⓈ-M Futures user data streams against `binance.com-futures` to demonstrate the `events`
parameter introduced for the new `/private/ws?listenKey=...&events=...` URL form (Binance announcement effective
2026-04-23).

* **Stream 1 (`UD_FullDefault`)** — no `events` argument, so UBWA subscribes to all event types listed in
  `BINANCE_FUTURES_USERDATA_EVENTS` (`ORDER_TRADE_UPDATE`, `ACCOUNT_UPDATE`, `MARGIN_CALL`, `TRADE_LITE`,
  `ACCOUNT_CONFIG_UPDATE`, `STRATEGY_UPDATE`, `GRID_UPDATE`, `CONDITIONAL_ORDER_TRIGGER_REJECT`,
  `ALGO_ORDER_UPDATE`, `listenKeyExpired`). This preserves the behaviour of the pre-2026-04-23 `/ws/<listenKey>`
  URL which streamed every event implicitly.
* **Stream 2 (`UD_Filtered`)** — `events=["ORDER_TRADE_UPDATE", "ACCOUNT_UPDATE", "listenKeyExpired"]`, the
  minimal subset for a typical execution bot. `listenKeyExpired` should be in any filtered set because UBWA's
  reconnect logic depends on it.

Authoritative list of event types:
[Binance USDⓈ-M Futures user data streams docs](https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams).

Names are not validated against an allow-list, so additional event types Binance introduces between UBWA releases
can be passed through immediately.

## Prerequisites
Ensure you have Python 3.9+ installed on your system.

Before running the provided script, install the required Python packages:
```bash
pip install -r requirements.txt
```

Edit the script and set `api_key` / `api_secret` to a Binance Futures API key with read access to the account
that should be observed.

## Usage
### Running the Script:
```bash
python binance_websocket_futures_userdata_events.py
```

Trigger an order on the account (e.g. via the REST API or the Binance UI) and you should see `ORDER_TRADE_UPDATE`
and `ACCOUNT_UPDATE` records arrive on both streams, while `TRADE_LITE` arrives only on `UD_FullDefault`.

### Graceful Shutdown:
The script is designed to handle a graceful shutdown upon receiving a KeyboardInterrupt (e.g., Ctrl+C) or
encountering an unexpected exception.

## Logging
The script employs logging to provide insights into its operation and to assist in troubleshooting. Logs are saved
to a file named after the script with a .log extension.

For further assistance or to report issues, please
[visit the GitHub repository](https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api).
