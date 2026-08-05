# Baseline models

The baseline runner compares three compact ImageNet-pretrained classifiers on the five
Thai Buddha pose classes:

- ResNet-18
- MobileNet V3 Small
- EfficientNet-B0

It discovers images in `cropping/cropped-batch*/<class>/`, keeps only the newest copy
when the same source filename appears in more than one batch, and fails loudly if a
source filename has conflicting class labels. A seeded stratified 70/15/15 split is
shared by every model. Class-weighted cross entropy and macro-F1 reduce the impact of
the current class imbalance.

## Setup and training

From the repository root:

```powershell
python -m pip install -r requirements.txt
python scripts/train_baselines.py
```

For a quick smoke test or a CPU-only run:

```powershell
python scripts/train_baselines.py --models resnet18 --epochs 1 --device cpu
```

The first pretrained run downloads torchvision weights. Use `--no-pretrained` for a
fully offline (but typically much weaker) from-scratch comparison.

Outputs are written under `runs/baselines/`: one best checkpoint and `metrics.json`
per model, plus a shared `split.json` and cross-model `summary.json`. The `runs/`
directory is intentionally ignored so checkpoints and experiment output are not
committed.

## Stronger group-aware evaluation

The original holdout is useful for quick comparisons, but multiple photographs can
show the same statue. Run statue/temple-disjoint five-fold cross-validation for a more
credible generalization estimate:

```powershell
python scripts/train_group_cv.py --dry-run
python scripts/train_group_cv.py --models resnet18 --folds 5
```

The runner maps newer images through `batch*_manifest.csv` (`statue_id`) and older
row-indexed images through `labeled_clean.csv` (`wat`). Unmapped images become their
own source group. It reports mean and standard deviation across folds. Horizontal
flipping is now opt-in because left/right hand position can be semantically relevant;
use `--horizontal-flip` only as an explicit ablation. Both runners support
`--image-size 320`, early stopping, confusion matrices, and per-image prediction CSVs.
