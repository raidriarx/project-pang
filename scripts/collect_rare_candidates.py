"""Collect Thai-specific candidates for Project Pang's scarce classes.

Candidates are intentionally kept separate from training data.  A candidate label
describes why an image was collected; it is not ground truth.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import time
from pathlib import Path
from typing import Any

import requests


API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {
    "User-Agent": (
        "ProjectPangResearch/2.0 (Thai Buddha pose classification research; "
        "contact: jirathanayosyingthumakul@gmail.com)"
    )
}
DELAY = 0.4
THUMB_WIDTH = 1400
MAX_VIEWS_PER_UNIT = 5

# Each Commons category below represents one named statue, so it is also a safe
# grouping key for temple/statue-disjoint model splits.  Pose is still verified
# manually from visible hand and body cues.
NAMED_UNITS = [
    ("samathi", "Category:Emerald Buddha"),
    ("samathi", "Category:Jade Buddha of Chiang Rai"),
    ("samathi", "Category:Phra Phuttha Sihing"),
    ("prathanphon", "Category:Luang Pho Chin Prathan Phon"),
    ("nakprok", "Category:Luang Pho Sila (Wat Thung Saliam)"),
    ("nakprok", "Category:Mucalinda of Wat Hua Wiang"),
    ("nakprok", "Category:Mucalinda of Wat Na Phra Men"),
    ("nakprok", "Category:Mucalinda of Wat Pradu Song Tham"),
]

# Searches discover additional units.  Thai terms reduce the non-Thai pollution
# seen with the old global Dhyana/Mucilinda/Varada searches.
SEARCHES = [
    ("samathi", "ปางสมาธิ พระพุทธรูป"),
    ("samathi", '"พระพุทธรูปปางสมาธิ"'),
    ("samathi", '"ปางสมาธิเพชร"'),
    ("samathi", '"สมาธิราบ" พระพุทธรูป'),
    ("samathi", '"meditation Buddha" Thailand'),
    ("samathi", '"Dhyana mudra" Thailand Buddha'),
    ("nakprok", "ปางนาคปรก พระพุทธรูป"),
    ("nakprok", '"พระพุทธรูปปางนาคปรก"'),
    ("nakprok", '"พระนาคปรก" Thailand'),
    ("nakprok", '"naga protected Buddha" Thailand'),
    ("nakprok", "Mucalinda Thailand Buddha"),
    ("nakprok", '"Mucilinda in Thailand"'),
    ("prathanphon", "ปางประทานพร พระพุทธรูป"),
    ("prathanphon", '"พระพุทธรูปปางประทานพร"'),
    ("prathanphon", '"ประทานพร" พระพุทธรูป'),
    ("prathanphon", '"Thai Buddha" varada'),
    ("prathanphon", '"blessing Buddha" Thailand statue'),
    ("prathanphon", '"Luang Pho Chin Prathan Phon"'),
]

FIELDS = [
    "page_id",
    "candidate_label",
    "statue_id",
    "source_type",
    "source_query",
    "commons_title",
    "commons_page_url",
    "download_url",
    "local_path",
    "sha1",
    "width",
    "height",
    "license",
    "author",
]


def api(params: dict[str, Any]) -> dict[str, Any]:
    response = requests.get(
        API,
        params={**params, "action": "query", "format": "json", "formatversion": 2},
        headers=HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    time.sleep(DELAY)
    return response.json()


def image_props() -> dict[str, Any]:
    return {
        "prop": "imageinfo",
        "iiprop": "url|size|mime|sha1|extmetadata",
        "iiurlwidth": THUMB_WIDTH,
        "iiextmetadatalanguage": "en",
    }


def category_files(category: str, limit: int) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    continuation: dict[str, Any] = {}
    while len(pages) < limit:
        data = api({
            "generator": "categorymembers",
            "gcmtitle": category,
            "gcmnamespace": 6,
            "gcmtype": "file",
            "gcmlimit": min(limit - len(pages), 50),
            **image_props(),
            **continuation,
        })
        batch = data.get("query", {}).get("pages", [])
        pages.extend(batch)
        if not batch or "continue" not in data:
            break
        continuation = data["continue"]
    return pages[:limit]


def search_files(query: str, limit: int) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    continuation: dict[str, Any] = {}
    while len(pages) < limit:
        data = api({
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": min(limit - len(pages), 50),
            **image_props(),
            **continuation,
        })
        batch = data.get("query", {}).get("pages", [])
        pages.extend(batch)
        if not batch or "continue" not in data:
            break
        continuation = data["continue"]
    return pages[:limit]


def clean(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value", "")
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def safe_filename(page_id: str, title: str, mime: str) -> str:
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
    stem = re.sub(r'[<>:"/\\|?*]+', "_", Path(title.removeprefix("File:")).stem)
    stem = re.sub(r"\s+", "_", stem).strip(" ._")[:100] or "candidate"
    return f"{page_id}_{stem}{extension}"


def fallback_unit(label: str, title: str) -> str:
    # Search hits are provisional one-image units until a reviewer assigns a
    # canonical statue/temple ID. This safely avoids accidental cross-split reuse.
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12]
    return f"unresolved:{label}:{digest}"


def write_manifest(path: Path, rows: dict[str, dict[str, str]]) -> None:
    """Checkpoint progress so interrupted crawls resume safely."""
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/rare_candidates"))
    parser.add_argument("--search-limit", type=int, default=30)
    parser.add_argument("--max-views-per-unit", type=int, default=MAX_VIEWS_PER_UNIT)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()

    output = args.output.resolve()
    image_dir = output / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest = output / "manifest.csv"

    existing: dict[str, dict[str, str]] = {}
    if manifest.exists():
        with manifest.open("r", newline="", encoding="utf-8-sig") as handle:
            existing = {row["page_id"]: row for row in csv.DictReader(handle)}

    jobs: list[tuple[str, str, str]] = []
    for label, category in NAMED_UNITS:
        jobs.append((label, "category", category))
    for label, query in SEARCHES:
        jobs.append((label, "text_search", query))

    rows = dict(existing)
    seen_sha1 = {row["sha1"] for row in rows.values() if row.get("sha1")}
    new_count = 0
    for label, source_type, source_query in jobs:
        print(f"Collecting {label}: {source_query}", flush=True)
        try:
            pages = (
                category_files(source_query, args.max_views_per_unit)
                if source_type == "category"
                else search_files(source_query, args.search_limit)
            )
        except requests.RequestException as error:
            print(f"  Request failed, continuing: {error}", flush=True)
            continue
        for page in pages:
            page_id = str(page.get("pageid", ""))
            infos = page.get("imageinfo") or []
            if not page_id or not infos or page_id in rows:
                continue
            info = infos[0]
            mime = info.get("mime", "")
            sha1 = info.get("sha1", "")
            if mime not in {"image/jpeg", "image/png", "image/webp"} or (sha1 and sha1 in seen_sha1):
                continue
            title = page.get("title", "")
            statue_id = (
                source_query.removeprefix("Category:")
                if source_type == "category"
                else fallback_unit(label, title)
            )
            filename = safe_filename(page_id, title, mime)
            relative_path = Path("images") / label / filename
            destination = output / relative_path
            thumb_url = info.get("thumburl") or info.get("url", "")
            if not args.metadata_only and not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                response = requests.get(thumb_url, headers=HEADERS, timeout=90)
                response.raise_for_status()
                destination.write_bytes(response.content)
                time.sleep(DELAY)
            metadata = info.get("extmetadata", {})
            rows[page_id] = {
                "page_id": page_id,
                "candidate_label": label,
                "statue_id": statue_id,
                "source_type": source_type,
                "source_query": source_query,
                "commons_title": title,
                "commons_page_url": info.get("descriptionurl", ""),
                "download_url": thumb_url,
                "local_path": relative_path.as_posix(),
                "sha1": sha1,
                "width": str(info.get("width", "")),
                "height": str(info.get("height", "")),
                "license": clean(metadata.get("LicenseShortName")),
                "author": clean(metadata.get("Artist")),
            }
            seen_sha1.add(sha1)
            new_count += 1
            write_manifest(manifest, rows)

    write_manifest(manifest, rows)

    print(f"New candidates: {new_count}")
    print(f"Total candidates: {len(rows)}")
    print(f"Manifest: {manifest}")
    if not args.metadata_only:
        print(f"Images: {image_dir}")


if __name__ == "__main__":
    main()
