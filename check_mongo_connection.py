"""
MongoDB connectivity checker for server-side diagnostics.

What it does:
1) Loads AWS_MONGODB_URI from .env (or MONGODB_URI fallback)
2) Resolves Mongo hosts via DNS
3) Tests TCP connectivity to each host
4) Runs MongoDB ping command using pymongo

Usage:
    python check_mongo_connection.py

Optional:
    python check_mongo_connection.py --uri "mongodb+srv://..."
    python check_mongo_connection.py --timeout-ms 15000
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import traceback
from typing import List, Tuple
from urllib.parse import urlparse

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ConnectionFailure, OperationFailure, ServerSelectionTimeoutError


def _mask_uri(uri: str) -> str:
    """Mask password in URI for safe logging."""
    try:
        parsed = urlparse(uri)
        if parsed.scheme and parsed.netloc and "@" in parsed.netloc:
            creds, hostpart = parsed.netloc.rsplit("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                masked_netloc = f"{user}:***@{hostpart}"
            else:
                masked_netloc = f"***@{hostpart}"
            return f"{parsed.scheme}://{masked_netloc}{parsed.path or ''}"
        return uri
    except Exception:
        return "<unable to mask URI>"


def _extract_hosts(uri: str) -> List[Tuple[str, int]]:
    """Best-effort host extraction from mongodb:// and mongodb+srv:// URIs."""
    parsed = urlparse(uri)
    hosts: List[Tuple[str, int]] = []

    netloc = parsed.netloc
    if "@" in netloc:
        _, netloc = netloc.rsplit("@", 1)

    for host_token in netloc.split(","):
        token = host_token.strip()
        if not token:
            continue
        if ":" in token:
            h, p = token.rsplit(":", 1)
            try:
                hosts.append((h.strip(), int(p.strip())))
            except ValueError:
                hosts.append((h.strip(), 27017))
        else:
            if parsed.scheme == "mongodb+srv":
                # SRV uses DNS to discover true nodes; 27017 is still useful for a quick check.
                hosts.append((token, 27017))
            else:
                hosts.append((token, 27017))

    return hosts


def _dns_check(host: str) -> None:
    print(f"[DNS] Resolving {host} ...", end=" ")
    try:
        socket.getaddrinfo(host, None)
        print("OK")
    except Exception as exc:
        print(f"FAILED ({exc})")


def _tcp_check(host: str, port: int, timeout_seconds: float) -> None:
    print(f"[TCP] Connecting to {host}:{port} ...", end=" ")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_seconds)
    try:
        sock.connect((host, port))
        print("OK")
    except Exception as exc:
        print(f"FAILED ({exc})")
    finally:
        sock.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check MongoDB connectivity from this server")
    parser.add_argument("--uri", default="", help="Mongo URI (overrides .env)")
    parser.add_argument("--timeout-ms", type=int, default=10000, help="Timeout in milliseconds (default: 10000)")
    args = parser.parse_args()

    load_dotenv()

    uri = args.uri or os.getenv("AWS_MONGODB_URI") or os.getenv("MONGODB_URI", "")
    if not uri:
        print("ERROR: Mongo URI not found. Set AWS_MONGODB_URI in .env or pass --uri.")
        return 2

    print("Mongo URI:", _mask_uri(uri))
    timeout_ms = max(1000, int(args.timeout_ms))
    timeout_seconds = timeout_ms / 1000.0

    hosts = _extract_hosts(uri)
    if hosts:
        print("\nHost-level checks:")
        for host, port in hosts:
            _dns_check(host)
            _tcp_check(host, port, timeout_seconds)

    print("\nMongoDB ping check:")
    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            socketTimeoutMS=timeout_ms,
            retryWrites=True,
            tls=True,
        )

        # Forces server selection + auth path.
        result = client.admin.command("ping")
        print("SUCCESS: MongoDB connection established.")
        print("Ping result:", result)

        try:
            info = client.server_info()
            version = info.get("version")
            print(f"Server version: {version}")
        except Exception:
            pass

        client.close()
        return 0

    except ServerSelectionTimeoutError as exc:
        print("FAILED: Server selection timed out.")
        print(f"Details: {exc}")
        print("Hints:")
        print("- Corporate proxy/firewall may block outbound TLS to MongoDB Atlas.")
        print("- Ensure Atlas IP access list allows your server egress IP.")
        print("- Verify DNS resolution for SRV records if using mongodb+srv URI.")
        return 1

    except OperationFailure as exc:
        print("FAILED: Connected but authentication/authorization failed.")
        print(f"Details: {exc}")
        return 1

    except ConfigurationError as exc:
        print("FAILED: URI or TLS configuration error.")
        print(f"Details: {exc}")
        return 1

    except ConnectionFailure as exc:
        print("FAILED: Network connection failure.")
        print(f"Details: {exc}")
        return 1

    except Exception as exc:
        print("FAILED: Unexpected error.")
        print(f"Details: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
