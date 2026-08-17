# YouTube Crypto Automation Skill

Professional cryptocurrency video generation for JARVIS. Generates complete video packages with scripts, voiceovers, editing specs, and SEO optimization.

## 📦 What's Included

- **PRODUCTION_PACK.md** - Complete 5-minute script template, scene breakdown, asset checklist, and production timeline
- **crypto_video_generator.py** - Main Python module with script generation, TTS, scene builder, and SEO optimizer
- **INTEGRATION.md** - Step-by-step integration guide for JARVIS workflow
- **requirements.txt** - Dependencies (edge-tts)

## 🚀 Quick Start

```python
import asyncio
from crypto_video_generator import CryptoVideoOrchestrator, ContentAngle

async def main():
    orchestrator = CryptoVideoOrchestrator()
    package = await orchestrator.generate_video_package(
        angle=ContentAngle.BEARISH_DIVERGENCE
    )
    print(package)

asyncio.run(main())
```

## 📊 5 Content Angles

1. **Bearish Divergence** - RSI divergence, resistance rejection
2. **Bullish Breakout** - Institutional accumulation, breakout plays
3. **Options Update** - Put/call ratios, gamma exposure
4. **Economic Catalyst** - Fed events, data releases, volatility plays
5. **Liquidation Cascade** - High leverage, liquidation zones

## ✨ Features

- ✅ Production-ready 5-minute scripts
- ✅ AI voiceover generation (edge-tts)
- ✅ Scene-by-scene editing specs (B-roll keywords, music BPM, voice tone)
- ✅ SEO optimization (5 title variations, keyword-rich descriptions)
- ✅ High-CTR thumbnail text ideas
- ✅ Multi-angle batch generation
- ✅ Fully integrated with JARVIS workflow

## 📁 Output Files

Each generation produces:
- `script_*.txt` - Complete video script
- `voiceover_*.mp3` - TTS audio file
- `scenes_*.json` - Editing breakdown
- `seo_*.json` - SEO metadata

## 💰 Monetization

| Niche | CPM | Audience |
|-------|-----|----------|
| Crypto Analysis | $12-20 | Traders, investors, enthusiasts |

High-value advertisers (trading platforms, blockchain companies) = premium CPM.

## 🎯 Production Timeline

- Script generation: 1 min
- TTS voiceover: 2 min
- Scene export: 1 min
- SEO metadata: 1 min
- **Total automation: ~5 min**

Manual video assembly (Stage 3): ~1 hour

## 📚 Documentation

- See **PRODUCTION_PACK.md** for complete specifications
- See **INTEGRATION.md** for JARVIS integration examples
- See **crypto_video_generator.py** for API documentation

## 🔧 Installation

```bash
pip install -r requirements.txt
```

## 📖 Usage Examples

### Generate single video
```python
await orchestrator.generate_video_package(angle=ContentAngle.BEARISH_DIVERGENCE)
```

### Generate all angles
```python
for angle in ContentAngle:
    await orchestrator.generate_video_package(angle=angle)
```

### Custom voiceover
```python
voiceover_gen = CryptoVoiceoverGenerator()
await voiceover_gen.generate_voiceover(
    script="Your script here",
    output_path="output.mp3",
    voice="en-US-GuyNeural",
    tone="intense"
)
```

### Export scene breakdown
```python
scene_builder = CryptoSceneBuilder()
scene_builder.export_to_json("scenes.json")
```

### Get SEO metadata
```python
seo_optimizer = CryptoSEOOptimizer()
metadata = seo_optimizer.get_seo_metadata(ContentAngle.BEARISH_DIVERGENCE)
seo_optimizer.export_metadata(metadata, "seo.json")
```

## 🎬 Integration with Stage 3 (Video Assembly)

The generated assets feed directly into your video assembly pipeline:

1. **Script** → Parse and sync with voiceover timing
2. **Voiceover** → Core audio layer
3. **Scenes JSON** → Use B-roll keywords to fetch stock footage from Pexels API
4. **Scenes JSON** → Use music BPM/mood to fetch tracks from Epidemic Sound
5. **SEO JSON** → Generate thumbnail using thumbnail_text suggestions
6. **SEO JSON** → Populate YouTube metadata (title, description, tags)

See **INTEGRATION.md** for detailed assembly examples.

## 🔄 Workflow

```
Stage 2 (This Module)          →  Stage 3 (Video Assembly)    →  Stage 4 (Upload)
Generate script + voiceover       Fetch B-roll + music          YouTube upload
Export scenes + SEO               Assemble timeline              Set premiere
                                  Generate thumbnail             Monitor metrics
```

## 🎨 Customization

### Voice Tones
```python
"intense", "analytical", "expert", "confident", "motivational"
```

### Music BPM
Each scene has recommended BPM (110-140 range). Adjust in `SCENE_TEMPLATES` as needed.

### Script Variations
Edit templates in `SCRIPT_TEMPLATES` dictionary to customize angles.

## 📊 Performance Metrics

Monitor after upload:
- **CTR**: 8-12% (thumbnail quality)
- **AVD**: 65%+ (script pacing)
- **Subs**: 50+ per video
- **Watch time (24h)**: 5K+ minutes
- **Engagement**: 200+ interactions

## 🆘 Troubleshooting

**Edge-TTS errors?**
```bash
pip install --upgrade edge-tts
```

**Script timing off?**
Adjust voice rate in `VOICE_CONFIG`: `"-5%"` (slower), `"+5%"` (faster)

**Different voice?**
Try: `"en-US-GuyNeural"`, `"en-US-JennyNeural"`, or other Microsoft Azure voices.

## 🚀 Next Steps

- [x] Stage 2: Script + TTS (COMPLETE)
- [ ] Stage 3: Video assembly (Use outputs here)
- [ ] Stage 4: YouTube upload (Existing action)
- [ ] Real-time market data integration
- [ ] Auto-thumbnail generation
- [ ] A/B title testing

## 📝 Version

**v1.0.0** - Production ready

## 📧 Questions?

Refer to INTEGRATION.md or see crypto_video_generator.py source code.
