"""FRIEND-LEASE tool bridge (experimental, grown for the 2026-10-23 test).

Read-only bridge from the AutoProteus seed to Raphael's FRIEND-LEASE app
(https://friend-lease.nema-anonymous.workers.dev). FRIEND-LEASE exposes a
single POST /actions bus plus a public GET /health. Every bus action takes
a session token; without one the server answers with its own auth error,
which this bridge surfaces honestly rather than hiding.

Only read actions are allowlisted. Nothing here can post, pay, follow, or
message. A token, when one exists, is read from the FRIEND_LEASE_TOKEN
environment variable and never written anywhere by this module.
"""
import http.client
import json
import os
import urllib.error
import urllib.request

BASE_URL = "https://friend-lease.nema-anonymous.workers.dev"
TIMEOUT = 10
MAX_RESPONSE = 200_000

READ_ACTIONS = {
    "getEngineCatalog",
    "getPaymentLinks",
    "listProfiles",
    "listHumans",
    "getSession",
}


def _request(method, path, payload=None):
    data = None
    headers = {"User-Agent": "AutoProteus-seed/friend-lease-tool", "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as e:
        raw = e.read(MAX_RESPONSE + 1)
        try:
            return json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            raise ValueError(f"FRIEND-LEASE returned HTTP {e.code} with a non-JSON body")
    except urllib.error.URLError as e:
        raise ValueError(f"FRIEND-LEASE unreachable: {e.reason}")
    except http.client.HTTPException as e:
        raise ValueError(f"FRIEND-LEASE connection failed mid-response: {e}")
    if len(raw) > MAX_RESPONSE:
        raise ValueError("FRIEND-LEASE response exceeded the size cap")
    return json.loads(raw.decode("utf-8"))


def friend_lease(workspace, args):
    action = args.get("action")
    if action == "health":
        return _request("GET", "/health")
    if action not in READ_ACTIONS:
        raise ValueError(
            "friend_lease tool is read-only; allowed actions: health, "
            + ", ".join(sorted(READ_ACTIONS))
        )
    call_args = dict(args.get("args") or {})
    token = os.environ.get("FRIEND_LEASE_TOKEN")
    if token and "token" not in call_args:
        call_args["token"] = token
    return _request("POST", "/actions", {"action": action, "args": call_args})
