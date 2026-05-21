#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: example_futures_userdata_events.py
#
# Part of 'UNICORN Binance WebSocket API'
# Project website: https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api
# Github: https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api
# Documentation: https://oliver-zehentleitner.github.io/unicorn-binance-websocket-api
# PyPI: https://pypi.org/project/unicorn-binance-websocket-api
#
# Author: Oliver Zehentleitner
#
# Copyright (c) 2019-2026, Oliver Zehentleitner
# (https://about.me/oliver-zehentleitner)
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
USDT-M Futures user-data stream with explicit event-type filtering.

Since 2026-04-23 the Binance USDⓈ-M Futures private WebSocket lives at
`wss://fstream.binance.com/private/ws?listenKey=...&events=...` and requires
an explicit `events` query parameter on production — without it the
connection succeeds but no payloads arrive.

UBWA subscribes to all documented event types by default (see
`BINANCE_FUTURES_USERDATA_EVENTS` in `connection_settings.py`). This example
shows the two common patterns:

  1. Default — receive every event type.
  2. Filter — restrict to a subset, e.g. order/account updates plus the
     mandatory `listenKeyExpired` housekeeping event.

For the authoritative list of event types, see:
https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams
"""

from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager
import logging
import os
import time


logging.basicConfig(level=logging.INFO,
                    filename=os.path.basename(__file__) + '.log',
                    format="{asctime} [{levelname:8}] {process} {thread} "
                           "{module}: {message}",
                    style="{")


API_KEY = os.getenv("BINANCE_FUTURES_API_KEY", "")
API_SECRET = os.getenv("BINANCE_FUTURES_API_SECRET", "")


def main():
    with BinanceWebSocketApiManager(exchange="binance.com-futures") as ubwa:
        # Pattern 1: default — subscribe to every documented event type.
        full_stream_id = ubwa.create_stream(
            channels=["arr"],
            markets=["!userData"],
            api_key=API_KEY,
            api_secret=API_SECRET,
            stream_label="futures-userdata-full",
        )

        # Pattern 2: filter — only the events this bot actually consumes.
        # `listenKeyExpired` should be in any filtered set because UBWA's
        # reconnect logic relies on it.
        filtered_stream_id = ubwa.create_stream(
            channels=["arr"],
            markets=["!userData"],
            api_key=API_KEY,
            api_secret=API_SECRET,
            events=["ORDER_TRADE_UPDATE", "ACCOUNT_UPDATE", "listenKeyExpired"],
            stream_label="futures-userdata-filtered",
        )

        try:
            while True:
                record = ubwa.pop_stream_data_from_stream_buffer()
                if record is None:
                    time.sleep(0.01)
                else:
                    print(record)
        except KeyboardInterrupt:
            print("\nStopping ...")


if __name__ == "__main__":
    main()
