#!/usr/bin/env python3
"""
Self-contained Post Bridge client. No external CLI required.

  pb.py accounts                       list connected accounts
  pb.py upload --file <path>           upload media, print media_id
  pb.py get --id <post_id>             fetch one post
  pb.py results [--post-id <id>]       publish results
  pb.py media                          list uploaded media

Also the shared transport for every other script in this skill.

Why this exists as a module: the Post Bridge write path returns success without
reliably persisting fields. `patch_verify` is the only safe way to write.
"""
import json, os, sys, time, mimetypes, argparse, urllib.request, urllib.error

API = "https://api.post-bridge.com/v1"
_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _HERE)
import config as _cfg  # noqa: E402

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".mp4": "video/mp4",
        ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".webm": "video/webm",
        ".pdf": "application/pdf"}


def api_key():
    env = os.environ.get("POST_BRIDGE_API_KEY")
    if env:
        return env
    p = _cfg.TOOLS.get("post_bridge_config", os.path.expanduser("~/.config/post-bridge/config.json"))
    p = os.path.expanduser(p)
    if not os.path.isfile(p):
        raise RuntimeError(
            f"no Post Bridge API key. set POST_BRIDGE_API_KEY or create {p} "
            'containing {"apiKey": "pb_live_..."}')
    return json.load(open(p))["apiKey"]


def req(path, method="GET", body=None, base=API):
    r = urllib.request.Request(
        f"{base}{path}", method=method,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(r) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else {}


def paged(path):
    """Follow Post Bridge pagination and return every record."""
    out, off = [], 0
    sep = "&" if "?" in path else "?"
    while True:
        pg = req(f"{path}{sep}limit=100&offset={off}")
        out += pg.get("data", [])
        if not (pg.get("meta") or {}).get("next"):
            return out
        off += 100


def upload(path):
    """Two step upload: reserve a URL, PUT the bytes. Returns media_id."""
    f = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(f):
        raise FileNotFoundError(f)
    size = os.path.getsize(f)
    ext = os.path.splitext(f)[1].lower()
    mime = MIME.get(ext) or mimetypes.guess_type(f)[0] or "application/octet-stream"
    created = req("/media/create-upload-url", "POST",
                  {"mime_type": mime, "size_bytes": size, "name": os.path.basename(f)})
    with open(f, "rb") as fh:
        put = urllib.request.Request(created["upload_url"], method="PUT",
                                     data=fh.read(), headers={"Content-Type": mime})
        with urllib.request.urlopen(put) as r:
            if r.status not in (200, 201, 204):
                raise RuntimeError(f"upload failed HTTP {r.status}")
    return created["media_id"], size


def patch_verify(post_id, body, check, attempts=5, wait=2.0):
    """Write, sleep, re-read, assert on the real field, retry.

    Required because this API will return HTTP 500 and persist anyway, or
    return HTTP 200 and silently drop social_accounts to []. The status code
    carries no information. Only a re-read does.
    """
    for i in range(1, attempts + 1):
        try:
            req(f"/posts/{post_id}", "PATCH", body)
        except urllib.error.HTTPError:
            pass
        time.sleep(wait)
        try:
            if check(req(f"/posts/{post_id}")):
                return True, f"attempt {i}"
        except Exception:
            pass
    return False, f"unverified after {attempts}"


def _main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("accounts")
    u = sub.add_parser("upload"); u.add_argument("--file", required=True)
    g = sub.add_parser("get"); g.add_argument("--id", required=True)
    r = sub.add_parser("results"); r.add_argument("--post-id")
    sub.add_parser("media")
    a = ap.parse_args()
    if a.cmd == "accounts":
        for x in paged("/social-accounts"):
            flag = "  NEEDS RECONNECT" if x.get("needs_reconnect") else ""
            print(f"{x['id']:<8} {x['platform']:<16} {x.get('username','')}{flag}")
    elif a.cmd == "upload":
        mid, size = upload(a.file)
        print(json.dumps({"media_id": mid, "size_bytes": size}, indent=2))
    elif a.cmd == "get":
        print(json.dumps(req(f"/posts/{a.id}"), indent=2))
    elif a.cmd == "results":
        q = f"?post_id={a.post_id}" if a.post_id else ""
        print(json.dumps(paged(f"/post-results{q}"), indent=2))
    elif a.cmd == "media":
        for m in paged("/media"):
            o = m.get("object") or {}
            print(f"{m['id']}  {m.get('mime_type',''):<18} {o.get('size_bytes',0):>12}  {o.get('name') or ''}")


if __name__ == "__main__":
    _main()
