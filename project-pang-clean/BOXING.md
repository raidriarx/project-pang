# Boxing guide (for the box annotator)

You draw one box per photo around the statue that the pose label refers to.
The labeler labels; you box. You two never edit the same file, so git never conflicts:

- labeler commits **`human_labels.json`** (and only them)
- you commit **`boxes.json`** (and only you)

## One-time setup

```bash
git clone <this repo>          # or git pull if you have it
cd <folder with label_app.py>  # project-pang-clean/
python3 download_images.py     # rebuilds raw/ (2,372 photos) from manifest.csv — ~30-60 min
                               # (skip if someone gave you the raw-images zip: unzip it here instead)
python3 label_app.py
```

Open **http://localhost:8765/?mode=boxer**

## How to box

- The blue chip (top-left) tells you the pose label and shows the book example —
  **box the statue that matches that label** (matters when several statues are in frame).
- **Drag** a rectangle around the whole statue — include the naga hood above the head
  and the pedestal/serpent coils below. When in doubt, slightly too big beats too tight.
- A drag saves instantly and jumps to the next photo. That's the whole job.
- `Z` = remove last box · `←/→` = move around · `G` = go to a row number · `E` = big pose examples
- Labels are locked in boxer mode — you can't break anything.
- Progress bar top = boxed / queue. When it says the queue is empty, `git pull`
  to fetch newer labels, restart the app, and more photos will appear.

## Daily sync loop

```bash
git pull                                  # get the labeler's newest human_labels.json
python3 label_app.py                      # box until the queue is empty
git add boxes.json && git commit -m "boxes" && git push
```

Boxes are stored in original-image pixels of `raw/<row>.jpg` (row = manifest row),
as `{"row": {"box": [x, y, w, h], "by": "boxer", "ts": ...}}`.
