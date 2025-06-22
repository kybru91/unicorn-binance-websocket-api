#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: unicorn_binance_websocket_api/connection_settings.py
#
# Part of ‘UNICORN Binance WebSocket API’
# Project website: https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api
# Github: https://github.com/oliver-zehentleitner/unicorn-binance-websocket-api
# Documentation: https://oliver-zehentleitner.github.io/unicorn-binance-websocket-api
# PyPI: https://pypi.org/project/unicorn-binance-websocket-api
#
# License: MIT
# https://github.com/oliver-zehentleitner/unicorn-binance-rest-api/blob/master/LICENSE
#
# Author: Oliver Zehentleitner
#
# Copyright (c) 2019-2025, Oliver Zehentleitner (https://about.me/oliver-zehentleitner)
#
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
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABIL-
# ITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHOR BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from enum import Enum

import sys
if sys.version_info >= (3, 9):
    from typing import Type
    MAX_SUBSCRIPTIONS_PER_STREAM: Type[int] = int
    WEBSOCKET_BASE_URI: Type[str] = str
    WEBSOCKET_API_BASE_URI: Type[str] = str
else:
    MAX_SUBSCRIPTIONS_PER_STREAM = int
    WEBSOCKET_BASE_URI = str
    WEBSOCKET_API_BASE_URI = str


class Exchanges(str, Enum):
    BINANCE = "binance.com"
    BINANCE_TESTNET = "binance.com-testnet"
    BINANCE_MARGIN = "binance.com-margin"
    BINANCE_MARGIN_TESTNET = "binance.com-margin-testnet"
    BINANCE_ISOLATED_MARGIN = "binance.com-isolated_margin"
    BINANCE_ISOLATED_MARGIN_TESTNET = "binance.com-isolated_margin-testnet"
    BINANCE_FUTURES = "binance.com-futures"
    BINANCE_COIN_FUTURES = "binance.com-coin_futures"
    BINANCE_FUTURES_TESTNET = "binance.com-futures-testnet"
    BINANCE_US = "binance.us"
    TRBINANCE = "trbinance.com"
    BINANCE_ORG = "binance.org"
    BINANCE_ORG_TESTNET = "binance.org-testnet"


DEX_EXCHANGES = [Exchanges.BINANCE_ORG, Exchanges.BINANCE_ORG_TESTNET]
CEX_EXCHANGES = [
    Exchanges.BINANCE,
    Exchanges.BINANCE_TESTNET,
    Exchanges.BINANCE_MARGIN,
    Exchanges.BINANCE_MARGIN_TESTNET,
    Exchanges.BINANCE_ISOLATED_MARGIN,
    Exchanges.BINANCE_ISOLATED_MARGIN_TESTNET,
    Exchanges.BINANCE_FUTURES,
    Exchanges.BINANCE_COIN_FUTURES,
    Exchanges.BINANCE_FUTURES_TESTNET,
    Exchanges.BINANCE_US,
    Exchanges.TRBINANCE,
]

# only python 3.9+
# CONNECTION_SETTINGS: dict[str, Tuple[MAX_SUBSCRIPTIONS_PER_STREAM, WEBSOCKET_BASE_URI, WEBSOCKET_API_BASE_URI]] = {

CONNECTION_SETTINGS = {
    Exchanges.BINANCE: (1024, "wss://stream.binance.com:9443/", "wss://ws-api.binance.com/ws-api/v3"),
    Exchanges.BINANCE_TESTNET: (1024, "wss://testnet.binance.vision/", "wss://testnet.binance.vision/ws-api/v3"),
    Exchanges.BINANCE_MARGIN: (1024, "wss://stream.binance.com:9443/", None),
    Exchanges.BINANCE_MARGIN_TESTNET: (1024, "wss://testnet.binance.vision/", None),
    Exchanges.BINANCE_ISOLATED_MARGIN: (1024, "wss://stream.binance.com:9443/", None),
    Exchanges.BINANCE_ISOLATED_MARGIN_TESTNET: (1024, "wss://testnet.binance.vision/", None),
    Exchanges.BINANCE_FUTURES: (200, "wss://fstream.binance.com/", "wss://ws-fapi.binance.com/ws-fapi/v1"),
    Exchanges.BINANCE_FUTURES_TESTNET: (200, "wss://stream.binancefuture.com/", "wss://testnet.binancefuture.com/ws-fapi/v1"),
    Exchanges.BINANCE_COIN_FUTURES: (200, "wss://dstream.binance.com/", None),
    Exchanges.BINANCE_US: (1024, "wss://stream.binance.us:9443/", None),
    Exchanges.TRBINANCE: (1024, "wss://stream-cloud.trbinance.com/", None),
    Exchanges.BINANCE_ORG: (1024, "wss://dex.binance.org/api/", None),
    Exchanges.BINANCE_ORG_TESTNET: (1024, "wss://testnet-dex.binance.org/api/", None),
}
