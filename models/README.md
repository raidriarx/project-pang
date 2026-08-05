# Trained baseline models

These checkpoints classify cropped Buddha images into the five Project Pang classes:
`marawichai`, `samathi`, `nakprok`, `prathanphon`, and `saiyat`.

| model | test accuracy | test macro-F1 |
|---|---:|---:|
| ResNet-18 | 0.8830 | 0.8923 |
| MobileNet V3 Small | 0.8298 | 0.8379 |
| EfficientNet-B0 | 0.8830 | 0.8723 |

Each model directory contains:

- `best.pt`: the checkpoint selected by validation macro-F1. It contains `model`
  (the PyTorch state dictionary), `classes`, and `model_name`.
- `metrics.json`: training history, test metrics, and the per-class report.

`summary.json` provides the cross-model comparison. See `BASELINES.md` and
`scripts/train_baselines.py` for dependencies, preprocessing, splitting, and training.

Load a checkpoint with PyTorch:

```python
checkpoint = torch.load("models/resnet18/best.pt", map_location="cpu", weights_only=True)
model = build_model(checkpoint["model_name"], pretrained=False)
model.load_state_dict(checkpoint["model"])
model.eval()
```
