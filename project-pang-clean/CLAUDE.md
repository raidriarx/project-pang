# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Dataset workspace for **Project Pang** — "An Initial Benchmark for Thai Buddha Image Pose (Pang) Classification Using Deep Learning", targeting ICCT 2026 (full-paper deadline **2026-08-31**). It holds the Wikimedia Commons crawl, the AI labeling pass, and the resulting per-image labels for 5 target pang classes: `marawichai`, `samathi`, `nakprok`, `prathanphon`, `saiyat` (+ `unknown` / `uncertain` / `exclude`).

Project documentation (labeling spec, annotation guideline, research notes, progress reports) lives in the Obsidian vault at `~/Documents/Obsidian/Vault101/ICCT 2026 Conference/` — this folder sits outside `~/Documents` because macOS denies Claude Code access to it. Keep prose there; keep code and data here.

## Pipeline (run in this order)

```
python3 collect.py           # crawl Commons category trees → manifest.csv (metadata only)
python3 download_images.py   # fetch each manifest row at 1024px → raw/00000.jpg…  (resumable; failures → download_failures.json)
python3 build_sheets.py      # group images into statue-units, pick 1 representative each → sheets/*.png montages + index.json
# (visual labeling pass over sheets/ happens here — results hand-encoded into write_labels.py)
python3 write_labels.py      # emit labels.json  (unit idx → [label, confidence, note])
python3 apply_labels.py      # fan unit labels out to every image → labeled_clean.csv + images/<label>/ copies
```

All scripts hardcode `WORK=/Users/admin/project-pang-clean` and take no arguments.

## Architecture — how the pieces couple

- **Row index is the image ID.** `raw/00042.jpg` is row 42 (0-based) of `manifest.csv`; `labeled_clean.csv` carries it as `_row`. **Never re-run `collect.py` over an existing `raw/`** — reordered manifest rows silently mismatch every downloaded file and label. A fresh crawl requires a fresh download and re-label (or an explicit migration by `file_name`).
- **Statue-units.** `unit_key()` groups images into ~185 units: Thai "Statues of the Buddha …" seeds group by `wat` (falling back to per-file), global seeds group by category. This function is **duplicated in `build_sheets.py` and `apply_labels.py` and must stay identical**, or labels fan out to the wrong images.
- **Label indices.** `labels.json` keys are montage cell indices assigned by `build_sheets.py` in `ORDER`-then-unit-size order and recorded in `index.json` (`idx`, `unit`, `rep_row`, `count`). Rebuilding sheets renumbers cells → invalidates `labels.json` and the hand-written table in `write_labels.py`.
- **`images/` is derived.** It is a byte-for-byte copy of `raw/` reorganized by label; regenerate it with `apply_labels.py` rather than editing it.
- Crawl etiquette: both network scripts send a User-Agent with a contact email and rate-limit (0.4s API / 0.2s downloads). Keep that when extending them.

## Data status — read before trusting the labels

Labels are **AI pre-labels, montage-based, not verified ground truth.** A 2026-07-17 audit (see "Progress Report — Dataset & Findings (2026-07-17)" in the vault) found:

- All 21 `nakprok` images are **non-Thai** (Bern museum piece, ancient sandstone, Burmese pagodas) — per spec they should be `exclude`; real Thai nakprok = 0.
- `samathi` row 622 is a placard-confirmed **marawichai mislabel**; usable samathi ≤ 1.
- `prathanphon` = 0 — its seed (`Vārada mudra`) returned only non-Thai bodhisattvas.
- The `uncertain` pile (761 imgs) hides recoverable units: Emerald Buddha (56) and Phra Phuttha Sihing (55) are documented samathi statues whose hands are hidden in photos. Open policy question: label by visible cue vs. documented statue identity.
- 250 of 534 `saiyat` images are one statue (Wat Pho) — temple-disjoint splits must balance by class too.

Usable today: marawichai (~538) and saiyat (~534) only. The planned fix is a targeted re-crawl with Thai-specific seeds (edit `SEEDS` in `collect.py`) plus re-montaging the `uncertain` units.

## Repository hygiene

`raw/` and `images/` (~1.1 GB each) are gitignored; the dataset ships as a zip on GitHub Releases and is reproducible from `manifest.csv` via `download_images.py`. Everything else — scripts, `manifest.csv`, `labels.json`, `labeled_clean.csv`, `index.json`, `sheets/` — is tracked.
