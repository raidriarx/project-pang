# Cropping — Project Pang

Photos of Thai Buddha statues, pre-sorted by pose, that need to be cropped down to just the statue. The crops become training data for a pose-classification model (ICCT 2026 paper), so consistency matters more than speed.

## Get the photos

Open **`to-crop-batch1.zip`** in this folder → **Download raw file** → unzip.

You'll find one subfolder per pose — `marawichai/`, `samathi/`, `nakprok/`, `prathanphon/`, `saiyat/` — 111 photos in batch 1. Filenames are dataset row numbers: they are how everything is matched back, so **never rename a file**.

## Crop the photos

**Option A — the cropping app (recommended).** Open **`CROP_APP_PROMPT.md`** in this folder, paste its contents into an AI assistant (Claude, ChatGPT, …), and it will generate a small local web app: you drag a rectangle on each photo, it saves the crop with the correct name in the correct folder and steps to the next one. Batch 1 takes well under an hour this way, and it also records the crop coordinates, which we can use directly.

**Option B — any image editor.** Preview, Photos, Paint, a phone gallery — all fine. Crop each photo and save it under the **same filename**, inside a folder structure mirroring the input (`cropped-batch1/marawichai/00616.jpg`, …). Export as JPEG at high quality; no resizing, rotating, or filters — crop only.

## Crop guidelines

- Include the **entire statue**: the naga/serpent hood **above** the head and the pedestal or coiled-serpent base **below** are part of it.
- Too wide beats too tight — a small margin around the statue is good.
- Several statues in frame → crop the **largest/front statue matching the folder's pose** (pose reference: marawichai = right hand over the knee pointing down · samathi = both hands stacked in the lap · nakprok = serpent hood over the head · prathanphon = right hand open, palm up on the knee · saiyat = reclining).
- If a photo can't be cropped sensibly (statue barely visible, doesn't match the pose), skip it and list the filename in `skipped.txt`.

## Return the results

1. Zip your output as **`cropped-batch1.zip`** (include `crops.json` and `skipped.txt` if you have them).
2. On this GitHub page open the `cropping` folder → **Add file → Upload files** → drag the zip in → **Commit changes**.

Further batches will appear here as `to-crop-batch2.zip`, `to-crop-batch3.zip`, … as labeling progresses; the workflow stays the same.
