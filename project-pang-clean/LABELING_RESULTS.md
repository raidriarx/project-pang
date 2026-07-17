# Project Pang — Clean Dataset Labeling Results

**Date:** 2026-07-17
**Method:** Wikimedia category-crawl → 2,373 images → collapsed to **185 statue-units**
(by wat / seed-category) → one representative montage-labeled per unit → label fanned
out to all images in the unit. Labeled against `Labeling Spec (5 Pang)`.

## Taxonomy (8 labels)
- **5 target pang:** `marawichai` (earth-touching), `samathi` (meditation),
  `nakprok` (naga-protected), `prathanphon` (varada/boon-granting), `saiyat` (reclining)
- **unknown** — certainly a real Buddha but NOT one of the 5 pang (abhaya, walking/lila,
  double-abhaya "ham yat", fasting Buddha, Pang Palelai, Dvaravati vitarka)
- **uncertain** — a Buddha, but can't tell which pang (hands hidden / distant / eroded / feet-only)
- **exclude** — not a valid Thai Buddha statue at all (relief, amulet, sign, logo, temple
  scenery, back-view, bust/head-only, painting/model, non-Thai: Khmer/Indian/Nepali/Chinese/Burmese)

## Distribution — all 2,373 images
| label | images |
|---|---|
| uncertain | 761 |
| marawichai | 655 |
| saiyat | 534 |
| exclude | 320 |
| unknown | 77 |
| nakprok | 21 |
| samathi | 4 |
| prathanphon | 0 |

## Usable 5-pang set (high + medium confidence only) = **1,093 images**
| pang | images | usable? |
|---|---|---|
| marawichai | 538 | ✅ plenty |
| saiyat | 534 | ✅ plenty |
| nakprok | 19 | ⚠️ scarce |
| samathi | 2 | ❌ too few |
| prathanphon | 0 | ❌ none |

## Key finding — the dataset is severely class-imbalanced
Only **marawichai** and **saiyat** are well-populated. The three other target classes
came up almost empty, and the reason is in the seed categories:

- **prathanphon = 0.** The global `Vārada mudra` seed returned only **non-Thai bodhisattvas**
  (Tibetan/Nepali Tara, Chinese standing figures, Indian/Pala steles). No Thai varada Buddhas.
  Standing Thai Buddhas in the dataset are almost all **abhaya** (raised hand), not varada → `unknown`.
- **nakprok = 19 (3 Thai units).** The global `Mucilinda` seed was mostly **non-Thai / reliefs**
  (Khmer museum pieces, Sri Lankan stupa, Indian steles, Borobudur-style panels).
- **samathi = 2.** Genuinely rare — nearly every seated Thai principal image is Maravijaya
  (earth-touching), consistent with the Fine Arts Dept. book.

## Recommendation for the ICCT paper
The current crawl only supports a credible benchmark for **marawichai vs saiyat** (± nakprok).
To reach the intended 5-class benchmark, do **targeted collection for the 3 rare classes**:
- `prathanphon`: search **Thai-specific** categories/temples, not the global mudra category
  (e.g. Buddha images described as ปางประทานพร / standing Thai Buddhas with the right hand
  lowered, palm out). Expect these to be uncommon.
- `nakprok`: Thai categories like "Phra Nak Prok" / specific wats (Wat Nong Pah Pong, etc.),
  not the global Mucilinda tree.
- `samathi`: Emerald-Buddha-style meditation images and specific meditation-posture wats.

Alternatively, **reframe the "initial benchmark" as 3-class (marawichai / saiyat / nakprok)**
and report the rare-class scarcity as a documented limitation + future-work item.

## Files
- `manifest.csv` — 2,373 rows, source metadata (license, author, url, wat, dims)
- `labels.json` — 185 unit labels: `idx -> [label, confidence, note]`
- `labeled_clean.csv` — per-image labels: `ai_pang, ai_confidence, ai_note` + provenance
- `raw/NNNNN.jpg` — all downloaded images @1024px (row-indexed)
- `images/<label>/NNNNN.jpg` — same images copied into per-label folders
- `sheets/` — the 20 montage sheets used for labeling
