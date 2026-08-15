# Google Drive → WhatsApp Status Auto-Poster

Watches a Google Drive folder in the background. New products (photo/video +
a matching `.txt` details file) get downloaded and posted to WhatsApp
Status automatically — one at a time, media on top, description below.

Module: `actions/gdrive_status_poster.py`
Config: `config/gdrive_status_config.json`
State: `memory/gdrive_watch_state.json`, `memory/gdrive_processed_products.json`
Log: `logs/gdrive_whatsapp_status.log`

## One-time setup (do this before saying "start")

1. **Google Cloud service account**
   - Console → IAM & Admin → Service Accounts → Create → Keys → Add key (JSON).
   - Download the JSON, save it as `config/gdrive_service_account.json`
     (already gitignored — never commit this file).
2. **Share the Drive folder**
   - Right-click the folder you'll drop products into → Share → paste the
     service account's email (looks like `xyz@project.iam.gserviceaccount.com`)
     → Viewer access.
3. **Set the folder ID**
   - Copy the folder ID from the URL: `drive.google.com/drive/folders/<ID>`
   - Paste it into `gdrive_folder_id` in `config/gdrive_status_config.json`.
4. **Calibrate WhatsApp Status click coordinates** (one-time, this machine only)
   - Open WhatsApp Desktop.
   - Run: `python -c "import pyautogui,time; time.sleep(3); print(pyautogui.position())"`
     then hover your mouse over the **Status tab** before the 3s timer ends —
     note the (x, y) it prints, put it in `status_tab_x` / `status_tab_y`.
   - Repeat while hovering over the **Add Status (+/camera)** icon →
     `add_status_x` / `add_status_y`.
   - Repeat while hovering over the **caption text box** (after attaching a
     test image manually once) → `caption_box_x` / `caption_box_y` (optional
     — falls back to Tab-key navigation if left blank).

## Data format expected in the Drive folder

**Flat mode** — same base filename for media + details:
```
leather_backpack_tan.jpg
leather_backpack_tan.txt
```

**Subfolder mode** — one subfolder per product:
```
/WatchedFolder/product_001/media.jpg
/WatchedFolder/product_001/details.txt
```

**`details.txt` format** (simple `Key: Value` lines):
```
Name: Leather Backpack - Classic Tan
Brand: Signature Leather Co.
Size: 15L / 30x40x15cm
Price: AED 249
```

## Usage (voice/chat)

- "Jarvis, Drive se naya data status pe daalna shuru karo" → one-time
  approval, then it runs forever in the background, resuming automatically
  on every restart. Never asks again.
- "Jarvis, abhi check karo" → immediate poll, doesn't wait for the timer.
- "Jarvis, kitne products post hue" → status report.
- "Jarvis, status posting band karo" → stops it.

## Known limitation

The WhatsApp Status click-automation (`_post_whatsapp_status` in the
module) depends on the calibrated coordinates above — WhatsApp Desktop's
UI isn't exposed through stable automation IDs on most builds, so this is
coordinate-based (like the rest of this project's `send_message.py` /
`facebook_poster.py` browser-automation fallbacks). If WhatsApp updates
its layout, re-run the calibration step.
