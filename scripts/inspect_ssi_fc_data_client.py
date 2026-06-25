# -*- coding: utf-8 -*-
"""Inspect the official SSI FC Data Python client without using credentials.

This script is intentionally metadata-only. It imports the installed package,
prints module names, public signatures, and selected constants, but never reads
environment variables, instantiates credentialed clients, or opens a stream.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path


PACKAGE = "ssi_fc_data"


def _has_text(path: str | None, needle: str) -> bool:
    if not path:
        return False
    try:
        return needle in Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def main() -> int:
    package = importlib.import_module(PACKAGE)
    print(f"package={PACKAGE}")
    print(f"version={getattr(package, '__version__', 'unknown')}")
    print(f"file={inspect.getfile(package)}")

    print("modules:")
    for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        print(f"- {module.name}")

    stream_module = importlib.import_module("ssi_fc_data.fc_md_stream")
    client_module = importlib.import_module("ssi_fc_data.fc_md_client")
    api_module = importlib.import_module("ssi_fc_data.model.api")
    connection_module = importlib.import_module("ssi_fc_data.signalr._connection")
    transport_module = importlib.import_module("ssi_fc_data.signalr.transports._transport")

    inspected = [
        client_module.MarketDataClient,
        stream_module.MarketDataStream,
        stream_module.MarketDataStream.start,
        stream_module.MarketDataStream.swith_channel,
        connection_module.Connection,
        connection_module.Connection.start,
        connection_module.Connection.close,
        transport_module.WebsocketTransport.start,
        transport_module.WebsocketTransport.stop,
    ]

    print("signatures:")
    for obj in inspected:
        print(f"- {obj.__module__}.{obj.__qualname__}{inspect.signature(obj)}")

    print("stream_constants:")
    for name in ("SIGNALR", "SIGNALR_METHOD", "SIGNALR_ERROR_METHOD", "SIGNALR_HUB_MD"):
        print(f"- {name}={getattr(api_module, name)}")

    stream_path = inspect.getsourcefile(stream_module.MarketDataStream)
    transport_path = inspect.getsourcefile(transport_module.WebsocketTransport)
    connection_path = inspect.getsourcefile(connection_module.Connection)
    print("safety_findings:")
    print(f"- transport_prints_headers={_has_text(transport_path, 'print(self.headers)')}")
    print(f"- connection_close_calls_transport_close={_has_text(connection_path, 'self.__transport.close()')}")
    print(f"- transport_has_stop={hasattr(transport_module.WebsocketTransport, 'stop')}")
    print(f"- stream_has_start={hasattr(stream_module.MarketDataStream, 'start')}")
    print(f"- stream_has_switch_channel_typo={hasattr(stream_module.MarketDataStream, 'swith_channel')}")
    print(f"- stream_source={stream_path}")
    print(f"- transport_source={transport_path}")
    print(f"- connection_source={connection_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
