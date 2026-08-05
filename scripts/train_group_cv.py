"""Run statue-disjoint stratified cross-validation for Project Pang baselines."""

from __future__ import annotations

import argparse
import csv
import json
import re
from copy import copy
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedGroupKFold

import train_baselines as baseline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("cropping"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/group_cv"))
    parser.add_argument("--models", nargs="+", choices=baseline.MODEL_NAMES, default=["resnet18"])
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--image-size", type=int, default=224)
    parser.add_argument("--early-stopping-patience", type=int, default=4)
    parser.add_argument("--horizontal-flip", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")
    parser.add_argument("--dry-run", action="store_true", help="Validate groups and print fold composition only")
    return parser.parse_args()


def read_csv(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_group_lookup(repo_root: Path, data_dir: Path):
    page_groups = {}
    for manifest in data_dir.glob("batch*_manifest.csv"):
        for row in read_csv(manifest):
            page_id = row.get("page_id", "").strip()
            if page_id:
                page_groups[page_id] = row.get("statue_id", "").strip() or page_id

    row_groups = {}
    labels_path = repo_root / "project-pang-clean" / "labeled_clean.csv"
    for row in read_csv(labels_path):
        row_id = row.get("_row", "").strip()
        if row_id:
            row_groups[str(int(row_id))] = row.get("wat", "").strip() or row.get("file_name", "").strip()
    return page_groups, row_groups


def group_for(path: Path, page_groups, row_groups) -> str:
    leading_id = re.match(r"^(\d+)", path.stem)
    if leading_id and leading_id.group(1) in page_groups:
        return "statue:" + page_groups[leading_id.group(1)].casefold()
    if path.stem.isdigit():
        row_id = str(int(path.stem))
        if row_id in row_groups:
            return "legacy:" + row_groups[row_id].casefold()
    return "source:" + path.name.casefold()


def fold_summary(samples, train_idx, test_idx, groups):
    result = {}
    for part, indices in (("train", train_idx), ("test", test_idx)):
        counts = np.bincount([samples[i][1] for i in indices], minlength=len(baseline.CLASSES))
        result[part] = {
            "images": len(indices),
            "groups": len({groups[i] for i in indices}),
            "class_counts": dict(zip(baseline.CLASSES, counts.tolist())),
        }
    return result


def main() -> None:
    args = parse_args()
    if args.folds < 2:
        raise ValueError("--folds must be at least 2")
    baseline.seed_everything(args.seed)
    samples = baseline.discover_samples(args.data_dir)
    repo_root = Path(__file__).resolve().parents[1]
    page_groups, row_groups = build_group_lookup(repo_root, args.data_dir)
    groups = np.array([group_for(path, page_groups, row_groups) for path, _ in samples])
    labels = np.array([label for _, label in samples])
    splitter = StratifiedGroupKFold(n_splits=args.folds, shuffle=True, random_state=args.seed)
    folds = list(splitter.split(np.arange(len(samples)), labels, groups))
    summaries = [fold_summary(samples, train, test, groups) for train, test in folds]
    print(json.dumps(summaries, indent=2))
    if args.dry_run:
        return

    device = baseline.choose_device(args.device)
    all_results = []
    for fold_number, (train_idx, test_idx) in enumerate(folds, start=1):
        # A deterministic slice of the training groups supplies validation data.
        inner = StratifiedGroupKFold(n_splits=args.folds, shuffle=True, random_state=args.seed + fold_number)
        inner_train_rel, val_rel = next(inner.split(train_idx, labels[train_idx], groups[train_idx]))
        fold_train = train_idx[inner_train_rel].tolist()
        fold_val = train_idx[val_rel].tolist()
        fold_test = test_idx.tolist()
        fold_args = copy(args)
        fold_args.output_dir = args.output_dir / f"fold_{fold_number}"
        for model_name in args.models:
            result = baseline.train_one(model_name, fold_args, samples, (fold_train, fold_val, fold_test), device)
            all_results.append({"fold": fold_number, **result})

    aggregate = []
    for model_name in args.models:
        rows = [row for row in all_results if row["model"] == model_name]
        for metric in ("accuracy", "macro_f1"):
            values = np.array([row["test"][metric] for row in rows])
            aggregate.append({"model": model_name, "metric": metric, "mean": values.mean(), "std": values.std(ddof=1)})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "cv_summary.json").write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()
