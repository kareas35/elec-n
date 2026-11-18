#!/usr/bin/env python3
"""Elektronik Akademi V3.8: cautious, resumable Wayback image recovery.

No dependencies outside the Python standard library. Never edits publication HTML
or records.json. Operates only on URL inventory supplied by the local project.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import struct
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

RISK_DOMAINS = {"www.mavikitaplar.com", "www.elektromania.net", "www.deli-prof.net"}
USER_AGENT = "ElektronikAkademi-ArchiveAudit/1.0 (manual, low-rate recovery)"
MAX_BYTES = 8 * 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def image_info(content):
    if content.startswith((b"GIF87a", b"GIF89a")) and len(content) >= 14:
        width, height = struct.unpack("<HH", content[6:10])
        return ("image/gif", "gif", width, height)
    if content.startswith(b"\x89PNG\r\n\x1a\n") and len(content) >= 24:
        width, height = struct.unpack(">II", content[16:24])
        return ("image/png", "png", width, height)
    if content.startswith(b"\xff\xd8\xff") and len(content) >= 4:
        return ("image/jpeg", "jpg", None, None)
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ("image/webp", "webp", None, None)
    return (None, None, None, None)


def record_bytes(data, original_url, outdir, existing=None):
    mime, ext, width, height = image_info(data)
    if mime is None or len(data) > MAX_BYTES:
        raise ValueError("Image signature invalid or file too large")
    sha = hashlib.sha256(data).hexdigest()
    destination = outdir / f"{sha}.{ext}"
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != sha:
            raise ValueError("Existing file hash mismatch")
    else:
        outdir.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".tmp")
        temp.write_bytes(data)
        temp.replace(destination)
    return {"sha256": sha, "file": str(destination), "bytes": len(data),
            "mime": mime, "width": width, "height": height,
            "validation": "signature_only; visual/rights review pending"}


def load_inventory(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by_url = {}
    for r in rows:
        if r["Domain"] not in RISK_DOMAINS:
            continue
        url = r["URL"]
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or parsed.netloc.lower() not in RISK_DOMAINS:
            continue
        item = by_url.setdefault(url, {"url": url, "domain": parsed.netloc.lower(), "publications": []})
        if r["Yayin"] not in item["publications"]:
            item["publications"].append(r["Yayin"])
    return by_url


def seed_prior(root, entries, manifest):
    test_csv = root / "wayback-ilk-test.csv"
    if not test_csv.exists():
        return 0
    count = 0
    with test_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            url = row["OriginalURL"]
            if url not in entries or url in manifest["entries"]:
                continue
            if row["Status"] == "SNAPSHOT_FOUND" and re.fullmatch(r"\d{14}", row["Timestamp"]):
                manifest["entries"][url] = {"status": "snapshot_found", "timestamp": row["Timestamp"],
                    "snapshot_url": row["SnapshotURL"], "updated_at": utc_now(), "attempts": 0}
                count += 1
            elif row["Status"] == "NO_SNAPSHOT_RETURNED":
                manifest["entries"][url] = {"status": "no_snapshot_returned", "updated_at": utc_now(), "attempts": 0}
                count += 1
    return count


def retry_after_seconds(headers):
    raw = headers.get("Retry-After") if headers else None
    if raw:
        try:
            return max(0, min(int(raw), 86400))
        except ValueError:
            try:
                return max(0, min(int((parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()), 86400))
            except (ValueError, TypeError, OverflowError):
                pass
    return 900  # Conservative 15 minute pause when server does not specify.


def get(req, max_bytes=MAX_BYTES):
    with urlopen(req, timeout=25) as response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Response exceeds safety size limit")
        return data, response.headers, response.geturl()


def availability(original):
    api = "https://archive.org/wayback/available?" + urlencode({"url": original})
    request = Request(api, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    data, headers, final = get(request, max_bytes=512 * 1024)
    payload = json.loads(data.decode("utf-8"))
    snapshot = payload.get("archived_snapshots", {}).get("closest", {})
    ts = snapshot.get("timestamp", "")
    if snapshot.get("available") and re.fullmatch(r"\d{14}", ts):
        return {"status": "snapshot_found", "timestamp": ts,
                "snapshot_url": snapshot.get("url", "")}
    return {"status": "no_snapshot_returned"}


def download_image(original, timestamp):
    # 'id_' retrieves the archived resource, not an HTML replay wrapper.
    url = f"https://web.archive.org/web/{timestamp}id_/{original}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    data, headers, final = get(request)
    if urlsplit(final).hostname not in ("web.archive.org", "wayback.archive-it.org"):
        raise ValueError(f"Unexpected Wayback redirect: {final[:120]}")
    mime, _, _, _ = image_info(data)
    if not mime:
        raise ValueError(f"Not an image (Content-Type={headers.get('Content-Type', '')})")
    return data, final


def write_csv(path, entries, manifest):
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["URL", "Domain", "Yayinlar", "Durum", "Timestamp", "SnapshotURL", "Dosya", "SHA256", "Bayt", "Mime", "Dogrulama", "Hata", "Guncelleme"]
    with path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(columns)
        for url, source in sorted(entries.items()):
            r = manifest["entries"].get(url, {})
            wr.writerow([url, source["domain"], ";".join(source["publications"]), r.get("status", "pending"),
                r.get("timestamp", ""), r.get("snapshot_url", ""), r.get("file", ""), r.get("sha256", ""),
                r.get("bytes", ""), r.get("mime", ""), r.get("validation", ""), r.get("error", ""), r.get("updated_at", "")])


def main():
    p = argparse.ArgumentParser(description="V3.8 Wayback cautious/resumable image recovery")
    p.add_argument("--root", type=Path, default=Path("blogger-arsiv/denetim/v3.8"))
    p.add_argument("--limit", type=int, default=3, help="Max different image URLs per run (default: 3)")
    p.add_argument("--delay", type=float, default=15, help="Seconds between requests (minimum: 10)")
    p.add_argument("--download", action="store_true", help="Retrieve image bytes (otherwise only find snapshots)")
    p.add_argument("--retry-failed", action="store_true", help="Retry previous failures/no snapshot after review")
    p.add_argument("--retry-downloads", action="store_true", help="Retry only download errors with known snapshots")
    p.add_argument("--import-069", action="store_true", help="Register previously validated 069.gif with its provenance")
    p.add_argument("--domain", type=str, default=None, help="Only process URLs from this domain")
    args = p.parse_args()
    if not 1 <= args.limit <= 20 or args.delay < 10:
        p.error("Use --limit between 1 and 20 and --delay >= 10")
    root = args.root
    inventory = root / "gorsel-envanteri.csv"
    if not inventory.exists():
        p.error(f"Missing inventory: {inventory}")
    entries = load_inventory(inventory)
    manifest_path = root / "wayback-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"version": 1, "entries": {}, "pause_until": 0}
    if manifest.get("version") != 1:
        p.error("Unexpected manifest version")
    seeded = seed_prior(root, entries, manifest)
    outdir = root / "wayback-kurtarilan" / "sha256"
    if args.import_069:
        first = root / "wayback-kurtarilan" / "069.gif"
        prior = root / "wayback-ilk-test.csv"
        matches = []
        if prior.exists():
            with prior.open(encoding="utf-8-sig", newline="") as f:
                matches = [r for r in csv.DictReader(f) if r["Yayin"] == "yayinlar/069.html" and r["Status"] == "SNAPSHOT_FOUND"]
        if not first.exists() or len(matches) != 1 or matches[0]["OriginalURL"] not in entries:
            p.error("Cannot import 069: source GIF or provenance row missing")
        row = matches[0]
        meta = record_bytes(first.read_bytes(), row["OriginalURL"], outdir)
        manifest["entries"][row["OriginalURL"]] = {"status": "verified_signature", "timestamp": row["Timestamp"],
            "snapshot_url": row["SnapshotURL"], "updated_at": utc_now(), "attempts": 0, **meta}
        print("Imported 069.gif with source URL, snapshot time and SHA256.")
    save_json(manifest_path, manifest)
    write_csv(root / "wayback-manifest.csv", entries, manifest)
    print(f"Inventory: {len(entries)} at-risk unique URLs; seeded previous lookups: {seeded}")
    if time.time() < float(manifest.get("pause_until", 0)):
        print("PAUSED after rate limit; no network requests. Resume after:",
              datetime.fromtimestamp(manifest["pause_until"], timezone.utc).isoformat())
        return

    # Prioritize publications with most risky URLs; then source stable order.
    risk_per_publication = {}
    for row in entries.values():
        for pub in row["publications"]:
            risk_per_publication[pub] = risk_per_publication.get(pub, 0) + 1
    decorative = (
        "tbl_", "simge_", "spacer", "blank",
        "corner", "background", "button",
        "menu_", "logo_", "pixel"
    )
    technical = (
        "elektronik_bilgi", "devre", "sema",
        "schematic", "circuit", "kondansator",
        "transistor", "motor", "entegre",
        "sensor", "direnc", "resistor",
        "pcb", "datasheet", "led"
    )

    def priority(source):
        url = source["url"].lower()
        filename = url.rsplit("/", 1)[-1]

        if any(word in filename for word in decorative):
            category = 2
        elif any(word in url for word in technical):
            category = 0
        else:
            category = 1

        affected = max(
            risk_per_publication[p]
            for p in source["publications"]
        )

        return (category, -affected, url)

    candidates = list(entries.values())
    if args.domain:
        from urllib.parse import urlparse
        domain = args.domain.lower().strip().lstrip(".")
        candidates = [
            source for source in candidates
            if (host := (urlparse(source["url"]).hostname or "").lower())
            and (host == domain or host.endswith("." + domain))
        ]
        print(f"Domain filter: {domain}; matching URLs: {len(candidates)}")

    ordered = sorted(candidates, key=priority)
    if args.retry_downloads:
        ordered = [source for source in ordered
                   if manifest["entries"].get(source["url"], {}).get("status") == "download_error"
                   and manifest["entries"][source["url"]].get("timestamp")]
        print(f"Download retries: {len(ordered)}")
    print("Priority ordering: technical -> unknown -> decorative")
    processed = 0
    last_request_at = None

    def pace():
        nonlocal last_request_at
        if last_request_at is not None:
            remaining = args.delay - (time.monotonic() - last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        last_request_at = time.monotonic()

    try:
        for source in ordered:
            url = source["url"]
            entry = manifest["entries"].get(url, {})
            state = entry.get("status", "pending")
            if state == "verified_signature" or (state in ("no_snapshot_returned", "lookup_error", "download_error") and not (args.retry_failed or args.retry_downloads)):
                continue
            if state == "snapshot_found" and not args.download:
                continue
            if processed >= args.limit:
                break
            processed += 1
            print(f"[{processed}/{args.limit}] {source['publications'][0]} {url[:110]}")
            try:
                if state not in ("snapshot_found", "download_error") or not entry.get("timestamp"):
                    pace()
                    result = availability(url)
                    entry.update(result)
                    entry["attempts"] = int(entry.get("attempts", 0)) + 1
                    entry["updated_at"] = utc_now()
                    manifest["entries"][url] = entry
                    save_json(manifest_path, manifest)
                    print("   lookup:", entry["status"])
                if entry["status"] in ("snapshot_found", "download_error") and args.download:
                    pace()
                    data, final = download_image(url, entry["timestamp"])
                    meta = record_bytes(data, url, outdir)
                    entry.update(meta)
                    entry["status"] = "verified_signature"
                    entry["replay_url"] = final
                    entry["updated_at"] = utc_now()
                    print("   image:", entry["bytes"], "bytes", entry["sha256"][:12])
            except HTTPError as exc:
                if exc.code == 429:
                    pause = retry_after_seconds(exc.headers)
                    manifest["pause_until"] = time.time() + pause
                    entry["status"] = "rate_limited"
                    entry["error"] = f"HTTP 429: paused {pause}s; do not retry before pause ends"
                    print("   RATE LIMIT: stopping immediately; pause", pause, "seconds")
                else:
                    entry["status"] = "download_error" if entry.get("timestamp") else "lookup_error"
                    entry["error"] = f"HTTP {exc.code} {exc.reason}"[:300]
                    print("   error:", entry["error"])
            except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
                entry["status"] = "download_error" if entry.get("timestamp") else "lookup_error"
                entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
                print("   error:", entry["error"])
            finally:
                entry["updated_at"] = utc_now()
                manifest["entries"][url] = entry
                save_json(manifest_path, manifest)
                write_csv(root / "wayback-manifest.csv", entries, manifest)
            if entry.get("status") == "rate_limited":
                break
    except KeyboardInterrupt:
        print("Interrupted: saved progress remains in manifest.")
    finally:
        save_json(manifest_path, manifest)
        write_csv(root / "wayback-manifest.csv", entries, manifest)
    print("Processed this run:", processed)
    counts = {}
    for row in manifest["entries"].values():
        status = row.get("status", "pending")
        counts[status] = counts.get(status, 0) + 1
    print("Recorded statuses:", counts)
    print("Manifest:", manifest_path)
    print("Existing HTML and records.json were not modified.")


if __name__ == "__main__":
    main()
