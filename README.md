# Project Pang — Thai Buddha Pose (Pang) Classification

A benchmark for classifying the **pose (ปาง / *pang*)** of Thai Buddha images into five
classes, built for ICCT 2026.

| | |
|---|---|
| **Dataset** | 826 statue images · 76 distinct statues · 5 classes |
| **Best model** | ResNet-18 on human crops — **macro-F1 0.795**, accuracy 0.845 |
| **Licensing** | 100% redistributable — CC BY-SA / CC BY / CC0 / PD, **zero NC or ND** |
| **Source** | Wikimedia Commons category crawl + human labelling |

---

## The five classes

| class | Thai | description | images | statues |
|---|---|---|---|---|
| `marawichai` | มารวิชัย | earth-touching; right hand over the knee, fingers down | 382 | 41 |
| `saiyat` | ไสยาสน์ | reclining | 146 | 11 |
| `nakprok` | นาคปรก | sheltered by the nāga | 126 | 14 |
| `samathi` | สมาธิ | meditation; both hands flat in the lap | 93 | 9 |
| `prathanphon` | ประทานพร | boon-giving; palm outward | 79 | 8 |

Plus two non-target labels used during annotation: `other` (a real Buddha statue in a
different pose — abhaya, walking, alms bowl) and `trash` with a degree
(1 = bad camera angle, 2 = poor quality, 3 = not a valid statue).

---

## Results

All numbers are **5-fold statue-grouped cross-validation** over 826 images, pooled
out-of-fold, with per-model tuned learning rates. Same folds and configs in every column
— only the input pixels differ.

| model | full image | **human crop** | auto crop |
|---|---|---|---|
| **ResNet-18** | 0.741 | **0.795** | 0.701 |
| EfficientNet-B0 | 0.721 | **0.790** | 0.715 |
| MobileNetV3-L | 0.650 | 0.718 | 0.688 |
| ViT-Tiny | 0.654 | 0.695 | 0.692 |
| **mean** | 0.692 | **0.750** | 0.699 |

### Per-class F1 (ResNet-18, human crops)

| marawichai | samathi | nakprok | prathanphon | saiyat |
|---|---|---|---|---|
| 0.891 | 0.682 | 0.755 | 0.676 | **0.973** |

### Automatic cropping

| cropper | mean IoU | downstream macro-F1 |
|---|---|---|
| human (reference) | — | 0.795 |
| trained box regressor | 0.639 | 0.701 |
| YOLOv8 zero-shot | 0.370 | 0.508 |

---

## Key findings

**1. Cropping to the statue is worth +0.058 macro-F1** — positive on all four
backbones, range +0.040 to +0.069. In a wide temple photograph the statue may occupy a
small fraction of the frame; cropping puts the pose evidence in view. The gain is
largest for `samathi` (+0.138), which is decided by hand position — a small,
low-contrast region that a whole-image view barely resolves.

**2. Automatic cropping does not yet pay for itself.** Mean gain over full images is
+0.007, and it *hurts* the two strongest models. A regressor at IoU 0.639 discards the
entire benefit that cropping buys. **Use human crops or no crops.** YOLO zero-shot is
far worse than either — COCO has no "statue" class, so it relies on `person`, which
fails completely on reclining figures (saiyat IoU 0.233).

**3. The evaluation split matters more than the model.** Photographs of one statue must
stay in the same fold. A stratified split lets a model memorise a statue seen in
training and recognise it at test time, measuring identity rather than pose. Removing
that leakage from an earlier split dropped ViT-Tiny from 0.569 to 0.470.

**4. Learning rate is the only hyperparameter that mattered**, and it must be set per
architecture — the optimum spans 30× (ViT-Tiny 1e-4, ResNet-18 3e-3). Layer-wise LR
decay, LP-then-FT, logit adjustment, and BatchNorm freezing were all neutral or harmful
at this data scale.

**5. Statue diversity is the ceiling.** 826 images rest on 76 statues; three classes have
fewer than 15. More photographs of statues already present will not help — only new
statues will.

---

## Repository layout

```
project-pang-clean/           dataset workspace
  manifest.csv                crawl metadata; ROW INDEX IS THE IMAGE ID
  human_labels.json           {row: {label, degree?, peeked, ts}}   pose labels
  boxes.json                  {row: {box:[x,y,w,h], by, ts}}        statue boxes
  labeled_clean.csv           per-row metadata incl. seed_category (statue unit)
  raw/                        raw/00042.jpg == manifest.csv row 42   (gitignored)
  label_app.py                labelling + boxing web app
  collect.py / collect2.py    Commons crawlers (collect2 is append-only)
  download_images.py          resumable image fetch

cropping/                     crop handoff with the box annotator
  cropped-batch*/             returned crops by class
  crops.json                  {batch/label/file.jpg: [x,y,w,h]}

scripts/, models/             baseline training + checkpoints
```

Training code lives outside this repo at `~/project-pang-train/` to keep the vault lean.

---

## Reproducing

```bash
# 1. dataset table + leakage-safe split
python3 prep2.py                 # -> data/dataset_v2.csv  (statue-family grouped)

# 2. crops from the human boxes
python3 label_app.py             # http://localhost:8765/?mode=boxer  to draw boxes

# 3. baselines
python train_crop_only.py        # 4 backbones on crops
python train_full_only.py        # 4 backbones on full images

# 4. automatic cropping
python cropper.py                # box regressor vs YOLO, IoU + downstream
```

### Training recipe

| parameter | value |
|---|---|
| optimizer | AdamW |
| batch size | 32 |
| schedule | 3-epoch warmup → cosine, 30 epochs |
| loss | class-weighted CE (inverse frequency), label smoothing 0.05 |
| input | 224 px |
| augmentation | RandomResizedCrop(0.7–1.0) + ColorJitter(0.2) |
| **horizontal flip** | **disabled** |
| weight decay | applied only to ndim>1 params (BN/bias excluded) |

Horizontal flip is off deliberately: which hand is raised and which way the palm faces
are class-defining, so mirroring an image teaches a false label.

Box regressor: ResNet-18 → sigmoid → (cx, cy, w, h) normalised, **L1 loss**, 40 epochs,
OneCycle lr 3e-4.

---

## Architecture invariants — do not break

- **Row index is the image ID.** `raw/00042.jpg` is row 42 of `manifest.csv`;
  `human_labels.json`, `labeled_clean.csv` and `boxes.json` all key on it.
  **Never re-run `collect.py` over an existing `raw/`** — it reorders the manifest and
  silently mismatches every label. Use `collect2.py`, which appends.
- **Boxes are in `raw/` pixel space.** Boxes drawn on full-resolution Commons originals
  must be rescaled by `raw_width / commons_width` on import. 46 boxes were wrong this
  way and produced crops of empty wall; see `boxes.json.bak-prescale-*`.
- **Pose labels and boxes live in separate files on purpose** so two annotators can work
  in parallel over git without merge conflicts.

---

## Known issues

- **12 mislabelled images.** All `Phra Buddha Angirasa` photos (Wat Ratchabophit) are
  labelled `nakprok` but depict `samathi`. Retained by decision; `nakprok` and `samathi`
  figures are mildly distorted.
- **`prathanphon` is provisional** — 79 images from 8 statues, and its Commons source
  category is a worldwide hand-gesture category that returns largely non-Thai
  bodhisattva sculpture. The class required manual curation.
- **`saiyat` may be partly separable by aspect ratio alone** (median 2.16 vs 0.50–0.85
  for the others). Its F1 of 0.973 should be read with that in mind.
- **Single seed.** Results are one 5-fold pass at seed 42. Measured seed-to-seed sd on
  this dataset ranges 0.005–0.068 by architecture; differences under ~0.05 between
  models are not meaningful.

---

## Licensing

All 826 images are redistributable: CC BY-SA (541), CC BY (178), CC0 (69),
public domain (37), FAL (1). **No NonCommercial or NoDerivatives images.**
Source URL is recorded for 100% of images and photographer credit for 99%.

Attribution for each image is in `manifest.csv` (`author`, `license`, `url`).
