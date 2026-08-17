# Stage 3: Complete Workflow & Examples

## The Stage 3 Pipeline

```
Stage 2 Outputs          →  Stage 3 Processing        →  Stage 3 Outputs
──────────────────          ──────────────────────        ────────────────
voiceover.mp3               [1] Fetch B-roll             video.mp4 (1080p)
scenes.json                 [2] Select music             thumbnail.png
seo.json                    [3] Assemble video           metadata.json
                            [4] Generate thumbnail
                            ↓ 10-16 minutes
```

## Example 1: Single Video Assembly

```python
import asyncio
import os
from pathlib import Path
from skills.youtube_crypto.video_assembler import VideoAssemblyOrchestrator

async def generate_single_crypto_video():
    """Generate one crypto analysis video"""
    
    # Setup
    orchestrator = VideoAssemblyOrchestrator(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        output_dir="./output/videos"
    )
    
    # Stage 2 outputs (from crypto_video_generator.py)
    stage2_outputs = {
        "script": "./output/stage2/script_bearish_20260817_143022.txt",
        "voiceover": "./output/stage2/voiceover_bearish_20260817_143022.mp3",
        "scenes": "./output/stage2/scenes_bearish_20260817_143022.json",
        "seo": "./output/stage2/seo_bearish_20260817_143022.json"
    }
    
    # Verify files exist
    for name, path in stage2_outputs.items():
        if not Path(path).exists():
            raise FileNotFoundError(f"Missing {name}: {path}")
    
    # Run Stage 3
    result = await orchestrator.assemble_video_from_stage2_outputs(
        script_path=stage2_outputs["script"],
        voiceover_path=stage2_outputs["voiceover"],
        scenes_json_path=stage2_outputs["scenes"],
        seo_json_path=stage2_outputs["seo"],
        angle="bearish"
    )
    
    # Output
    print("\n✅ STAGE 3 COMPLETE")
    print(f"Video: {result['video']}")
    print(f"Thumbnail: {result['thumbnail']}")
    print(f"Size: {result['video_size_mb']:.1f} MB")
    print(f"Duration: ~5 minutes")
    
    # Ready for YouTube upload (Stage 4)
    return result

# Run it
if __name__ == "__main__":
    result = asyncio.run(generate_single_crypto_video())
```

## Example 2: Batch Generate Multiple Angles

```python
import asyncio
import os
from skills.youtube_crypto.crypto_video_generator import (
    CryptoVideoOrchestrator, 
    ContentAngle
)
from skills.youtube_crypto.video_assembler import VideoAssemblyOrchestrator

async def batch_generate_crypto_videos():
    """Generate all 5 crypto angles in sequence"""
    
    # Stage 2: Generate scripts + voiceovers
    stage2_orch = CryptoVideoOrchestrator(output_dir="./output/stage2")
    
    stage2_results = {}
    for angle in ContentAngle:
        print(f"\n[STAGE 2] Generating {angle.value}...")
        result = await stage2_orch.generate_video_package(angle=angle)
        stage2_results[angle.value] = result
    
    # Stage 3: Assemble videos
    stage3_orch = VideoAssemblyOrchestrator(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        output_dir="./output/stage3"
    )
    
    stage3_results = {}
    for angle_name, stage2_data in stage2_results.items():
        print(f"\n[STAGE 3] Assembling {angle_name}...")
        
        result = await stage3_orch.assemble_video_from_stage2_outputs(
            script_path=stage2_data["script"],
            voiceover_path=stage2_data["voiceover"],
            scenes_json_path=stage2_data["scenes"],
            seo_json_path=stage2_data["seo"],
            angle=angle_name
        )
        
        stage3_results[angle_name] = result
    
    # Summary
    print("\n" + "="*60)
    print("BATCH GENERATION COMPLETE")
    print("="*60)
    
    for angle, result in stage3_results.items():
        print(f"\n{angle.upper()}")
        print(f"  Video: {Path(result['video']).name}")
        print(f"  Size: {result['video_size_mb']:.1f} MB")
        print(f"  Title: {result['metadata']['title']}")
    
    return stage3_results

# Run it
if __name__ == "__main__":
    results = asyncio.run(batch_generate_crypto_videos())
```

## Example 3: Integration with JARVIS Actions

Create `actions/youtube_crypto_full_pipeline.py`:

```python
"""
Full YouTube Crypto Pipeline: Stage 2 → Stage 3 → Stage 4

One function call generates, assembles, and uploads video.
"""

import asyncio
import os
from pathlib import Path
from skills.youtube_crypto.crypto_video_generator import (
    CryptoVideoOrchestrator,
    ContentAngle
)
from skills.youtube_crypto.video_assembler import VideoAssemblyOrchestrator
from actions.youtube_upload import upload_video  # Existing action

async def generate_crypto_video_end_to_end(
    angle: str = "bearish",
    auto_upload: bool = False
) -> dict:
    """
    Complete pipeline: Stage 2 → Stage 3 → Stage 4
    
    Args:
        angle: Video angle ('bearish', 'bullish', 'options', 'catalyst', 'liquidation')
        auto_upload: Upload to YouTube automatically
    
    Returns:
        {
            "stage2": {...},
            "stage3": {...},
            "stage4": {...} or None
        }
    """
    
    # Map angle string to ContentAngle enum
    angle_map = {
        "bearish": ContentAngle.BEARISH_DIVERGENCE,
        "bullish": ContentAngle.BULLISH_BREAKOUT,
        "options": ContentAngle.OPTIONS_UPDATE,
        "catalyst": ContentAngle.ECONOMIC_CATALYST,
        "liquidation": ContentAngle.LIQUIDATION_CASCADE,
    }
    
    content_angle = angle_map.get(angle.lower())
    if not content_angle:
        raise ValueError(f"Invalid angle: {angle}")
    
    print(f"\n🚀 STAGE 2 → 3 → 4 PIPELINE: {angle}")
    print("="*60)
    
    # ======== STAGE 2: Generate Script + Voiceover ========
    print("\n[STAGE 2] Generating script + voiceover + specs...")
    stage2_orch = CryptoVideoOrchestrator(output_dir="./output/stage2")
    stage2_result = await stage2_orch.generate_video_package(angle=content_angle)
    print(f"✓ Voiceover: {Path(stage2_result['voiceover']).name}")
    
    # ======== STAGE 3: Assemble Video + Thumbnail ========
    print("\n[STAGE 3] Fetching B-roll + assembling video...")
    stage3_orch = VideoAssemblyOrchestrator(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        output_dir="./output/stage3"
    )
    
    stage3_result = await stage3_orch.assemble_video_from_stage2_outputs(
        script_path=stage2_result["script"],
        voiceover_path=stage2_result["voiceover"],
        scenes_json_path=stage2_result["scenes"],
        seo_json_path=stage2_result["seo"],
        angle=angle
    )
    print(f"✓ Video: {Path(stage3_result['video']).name}")
    print(f"✓ Thumbnail: {Path(stage3_result['thumbnail']).name}")
    
    # ======== STAGE 4: Upload to YouTube (Optional) ========
    stage4_result = None
    if auto_upload:
        print("\n[STAGE 4] Uploading to YouTube...")
        
        # Use existing YouTube upload action
        stage4_result = upload_video(
            video_path=stage3_result["video"],
            thumbnail_path=stage3_result["thumbnail"],
            title=stage3_result["metadata"]["title"],
            description=stage3_result["metadata"]["description"],
            tags=stage3_result["metadata"]["tags"],
            premiere_time=None,  # Upload immediately
            visibility="private"  # Start as private
        )
        print(f"✓ Uploaded: {stage4_result.get('youtube_url', 'pending')}")
    else:
        print("\n[STAGE 4] Skipped (auto_upload=False)")
        print("Run upload_to_youtube() to upload manually")
    
    # ======== SUMMARY ========
    print("\n" + "="*60)
    print("✅ PIPELINE COMPLETE")
    print("="*60)
    print(f"Angle: {angle}")
    print(f"Video: {Path(stage3_result['video']).name}")
    print(f"Size: {stage3_result['video_size_mb']:.1f} MB")
    print(f"Title: {stage3_result['metadata']['title']}")
    
    if not auto_upload:
        print(f"\n📤 To upload:")
        print(f"upload_to_youtube('{stage3_result['video']}', '{stage3_result['thumbnail']}')")
    
    return {
        "stage2": stage2_result,
        "stage3": stage3_result,
        "stage4": stage4_result,
        "angle": angle
    }


def upload_to_youtube(video_path: str, thumbnail_path: str):
    """Upload assembled video to YouTube"""
    # Wrapper for use after manual assembly
    from skills.youtube_crypto.video_assembler import VideoAssemblyOrchestrator
    import json
    
    # Extract metadata from nearby seo.json
    seo_path = video_path.replace(".mp4", ".json")
    if Path(seo_path).exists():
        with open(seo_path) as f:
            metadata = json.load(f)
    else:
        raise FileNotFoundError(f"Metadata not found: {seo_path}")
    
    return upload_video(
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        title=metadata["title"],
        description=metadata["description"],
        tags=metadata["tags"]
    )


# CLI
if __name__ == "__main__":
    import sys
    
    angle = sys.argv[1] if len(sys.argv) > 1 else "bearish"
    auto_upload = "--upload" in sys.argv
    
    asyncio.run(generate_crypto_video_end_to_end(angle, auto_upload))
```

**Usage:**
```bash
# Generate video (no upload)
python -c "from actions.youtube_crypto_full_pipeline import generate_crypto_video_end_to_end; \
import asyncio; asyncio.run(generate_crypto_video_end_to_end('bearish'))"

# Generate and upload
python -c "from actions.youtube_crypto_full_pipeline import generate_crypto_video_end_to_end; \
import asyncio; asyncio.run(generate_crypto_video_end_to_end('bullish', auto_upload=True))"
```

## Example 4: Monitor & Troubleshoot

```python
import subprocess
from pathlib import Path

def check_video_quality(video_path: str):
    """Verify video quality with FFprobe"""
    
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-show_entries", "stream=width,height,r_frame_rate,codec_name",
        "-of", "default=noprint_wrappers=1",
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"\nVideo Quality Check: {Path(video_path).name}")
    print(result.stdout)
    
    # Verify specs
    lines = result.stdout.strip().split("\n")
    specs = {}
    for line in lines:
        if "=" in line:
            key, value = line.split("=")
            specs[key] = value
    
    # Validate
    checks = {
        "resolution": specs.get("width") == "1920" and specs.get("height") == "1080",
        "framerate": "60" in specs.get("r_frame_rate", ""),
        "codec": specs.get("codec_name") == "h264",
    }
    
    print("\nValidation:")
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {check}")
    
    return all(checks.values())

def check_audio_sync(video_path: str, expected_duration: float = 300):
    """Verify audio/video sync"""
    
    cmd = [
        "ffmpeg", "-i", video_path,
        "-f", "null", "-"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    stderr = result.stderr
    
    # Extract duration
    import re
    duration_match = re.search(r"Duration: (\d+):(\d+):(\d+)", stderr)
    
    if duration_match:
        hours, mins, secs = map(int, duration_match.groups())
        total_seconds = hours * 3600 + mins * 60 + secs
        
        print(f"\nAudio/Video Sync Check:")
        print(f"  Video duration: {total_seconds}s (~{total_seconds/60:.1f} min)")
        print(f"  Expected: {expected_duration}s (~{expected_duration/60:.1f} min)")
        
        if abs(total_seconds - expected_duration) < 5:
            print("  ✓ Sync OK")
            return True
        else:
            print("  ✗ Sync issue - duration mismatch")
            return False

# Usage
if __name__ == "__main__":
    video = "./output/stage3/crypto_bearish_20260817_143022.mp4"
    
    check_video_quality(video)
    check_audio_sync(video, expected_duration=300)  # 5 minutes
```

## Example 5: Custom B-roll Fallback

If Pexels API is slow or unavailable:

```python
import asyncio
from pathlib import Path
from skills.youtube_crypto.video_assembler import (
    VideoAssemblyOrchestrator,
    BRollClip
)

# Pre-downloaded fallback B-roll library
FALLBACK_BROLL = {
    "Bitcoin spike": "./broll_library/bitcoin_spike.mp4",
    "candle wicks": "./broll_library/candles_red_green.mp4",
    "coin animation": "./broll_library/coin_loop_30s.mp4",
    "trading platform": "./broll_library/tradingview_charts.mp4",
    "RSI divergence": "./broll_library/rsi_divergence.mp4",
    "whale transactions": "./broll_library/on_chain_flow.mp4",
    # ... more keywords
}

async def assemble_with_fallback(orchestrator, scenes_json_path):
    """Use local B-roll library if Pexels fails"""
    
    import json
    with open(scenes_json_path) as f:
        scenes_spec = json.load(f)
    
    # For each scene, try Pexels first, fallback to local library
    for scene_spec in scenes_spec:
        keywords = scene_spec["broll_keywords"]
        
        try:
            # Try Pexels
            clips = await orchestrator.broll_fetcher.fetch_broll_for_scene(
                keywords=keywords,
                duration=scene_spec["duration_seconds"]
            )
            if clips:
                print(f"✓ Fetched from Pexels: {keywords[0]}")
                continue
        except Exception as e:
            print(f"⚠ Pexels failed for {keywords}: {e}")
        
        # Fallback to local library
        for keyword in keywords:
            if keyword in FALLBACK_BROLL:
                fallback_path = FALLBACK_BROLL[keyword]
                if Path(fallback_path).exists():
                    print(f"✓ Using fallback: {keyword} → {fallback_path}")
                    break
        else:
            raise FileNotFoundError(f"No B-roll available for: {keywords}")
```

## Performance Metrics

Track these after generating videos:

```python
import json
from pathlib import Path

def analyze_output(stage3_result: dict):
    """Analyze Stage 3 output"""
    
    video_path = stage3_result["video"]
    video_size_mb = stage3_result["video_size_mb"]
    
    print("\n📊 Output Analysis:")
    print(f"  File size: {video_size_mb:.1f} MB")
    print(f"  Video bitrate: ~{video_size_mb * 8 / 5 / 1000:.1f} Mbps (5 min)")
    print(f"  Codec: H.264 (fast preset, CRF 23)")
    print(f"  Duration: ~5 minutes")
    
    # Predict upload time to YouTube
    upload_speed_mbps = 25  # Average upload speed
    upload_time_minutes = (video_size_mb * 8) / upload_speed_mbps / 60
    print(f"\n📤 Upload estimation:")
    print(f"  At {upload_speed_mbps} Mbps: ~{upload_time_minutes:.1f} minutes")
    
    return {
        "file_size_mb": video_size_mb,
        "estimated_upload_minutes": upload_time_minutes
    }
```

---

**Total Pipeline Time:**
- Stage 2 (script + TTS): ~5 minutes
- Stage 3 (assembly): ~10-16 minutes
- **Total: ~15-21 minutes per video**

**With parallelization (batch angles):**
- Stage 2 (all 5 angles): ~10 minutes (parallel)
- Stage 3 (all 5 videos): ~10-16 minutes (sequential, can batch with more CPU)
- **Total: ~25-30 minutes for all 5 angles**
