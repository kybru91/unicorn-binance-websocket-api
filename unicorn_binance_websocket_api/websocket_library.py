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
from urllib.parse import quote, unquote, urlparse
import ssl
import logging
import websockets
import websockets.exceptions

try:
    import picows
    import picows.websockets as picows_websockets
except ImportError:  # picows is an optional dependency
    picows = None
    picows_websockets = None

try:
    # Dependency of picows; carries the proxy errors of picows' native proxy
    # path (`connect(proxy="socks5://...")`).
    import python_socks
except ImportError:
    python_socks = None

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

# Raised while the connection is entered when the proxy hop fails: the
# libraries' own `ProxyError` (`websockets` wraps python-socks failures and
# HTTP CONNECT rejections, picows the CONNECT ones), `InvalidProxy` (proxy URL
# the library cannot use) and python-socks' errors, which picows lets through
# on its SOCKS path. UBWA maps all of them to `ProxyConnectionError`.
PROXY_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    _exception_tuple("ProxyError")
    + _exception_tuple("InvalidProxy")
    + (
        (
            python_socks.ProxyError,
            python_socks.ProxyConnectionError,
            python_socks.ProxyTimeoutError,
        )
        if python_socks is not None
        else ()
    )
)

SUPPORTED_PROXY_SCHEMES: Tuple[str, ...] = (
    "http",
    "https",
    "socks4",
    "socks4a",
    "socks5",
    "socks5h",
)


def validate_proxy_url(proxy: Optional[str]) -> Optional[str]:
    """
    Check a `proxy` URL for `BinanceWebSocketApiManager(proxy=...)` and return
    it unchanged, `None` for `None`. Raises `ValueError` for anything the
    libraries cannot use (unknown scheme, missing host), so a typo fails at
    construction time instead of in every stream's restart loop.

    Schemes: `http://`, `https://` (TLS to the proxy itself), `socks4://`,
    `socks4a://`, `socks5://`, `socks5h://` (hostname resolved by the proxy).
    Credentials go into the URL (`socks5://user:pass@host:1080`), percent-
    encoded if they contain `@`, `:` or `/`.
    """
    if proxy is None:
        return None
    if not isinstance(proxy, str) or not proxy:
        raise ValueError(f"`proxy` must be a URL string, got {proxy!r}")
    parsed = urlparse(proxy)
    if parsed.scheme not in SUPPORTED_PROXY_SCHEMES:
        raise ValueError(
            f"Unsupported proxy scheme {parsed.scheme!r} in {proxy!r}, "
            f"supported: {', '.join(f'{scheme}://' for scheme in SUPPORTED_PROXY_SCHEMES)}"
        )
    if not parsed.hostname:
        raise ValueError(f"`proxy` URL {proxy!r} has no host")
    try:
        parsed.port
    except ValueError as error_msg:
        raise ValueError(f"`proxy` URL {proxy!r}: {error_msg}")
    return proxy


def check_proxy_credentials(websocket_library: str, proxy: Optional[str]) -> None:
    """
    Fail loud on proxy credentials the selected library would send wrongly.

    `websockets` (checked up to 16.0) passes `username`/`password` of the
    proxy URL to the proxy *without* percent-decoding them, so a password
    that had to be encoded to fit into the URL (`p@ss` -> `p%40ss`) arrives
    as the literal `p%40ss` and is rejected (reported upstream:
    python-websockets/websockets, see context/websocket-library.md).
    `picows` decodes (python-socks does it for it). Rather than letting the
    stream restart forever on an authentication error, refuse such
    credentials for `websockets` at construction time.
    """
    if proxy is None or websocket_library == WEBSOCKET_LIBRARY_PICOWS:
        return
    parsed = urlparse(proxy)
    for name, value in (("user", parsed.username), ("password", parsed.password)):
        if value is not None and unquote(value) != value:
            raise ValueError(
                f"The proxy {name} contains characters that need percent-encoding in a URL, but "
                f"`websockets` sends proxy credentials without decoding them (upstream limitation), "
                f'so this proxy login cannot work with websocket_library="websockets". Use '
                f"credentials without `@`, `:`, `/`, `%` and similar characters, or "
                f'websocket_library="picows".'
            )


def proxy_connect_kwargs(websocket_library: str, proxy: Optional[str]) -> dict:
    """
    `connect()` kwargs for the configured proxy: the URL itself plus, for an
    `https://` proxy, the TLS context for the hop to the proxy - `websockets`
    (>= 15.0) requires it as `proxy_ssl`, `picows` (>= 2.3.0) takes it as
    `proxy_ssl_context`. Empty when no proxy is configured, so the libraries
    keep their own default (`proxy=True`: environment `wss_proxy`/`https_proxy`).
    """
    if proxy is None:
        return {}
    kwargs = {"proxy": proxy}
    if urlparse(proxy).scheme == "https":
        if websocket_library == WEBSOCKET_LIBRARY_PICOWS:
            kwargs["proxy_ssl_context"] = ssl.create_default_context()
        else:
            kwargs["proxy_ssl"] = ssl.create_default_context()
    return kwargs


def build_socks5_proxy_url(
    address: str,
    port: int,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """
    `socks5://[user:password@]address:port` from the legacy `socks5_proxy_*`
    manager parameters, for `connect(proxy=...)` of both libraries. User and
    password are percent-encoded so that `@`, `:` or `/` in credentials
    survive the URL round trip.
    """
    auth = ""
    if user is not None:
        auth = quote(str(user), safe="")
        if password is not None:
            auth += ":" + quote(str(password), safe="")
        auth += "@"
    return f"socks5://{auth}{address}:{int(port)}"


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
