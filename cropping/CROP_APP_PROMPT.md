# Prompt: build the cropping web app

Copy everything below the line into an AI coding assistant (Claude, ChatGPT, …) and it will generate the tool. Save the result as `crop_app.py` in the same folder as your unzipped `to-crop-batch1/`, run `python3 crop_app.py`, and open http://localhost:8770.

---

Build a single-file local web app, `crop_app.py`, for cropping statue photos. Requirements:

**Stack.** One Python 3 file using only the standard library (`http.server`, `json`, `pathlib`). No pip installs, no external assets, fully offline. The HTML/CSS/JS is one page embedded in the Python file. Serve on `127.0.0.1:8770` and send `Cache-Control: no-store` on every response.

**Input.** In the working directory there are one or more folders named `to-crop-batch<N>/` containing pose subfolders of JPEGs, e.g. `to-crop-batch1/marawichai/00616.jpg`. The pose names are: marawichai, samathi, nakprok, prathanphon, saiyat. Scan all batch folders at startup.

**Output.** For an input `to-crop-batch1/<pose>/<name>.jpg`, the crop is written to `cropped-batch1/<pose>/<name>.jpg` — mirrored path, same filename, folders auto-created. Also maintain `crops.json` mapping `"batch1/<pose>/<name>.jpg"` to `[x, y, w, h]` — the crop rectangle in the photo's own pixel coordinates — and `skipped.txt`, one relative path per line. Write JSON atomically (temp file + rename).

**Queue.** The work queue is every input photo that has no file yet in the mirrored `cropped-` path. Order by batch, then pose, then filename. On startup jump to the first un-cropped photo, so quitting and rerunning resumes automatically. When the queue is empty show a done message with counts.

**UI.** Dark theme, keyboard-first. Layout: a top bar showing pose name (large), batch, filename, and progress (`cropped / total` + a thin progress bar); the photo centered and as large as fits (`object-fit: contain`); a small footer with the key hints. Show a brief toast on every action.

**Cropping interaction.** Drag with the mouse to draw a rectangle over the photo (live dashed outline while dragging). On mouseup:
1. Convert the screen rectangle to the image's natural pixel coordinates (account for the letterboxed contain-fit: scale = min(displayedW/naturalW, displayedH/naturalH), centered offsets; clamp to image bounds; ignore drags smaller than 8×8 screen px).
2. Crop client-side with a `<canvas>`: draw the selected region, export `canvas.toBlob('image/jpeg', 0.95)`.
3. POST the JPEG bytes to the server (e.g. `/api/save?path=...` with the coordinate rectangle in a header or query params); the server writes the file and updates `crops.json`.
4. Advance to the next un-cropped photo automatically. Preload the next image.

**Keys.** `←`/`→` navigate freely · `Z` undo (delete the last saved crop file + its `crops.json` entry and return to that photo) · `S` skip (append to `skipped.txt`, advance) · `Esc` cancel a drag. Dragging again on an already-cropped photo replaces its crop. When revisiting a cropped photo, show its saved rectangle as a green outline (recompute from `crops.json` and the current display scale, reposition on window resize).

**Safety.** The server must only read/write inside the working directory (reject `..` in paths). Never modify the input photos.

**Acceptance checklist — verify each before delivering:** runs with plain `python3 crop_app.py` offline; drag produces a correctly-cropped JPEG at the mirrored path with the same filename; `crops.json` coordinates match the crop; restart resumes at the first un-cropped photo; `Z` really deletes and steps back; `S` records the skip; a photo can be re-cropped; no JS errors in the browser console.
