"""Train reproducible image-classification baselines on the cropped Pang data."""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import StratifiedShuffleSplit
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


CLASSES = ("marawichai", "samathi", "nakprok", "prathanphon", "saiyat")
MODEL_NAMES = ("resnet18", "mobilenet_v3_small", "efficientnet_b0")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("cropping"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs/baselines"))
    parser.add_argument("--models", nargs="+", choices=MODEL_NAMES, default=list(MODEL_NAMES))
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--test-size", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="auto")
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def batch_number(path: Path) -> int:
    match = re.search(r"cropped-batch(\d+)$", path.name)
    return int(match.group(1)) if match else -1


def discover_samples(data_dir: Path) -> list[tuple[Path, int]]:
    """Use the newest crop for duplicates and reject cross-class label conflicts."""
    batches = sorted(data_dir.glob("cropped-batch*"), key=batch_number)
    if not batches:
        raise FileNotFoundError(f"No cropped-batch* directories found under {data_dir}")

    by_source: dict[str, tuple[Path, int]] = {}
    for batch in batches:
        for label_index, label in enumerate(CLASSES):
            label_dir = batch / label
            if not label_dir.is_dir():
                continue
            for path in sorted(label_dir.iterdir()):
                if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                source_id = path.name.casefold()
                previous = by_source.get(source_id)
                if previous is not None and previous[1] != label_index:
                    raise ValueError(
                        f"Conflicting labels for {path.name}: "
                        f"{CLASSES[previous[1]]} ({previous[0]}) vs {label} ({path})"
                    )
                by_source[source_id] = (path, label_index)

    samples = sorted(by_source.values(), key=lambda item: item[0].name.casefold())
    counts = Counter(label for _, label in samples)
    missing = [CLASSES[i] for i in range(len(CLASSES)) if counts[i] < 3]
    if missing:
        raise ValueError(f"Need at least 3 unique images per class; insufficient: {missing}")
    print("Unique samples:", {CLASSES[i]: counts[i] for i in range(len(CLASSES))})
    return samples


def split_samples(samples: list[tuple[Path, int]], val_size: float, test_size: float, seed: int):
    if val_size <= 0 or test_size <= 0 or val_size + test_size >= 1:
        raise ValueError("val-size and test-size must be positive and sum to less than 1")
    labels = np.array([label for _, label in samples])
    indices = np.arange(len(samples))
    outer = StratifiedShuffleSplit(n_splits=1, test_size=val_size + test_size, random_state=seed)
    train_idx, holdout_idx = next(outer.split(indices, labels))
    relative_test = test_size / (val_size + test_size)
    inner = StratifiedShuffleSplit(n_splits=1, test_size=relative_test, random_state=seed + 1)
    val_rel, test_rel = next(inner.split(holdout_idx, labels[holdout_idx]))
    return train_idx.tolist(), holdout_idx[val_rel].tolist(), holdout_idx[test_rel].tolist()


class PangDataset(Dataset):
    def __init__(self, samples, indices, transform):
        self.samples = samples
        self.indices = indices
        self.transform = transform

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, item: int):
        path, label = self.samples[self.indices[item]]
        with Image.open(path) as image:
            image = image.convert("RGB")
        return self.transform(image), label


def make_transforms():
    normalize = transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    train = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.15),
        transforms.ToTensor(),
        normalize,
    ])
    evaluate = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        normalize,
    ])
    return train, evaluate


def build_model(name: str, pretrained: bool) -> nn.Module:
    if name == "resnet18":
        model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT if pretrained else None)
        model.fc = nn.Linear(model.fc.in_features, len(CLASSES))
    elif name == "mobilenet_v3_small":
        model = models.mobilenet_v3_small(
            weights=models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
        )
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(CLASSES))
    elif name == "efficientnet_b0":
        model = models.efficientnet_b0(weights=models.EfficientNet_B0_Weights.DEFAULT if pretrained else None)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(CLASSES))
    else:
        raise ValueError(f"Unsupported model: {name}")
    return model


def choose_device(requested: str) -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def evaluate(model, loader, criterion, device):
    model.eval()
    loss_sum = 0.0
    targets, predictions = [], []
    with torch.inference_mode():
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            logits = model(images)
            loss_sum += criterion(logits, labels).item() * labels.size(0)
            targets.extend(labels.cpu().tolist())
            predictions.extend(logits.argmax(dim=1).cpu().tolist())
    metrics = {
        "loss": loss_sum / len(loader.dataset),
        "accuracy": accuracy_score(targets, predictions),
        "macro_f1": f1_score(targets, predictions, average="macro", zero_division=0),
    }
    return metrics, targets, predictions


def train_one(name, args, samples, split, device):
    train_idx, val_idx, test_idx = split
    train_tf, eval_tf = make_transforms()
    datasets = {
        "train": PangDataset(samples, train_idx, train_tf),
        "val": PangDataset(samples, val_idx, eval_tf),
        "test": PangDataset(samples, test_idx, eval_tf),
    }
    loaders = {
        key: DataLoader(ds, batch_size=args.batch_size, shuffle=key == "train",
                        num_workers=args.workers, pin_memory=device.type == "cuda")
        for key, ds in datasets.items()
    }
    train_labels = [samples[i][1] for i in train_idx]
    counts = np.bincount(train_labels, minlength=len(CLASSES))
    class_weights = len(train_labels) / (len(CLASSES) * counts)
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(class_weights, dtype=torch.float32, device=device))
    model = build_model(name, not args.no_pretrained).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    model_dir = args.output_dir / name
    model_dir.mkdir(parents=True, exist_ok=True)
    best_f1 = -1.0
    history = []
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        loss_sum = 0.0
        for images, labels in loaders["train"]:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            loss_sum += loss.item() * labels.size(0)
        scheduler.step()
        val_metrics, _, _ = evaluate(model, loaders["val"], criterion, device)
        row = {"epoch": epoch, "train_loss": loss_sum / len(datasets["train"]), **val_metrics}
        history.append(row)
        print(f"{name} epoch {epoch:02d}: val macro-F1={val_metrics['macro_f1']:.4f}")
        if val_metrics["macro_f1"] > best_f1:
            best_f1 = val_metrics["macro_f1"]
            torch.save({"model": model.state_dict(), "classes": CLASSES, "model_name": name}, model_dir / "best.pt")

    checkpoint = torch.load(model_dir / "best.pt", map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model"])
    test_metrics, targets, predictions = evaluate(model, loaders["test"], criterion, device)
    report = classification_report(targets, predictions, target_names=CLASSES, output_dict=True, zero_division=0)
    result = {
        "model": name,
        "pretrained": not args.no_pretrained,
        "seed": args.seed,
        "split_sizes": {key: len(value) for key, value in datasets.items()},
        "best_val_macro_f1": best_f1,
        "test": test_metrics,
        "classification_report": report,
        "training_seconds": time.time() - started,
        "history": history,
    }
    (model_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    samples = discover_samples(args.data_dir)
    split = split_samples(samples, args.val_size, args.test_size, args.seed)
    device = choose_device(args.device)
    print(f"Device: {device}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    split_manifest = {
        part: [str(samples[i][0]) for i in indices]
        for part, indices in zip(("train", "val", "test"), split)
    }
    (args.output_dir / "split.json").write_text(json.dumps(split_manifest, indent=2), encoding="utf-8")

    results = [train_one(name, args, samples, split, device) for name in args.models]
    summary = [
        {"model": row["model"], "val_macro_f1": row["best_val_macro_f1"], **row["test"]}
        for row in results
    ]
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
