#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ¯\_(ツ)_/¯
#
# File: unicorn_binance_websocket_api/websocket_library.py
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
# Copyright (c) 2019-2026, Oliver Zehentleitner (https://about.me/oliver-zehentleitner)
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

from .exceptions import *

"""
Selection of the underlying WebSocket client library.

UBWA talks to the WebSocket library exclusively through the `websockets`
client API (`connect()`, `recv()`, `send()`, `close()` and the exception
classes). `picows` ships a drop-in replacement of that API in its
`picows.websockets` subpackage (picows >= 2.0.0), so supporting it is a
matter of picking the right `connect()` and catching both exception
families. This module is the single place where that choice is made.
"""

from typing import Callable, Optional, Tuple, Type
import logging
import websockets
import websockets.exceptions

try:
    import picows
    import picows.websockets as picows_websockets
except ImportError:  # picows is an optional dependency
    picows = None
    picows_websockets = None

__logger__: logging.getLogger = logging.getLogger("unicorn_binance_websocket_api")

logger = __logger__

WEBSOCKET_LIBRARY_WEBSOCKETS: str = "websockets"
WEBSOCKET_LIBRARY_PICOWS: str = "picows"
SUPPORTED_WEBSOCKET_LIBRARIES: Tuple[str, ...] = (
    WEBSOCKET_LIBRARY_WEBSOCKETS,
    WEBSOCKET_LIBRARY_PICOWS,
)


def _exception_tuple(name: str) -> Tuple[Type[BaseException], ...]:
    """
    Build a tuple with the `websockets` exception class of the given name plus
    the `picows.websockets` equivalent if picows is installed. The picows
    classes are NOT subclasses of the `websockets` ones, so both have to be
    caught explicitly.
    """
    classes = [getattr(websockets.exceptions, name)]
    if picows_websockets is not None:
        classes.append(getattr(picows_websockets.exceptions, name))
    return tuple(classes)


CONNECTION_CLOSED_EXCEPTIONS = _exception_tuple("ConnectionClosed")
INVALID_STATUS_EXCEPTIONS = _exception_tuple("InvalidStatus")
INVALID_MESSAGE_EXCEPTIONS = _exception_tuple("InvalidMessage")
NEGOTIATION_ERROR_EXCEPTIONS = _exception_tuple("NegotiationError")


def get_http_status_code(error: BaseException) -> Optional[int]:
    """
    HTTP status of a rejected handshake (`InvalidStatus` of either family),
    `None` when the exception carries no usable response.

    Both families attach a `Response` with `status_code` (picows since 2.2.0,
    the version floor of the extra; 2.1.x attached the raw `WSUpgradeResponse`
    without it, see tarasko/picows#108). The manager decides crash vs.
    restart from this code and must never die on the shape of the exception.
    """
    response = getattr(error, "response", None)
    code = getattr(response, "status_code", None)
    if code is None:
        return None
    try:
        return int(code)
    except (TypeError, ValueError):
        return None


def is_picows_available() -> bool:
    return picows_websockets is not None


def validate_websocket_library(websocket_library: Optional[str]) -> str:
    """
    Validate the `websocket_library` value passed to the manager and return the
    normalized name. Fails loud on unknown values and on `picows` without the
    package installed - a silent fallback to `websockets` would hide a broken
    deployment.

    :raises ValueError: unknown library name
    :raises ImportError: `picows` selected but not installed
    """
    if websocket_library is None:
        return WEBSOCKET_LIBRARY_WEBSOCKETS
    if websocket_library not in SUPPORTED_WEBSOCKET_LIBRARIES:
        raise ValueError(
            f"Unknown websocket_library '{websocket_library}'! Supported: "
            f"{', '.join(SUPPORTED_WEBSOCKET_LIBRARIES)}"
        )
    if websocket_library == WEBSOCKET_LIBRARY_PICOWS and not is_picows_available():
        raise ImportError(
            "websocket_library='picows' requested, but the optional dependency "
            "`picows` is not installed. Install it with: "
            "pip install unicorn-binance-websocket-api[picows]"
        )
    return websocket_library


def get_websocket_library_version(websocket_library: str) -> str:
    if websocket_library == WEBSOCKET_LIBRARY_PICOWS:
        return picows.__version__
    return websockets.__version__


def get_connect(websocket_library: str) -> Callable:
    """
    Return the `connect()` callable of the selected library. Both share the
    same call signature and return an async context manager yielding a
    connection object with `recv()`, `send()` and `close()`.
    """
    if websocket_library == WEBSOCKET_LIBRARY_PICOWS:
        return picows_websockets.connect
    return websockets.connect
