# Crypto YouTube Automation - JARVIS Integration

## Overview
Seamless crypto video generation pipeline for JARVIS. Generates production-ready scripts, voiceovers, editing specs, and SEO metadata.

## Features
- ✅ **5 content angles**: Bearish divergence, bullish breakout, options update, economic catalyst, liquidation cascade
- ✅ **TTS voiceover**: Edge-TTS integration with tone-based voice modulation
- ✅ **Scene specifications**: Detailed B-roll keywords, music BPM, voiceover tone per scene
- ✅ **SEO optimization**: 5 title variations, keyword-rich descriptions, CTR-optimized thumbnail text
- ✅ **Batch generation**: Generate multiple video variants in one run

## Installation

### 1. Add to JARVIS Requirements
```bash
cd /path/to/jarvis1
pip install edge-tts
```

### 2. Import Module
```python
from skills.youtube_crypto.crypto_video_generator import (
    CryptoVideoOrchestrator,
    ContentAngle
)
```

## Usage

### Quick Start: Generate Single Video Package
```python
import asyncio
from skills.youtube_crypto.crypto_video_generator import CryptoVideoOrchestrator, ContentAngle

async def generate_crypto_video():
    orchestrator = CryptoVideoOrchestrator(output_dir="./outputs/crypto_videos")
    
    # Generate video package (script + voiceover + scenes + SEO)
    package = await orchestrator.generate_video_package(
        angle=ContentAngle.BEARISH_DIVERGENCE
    )
    
    print(package)
    # Output:
    # {
    #     "angle": "bearish",
    #     "script": "./outputs/crypto_videos/script_bearish_20260817_143022.txt",
    #     "voiceover": "./outputs/crypto_videos/voiceover_bearish_20260817_143022.mp3",
    #     "scenes": "./outputs/crypto_videos/scenes_bearish_20260817_143022.json",
    #     "seo": "./outputs/crypto_videos/seo_bearish_20260817_143022.json",
    #     "timestamp": "20260817_143022"
    # }

asyncio.run(generate_crypto_video())
```

### Advanced: Batch Generate All Angles
```python
async def batch_generate():
    orchestrator = CryptoVideoOrchestrator(output_dir="./outputs/crypto_videos")
    
    results = {}
    for angle in ContentAngle:
        package = await orchestrator.generate_video_package(angle=angle)
        results[angle.value] = package
    
    # All video packages ready for Stage 3 (assembly)
    return results

asyncio.run(batch_generate())
```

### Integration with jarvis1 Actions
Add to `actions/youtube_crypto.py`:

```python
from skills.youtube_crypto.crypto_video_generator import CryptoVideoOrchestrator, ContentAngle
import asyncio

async def generate_crypto_analysis_video(angle: str = "bearish"):
    """
    Generate crypto analysis video package
    
    Args:
        angle: One of 'bearish', 'bullish', 'options', 'catalyst', 'liquidation'
    
    Returns:
        dict with paths to script, voiceover, scenes, and SEO metadata
    """
    
    angle_map = {
        "bearish": ContentAngle.BEARISH_DIVERGENCE,
        "bullish": ContentAngle.BULLISH_BREAKOUT,
        "options": ContentAngle.OPTIONS_UPDATE,
        "catalyst": ContentAngle.ECONOMIC_CATALYST,
        "liquidation": ContentAngle.LIQUIDATION_CASCADE,
    }
    
    orchestrator = CryptoVideoOrchestrator(
        output_dir="./outputs/crypto_videos"
    )
    
    content_angle = angle_map.get(angle.lower(), ContentAngle.BEARISH_DIVERGENCE)
    package = await orchestrator.generate_video_package(angle=content_angle)
    
    return package
```

## Output Structure

```
./crypto_videos/
├── script_bearish_20260817_143022.txt
│   └── Complete 5-minute script ready for TTS
├── voiceover_bearish_20260817_143022.mp3
│   └── Generated TTS audio
├── scenes_bearish_20260817_143022.json
│   └── Scene-by-scene editing breakdown
└── seo_bearish_20260817_143022.json
    └── SEO titles, descriptions, tags
```

### Script Format
```
[0-3s HOOK]
Bitcoin just hit a price only one percent of people predicted...

[3-30s MARKET SETUP]
When Bitcoin moves this fast, it's not random...

[30s RETENTION HOOK]
This technical indicator is lighting up red...

[30s-2:30m DATA BREAKDOWN]
Here's how this works...

...and so on
```

### Scenes JSON Format
```json
[
  {
    "name": "Hook",
    "duration_seconds": 3,
    "start_time": "0:00",
    "broll_keywords": ["Bitcoin spike", "candle wicks", "coin animation"],
    "voiceover_tone": "intense",
    "music_mood": "fast-paced electronic pulse",
    "music_bpm": 130
  },
  ...
]
```

### SEO JSON Format
```json
{
  "titles": [
    "Bitcoin Technical Analysis: The Signal Everyone's Missing (2026)",
    "Cryptocurrency Market Breakdown | What Smart Money Knows",
    ...
  ],
  "thumbnail_texts": [
    "Bitcoin Signal NOBODY Sees",
    "Crypto Market Move Predicted",
    ...
  ],
  "description": "In-depth cryptocurrency and blockchain analysis...",
  "tags": ["crypto", "cryptocurrency", "bitcoin", ...]
}
```

## Stage 3 Integration (Video Assembly)

Use the generated assets in your video assembly pipeline:

```python
# Pseudo-code for Stage 3
def assemble_video(video_package):
    script_path = video_package["script"]
    voiceover_path = video_package["voiceover"]
    scenes_path = video_package["scenes"]
    seo_path = video_package["seo"]
    
    # Load scenes
    scenes = json.load(open(scenes_path))
    
    # For each scene:
    for scene in scenes:
        # 1. Fetch B-roll via Pexels API using scene["broll_keywords"]
        broll = fetch_pexels(scene["broll_keywords"])
        
        # 2. Fetch music via Epidemic Sound using scene["music_bpm"] & scene["music_mood"]
        music_track = fetch_epidemic_sound(scene["music_mood"], scene["music_bpm"])
        
        # 3. Assemble scene in DaVinci/Premiere
        timeline.add_broll(broll, duration=scene["duration_seconds"])
        timeline.add_audio(voiceover_path, start=scene["start_time"])
        timeline.add_music(music_track, volume=0.3)
    
    # 4. Generate thumbnail using SEO data
    thumbnail = generate_thumbnail(seo_path["thumbnail_texts"][0])
    
    # 5. Export video
    video_file = timeline.export(format="mp4", resolution="1080p")
    
    return {
        "video": video_file,
        "thumbnail": thumbnail,
        "metadata": json.load(open(seo_path))
    }
```

## Content Angles

### 1. Bearish Divergence (DEFAULT)
- **Ideal for**: RSI showing bearish divergence, resistance rejection
- **Hook**: "Bitcoin just hit a price only 1% predicted. Here's what happens next."
- **Strategy**: Options spreads, hedged plays
- **CPM**: $12-15

### 2. Bullish Breakout
- **Ideal for**: Breaking above resistance, institutional accumulation signals
- **Hook**: "This Bitcoin setup has only triggered 3 times in history. All three times it printed gains."
- **Strategy**: Call spreads, breakout plays
- **CPM**: $14-17

### 3. Options Update
- **Ideal for**: Extreme put/call ratios, gamma exposure
- **Hook**: "Institutional put/call ratios just hit extreme levels. Here's what happens every time."
- **Strategy**: Contrarian plays
- **CPM**: $13-16

### 4. Economic Catalyst
- **Ideal for**: Major economic calendar events
- **Hook**: "Three data points drop this week. Here's exactly how each one moves Bitcoin."
- **Strategy**: Range trading, volatility plays
- **CPM**: $11-14

### 5. Liquidation Cascade
- **Ideal for**: High leverage, cascading liquidations predicted
- **Hook**: "Leverage is at peak levels. When this breaks, $500M in longs will liquidate."
- **Strategy**: Scalp setups, contrarian bounce plays
- **CPM**: $12-15

## Voice Configuration

Adjust TTS tone and personality:

```python
VOICE_CONFIGS = {
    "intense": {"rate": "+0%", "pitch": "+10Hz"},      # Urgent, commanding
    "analytical": {"rate": "+0%", "pitch": "+5Hz"},    # Sharp, confident
    "expert": {"rate": "-5%", "pitch": "+5Hz"},        # Slow, authoritative
    "confident": {"rate": "+0%", "pitch": "+8Hz"},     # Assured, persuasive
    "motivational": {"rate": "+5%", "pitch": "+12Hz"}, # Fast, energetic
}
```

## Production Timeline

| Step | Time | Tools |
|------|------|-------|
| Script generation | 1 min | `CryptoScriptGenerator` |
| TTS voiceover | 2 min | edge-tts |
| Scene export | 1 min | `CryptoSceneBuilder` |
| SEO metadata | 1 min | `CryptoSEOOptimizer` |
| **Total** | **~5 min** | Fully automated |

Then Stage 3 (video assembly) takes ~1 hour with template reuse.

## Performance Tracking

After upload, monitor:
- **CTR**: Target 8-12% (thumbnail performance)
- **AVD**: Target 65%+ (script pacing)
- **Subs gained**: Target 50+ per video
- **Watch time (24h)**: Target 5K+ minutes
- **Engagement**: Target 200+ likes/comments

Adjust subsequent angles based on metrics.

## File Structure

```
skills/youtube_crypto/
├── PRODUCTION_PACK.md              # Complete manual + specs
├── INTEGRATION.md                  # This file
├── crypto_video_generator.py       # Main module
├── requirements.txt                # Dependencies
└── config.json                     # Optional: custom templates
```

## Dependencies

```
edge-tts>=0.37.0
```

## Testing

```bash
# Run generator
python -m skills.youtube_crypto.crypto_video_generator

# Output directory
./crypto_videos/
```

## Next Steps

1. ✅ Stage 2 (script + voiceover) - **DONE** (this module)
2. ⏳ Stage 3 (video assembly + thumbnail) - Use outputs from this module
3. ⏳ Stage 4 (upload to YouTube) - Use existing YouTube actions

## Troubleshooting

**Edge-TTS not working?**
```bash
pip install --upgrade edge-tts
```

**Script too fast/slow?**
Adjust rate in `VOICE_CONFIG`: `"+0%"` (normal) → `"-5%"` (slower) or `"+5%"` (faster)

**Voiceover quality?**
Test different voices: `"en-US-AriaNeural"`, `"en-US-GuyNeural"`, `"en-US-JennyNeural"`

## Future Enhancements

- [ ] Dynamic script generation based on real-time market data
- [ ] Custom voice training for brand consistency
- [ ] Automatic B-roll fetching from Pexels API
- [ ] Auto-thumbnail generation with OCR optimization
- [ ] A/B title testing framework
- [ ] Real-time CPM tracking per angle

---

**Last Updated**: 2026-08-17  
**Module Status**: Production Ready ✅
