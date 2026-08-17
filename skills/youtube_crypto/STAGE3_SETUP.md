# Stage 3: Video Assembly & Thumbnail Generation - Setup Guide

## Overview

Stage 3 converts Stage 2 outputs into production-ready YouTube videos:

**Input (Stage 2):**
- `script_*.txt` - Video script
- `voiceover_*.mp3` - TTS audio
- `scenes_*.json` - Scene specifications with B-roll keywords + music BPM
- `seo_*.json` - Thumbnail text + titles + descriptions

**Output (Stage 3):**
- `crypto_*.mp4` - Final 1080p/60fps video
- `thumbnail_*.png` - YouTube-ready thumbnail
- `metadata.json` - SEO-optimized YouTube metadata

## Installation

### 1. Install Dependencies

```bash
cd skills/youtube_crypto
pip install -r requirements_stage3.txt
```

### 2. Install FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html or:
```bash
choco install ffmpeg
```

### 3. Get Pexels API Key

1. Go to https://www.pexels.com/api/
2. Click "Get API Key"
3. Sign up (free)
4. Copy your API key

Set environment variable:
```bash
export PEXELS_API_KEY="your_api_key_here"
```

Or add to `.env`:
```
PEXELS_API_KEY=your_api_key_here
```

## Quick Start

### Run Stage 3 Locally

```python
import asyncio
from video_assembler import VideoAssemblyOrchestrator

async def assemble_video():
    orchestrator = VideoAssemblyOrchestrator(
        pexels_api_key="your_api_key",
        output_dir="./videos_assembled"
    )
    
    result = await orchestrator.assemble_video_from_stage2_outputs(
        script_path="./crypto_videos/script_bearish_*.txt",
        voiceover_path="./crypto_videos/voiceover_bearish_*.mp3",
        scenes_json_path="./crypto_videos/scenes_bearish_*.json",
        seo_json_path="./crypto_videos/seo_bearish_*.json",
        angle="bearish"
    )
    
    print(f"✅ Video: {result['video']}")
    print(f"✅ Thumbnail: {result['thumbnail']}")
    print(f"✅ Size: {result['video_size_mb']:.1f} MB")

asyncio.run(assemble_video())
```

## Pipeline Breakdown

### [1/4] Fetch B-roll from Pexels

```python
fetcher = PexelsVideoFetcher(api_key="your_key")

# For each scene, fetch B-roll using keywords
clips = await fetcher.fetch_broll_for_scene(
    keywords=["Bitcoin spike", "candle wicks", "coin animation"],
    duration=3,  # 3 seconds
    output_dir="./broll"
)
```

**What happens:**
- Searches Pexels for each keyword
- Downloads highest-quality video
- Returns list of BRollClip objects with local paths

**Output:** `./broll/bitcoin_spike.mp4`, etc.

### [2/4] Select Background Music

```python
music_path = BackgroundMusicSelector.get_music_for_scene(
    mood="fast-paced electronic pulse",
    bpm=130
)
```

**Music Library Structure:**
```
./music/
├── fast_electronic.mp3          # 130 BPM, urgent
├── tension_dramatic.mp3         # 115 BPM, building
├── analytical_cinematic.mp3     # 110 BPM, focused
├── powerful_momentum.mp3        # 125 BPM, energetic
└── triumphant_energy.mp3        # 140 BPM, climactic
```

**Setup local music:**
1. License music from Epidemic Sound / Artlist / AudioJungle
2. Place in `./music/` with correct names
3. Ensure music tracks are royalty-free for YouTube

### [3/4] Assemble Video with FFmpeg

```python
assembler = FFmpegVideoAssembler()

assembler.assemble_full_video(
    scenes_with_clips=scenes_list,
    voiceover_path="voiceover.mp3",
    output_path="final_video.mp4"
)
```

**FFmpeg Pipeline:**
1. Load B-roll clips (concat if multiple per scene)
2. Load voiceover audio
3. Load background music
4. Apply filters:
   - Resize to 1920×1080
   - Scale/crop B-roll to fill frame
   - Mix audio (voiceover 100% + music 30%)
5. Encode with H.264 (fast preset, quality 23)
6. Export MP4 with AAC audio

**Output:** `crypto_bearish_20260817_143022.mp4` (~500-800 MB for 5 min)

### [4/4] Generate Thumbnail

```python
thumbnail_gen = ThumbnailGenerator()

thumbnail_gen.create_thumbnail(
    text="Bitcoin Signal NOBODY Sees",
    bg_color=(255, 0, 0),          # Red background
    text_color=(255, 255, 255),    # White text
    accent_color=(255, 255, 0),    # Yellow stripe
    output_path="thumbnail.png"
)
```

**Thumbnail Specs:**
- Resolution: 1280×720px
- Format: PNG
- Text: 5 words max (from SEO data)
- Colors: High contrast (red + white + yellow)
- Safe margin: 40px from edges

**Output:** `thumbnail_bearish_20260817_143022.png`

## Integration with JARVIS Actions

Add to `actions/youtube_crypto_stage3.py`:

```python
from skills.youtube_crypto.video_assembler import VideoAssemblyOrchestrator
import asyncio
import os

async def assemble_crypto_video(
    voiceover_path: str,
    scenes_json_path: str,
    seo_json_path: str,
    angle: str = "bearish"
) -> dict:
    """
    Stage 3: Assemble video from Stage 2 outputs
    
    Args:
        voiceover_path: Path to MP3 from Stage 2
        scenes_json_path: Path to scenes.json from Stage 2
        seo_json_path: Path to seo.json from Stage 2
        angle: Video angle ('bearish', 'bullish', etc.)
    
    Returns:
        {
            "video": "/path/to/video.mp4",
            "thumbnail": "/path/to/thumbnail.png",
            "metadata": {...},
            "video_size_mb": 650.5
        }
    """
    
    orchestrator = VideoAssemblyOrchestrator(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        output_dir="./videos_assembled"
    )
    
    result = await orchestrator.assemble_video_from_stage2_outputs(
        script_path=None,  # Not needed for Stage 3
        voiceover_path=voiceover_path,
        scenes_json_path=scenes_json_path,
        seo_json_path=seo_json_path,
        angle=angle
    )
    
    return result
```

## Full Workflow (Stage 2 → Stage 3 → Stage 4)

```python
# Stage 2: Generate script + voiceover + scenes + SEO
from skills.youtube_crypto.crypto_video_generator import CryptoVideoOrchestrator, ContentAngle

stage2_orchestrator = CryptoVideoOrchestrator()
stage2_result = await stage2_orchestrator.generate_video_package(
    angle=ContentAngle.BEARISH_DIVERGENCE
)

# Extract outputs
voiceover = stage2_result["voiceover"]
scenes_json = stage2_result["scenes"]
seo_json = stage2_result["seo"]

# Stage 3: Assemble video + generate thumbnail
from actions.youtube_crypto_stage3 import assemble_crypto_video

stage3_result = await assemble_crypto_video(
    voiceover_path=voiceover,
    scenes_json_path=scenes_json,
    seo_json_path=seo_json,
    angle="bearish"
)

# Stage 4: Upload to YouTube (existing action)
from actions.youtube_upload import upload_video

stage4_result = upload_video(
    video_path=stage3_result["video"],
    thumbnail_path=stage3_result["thumbnail"],
    title=stage3_result["metadata"]["title"],
    description=stage3_result["metadata"]["description"],
    tags=stage3_result["metadata"]["tags"]
)

print(f"✅ Video uploaded: {stage4_result['youtube_url']}")
```

## Performance & Optimization

### Video Assembly Time

| Component | Time | Notes |
|-----------|------|-------|
| Fetch B-roll (5 scenes) | 2-3 min | Depends on internet speed |
| Select music | 5 sec | Local library lookup |
| Assemble video | 8-12 min | FFmpeg encoding (fast preset) |
| Generate thumbnail | 2 sec | PIL image generation |
| **Total** | **10-16 min** | Can be parallelized |

### File Sizes

| File | Size | Notes |
|------|------|-------|
| Voiceover MP3 | 5-8 MB | 5 min audio |
| B-roll clips (total) | 100-200 MB | Multiple scenes, HD |
| Final video MP4 | 500-800 MB | 1080p/60fps, H.264 |
| Thumbnail PNG | 200-400 KB | 1280×720 |

### Optimization Tips

1. **Faster encoding:** Change preset from "fast" to "ultrafast" (lower quality)
   ```python
   "-preset", "ultrafast",  # 2x faster, slightly lower quality
   ```

2. **Smaller file:** Increase CRF from 23 to 28
   ```python
   "-crf", "28",  # Smaller file, some quality loss
   ```

3. **Parallel B-roll fetching:** Fetch multiple scenes simultaneously
   ```python
   import asyncio
   tasks = [fetcher.fetch_broll_for_scene(...) for scene in scenes]
   results = await asyncio.gather(*tasks)
   ```

## Troubleshooting

### FFmpeg not found
```
❌ FFmpeg not found. Install with: apt-get install ffmpeg
```
**Solution:** Install FFmpeg (see Installation section)

### Pexels API 429 (Rate Limited)
```
⚠ Pexels API rate limit exceeded
```
**Solution:** Add retry logic with exponential backoff
```python
import time
time.sleep(2)  # Wait 2 seconds before retry
```

### Video audio out of sync
**Cause:** Voiceover duration doesn't match scene timing

**Solution:** Check voiceover MP3 duration:
```bash
ffprobe -v error -show_entries format=duration voiceover.mp3
```

Adjust scene timings in `scenes_*.json` to match voiceover.

### No B-roll found for keyword
```
⚠ No videos found for: Bitcoin trading
```
**Solution:** Provide fallback keywords or use generic footage
```python
keywords = ["Bitcoin trading", "crypto charts", "financial data"]  # Fallback
```

### Thumbnail text too small
**Solution:** Adjust font size in `ThumbnailGenerator._load_fonts()`
```python
font_size_large = 100  # Increase from 80
```

## Advanced: Custom B-roll Fallback

If Pexels API fails, use local B-roll library:

```python
FALLBACK_BROLL = {
    "Bitcoin spike": "./broll_library/btc_spike.mp4",
    "candle wicks": "./broll_library/candles.mp4",
    "coin animation": "./broll_library/coin_loop.mp4",
}

def fetch_with_fallback(keyword, fetcher):
    try:
        clips = await fetcher.fetch_broll_for_scene([keyword], 30)
        return clips
    except Exception:
        fallback_path = FALLBACK_BROLL.get(keyword)
        if fallback_path:
            return [BRollClip(url=None, keyword=keyword, duration=30, path=fallback_path)]
        raise
```

## Next Steps

1. ✅ Install FFmpeg + Pexels API key
2. ✅ Run Stage 2: `python crypto_video_generator.py`
3. ✅ Run Stage 3: `python video_assembler.py`
4. ⏳ Stage 4: Upload to YouTube (use existing action)
5. ⏳ Monitor metrics (CTR, AVD, watch time)

## File Structure

```
skills/youtube_crypto/
├── PRODUCTION_PACK.md           # Complete specs
├── INTEGRATION.md               # Stage 2 integration
├── STAGE3_SETUP.md             # This file
├── crypto_video_generator.py    # Stage 2: Script + TTS
├── video_assembler.py           # Stage 3: Video assembly
├── requirements.txt             # Stage 2 deps
├── requirements_stage3.txt      # Stage 3 deps
└── README.md                    # Overview
```

## Environment Variables

Create `.env` in jarvis1 root:
```
PEXELS_API_KEY=your_api_key
FFMPEG_PATH=/usr/bin/ffmpeg  # Optional, if FFmpeg not in PATH
```

Load in Python:
```python
from dotenv import load_dotenv
import os

load_dotenv()
pexels_key = os.getenv("PEXELS_API_KEY")
```

## Support

- FFmpeg docs: https://ffmpeg.org/documentation.html
- Pexels API: https://www.pexels.com/api/documentation/
- PIL/Pillow: https://pillow.readthedocs.io/

---

**Last Updated:** 2026-08-17  
**Status:** Production Ready ✅
