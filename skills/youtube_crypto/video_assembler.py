"""
Stage 3: Video Assembly & Thumbnail Generation
Converts Stage 2 outputs (script, voiceover, scenes, SEO) into production-ready videos.

Pipeline:
1. Load voiceover (MP3) + scenes specification (JSON)
2. Fetch B-roll from Pexels API using scene keywords
3. Select background music (based on BPM/mood)
4. Assemble timeline with FFmpeg:
   - Layer B-roll video
   - Sync voiceover audio
   - Mix background music
5. Generate YouTube-ready thumbnail
6. Export final video (1080p/60fps)
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
from PIL import Image, ImageDraw, ImageFont
import os


@dataclass
class BRollClip:
    """Stock video clip specification"""
    url: str
    keyword: str
    duration: int  # seconds
    path: Optional[str] = None


@dataclass
class Scene:
    """Video scene with all assets"""
    name: str
    duration_seconds: int
    start_time: str
    broll_keywords: List[str]
    voiceover_tone: str
    music_mood: str
    music_bpm: int
    broll_clips: List[BRollClip] = None


class PexelsVideoFetcher:
    """Fetch stock video from Pexels API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Pexels fetcher
        
        Args:
            api_key: Pexels API key (or env var PEXELS_API_KEY)
        """
        self.api_key = api_key or os.getenv("PEXELS_API_KEY")
        if not self.api_key:
            raise ValueError("PEXELS_API_KEY environment variable not set")
        self.base_url = "https://api.pexels.com/videos/search"
        self.session = requests.Session()
        self.session.headers.update({"Authorization": self.api_key})
    
    def search_videos(
        self,
        query: str,
        per_page: int = 5,
        min_duration: int = 1
    ) -> List[dict]:
        """
        Search for videos on Pexels
        
        Args:
            query: Search query (e.g., "Bitcoin trading")
            per_page: Number of results
            min_duration: Minimum video duration in seconds
        
        Returns:
            List of video metadata dicts
        """
        params = {
            "query": query,
            "per_page": per_page,
            "min_duration": min_duration
        }
        
        response = self.session.get(self.base_url, params=params)
        response.raise_for_status()
        
        videos = response.json().get("videos", [])
        if not videos:
            print(f"⚠ No videos found for: {query}")
            return []
        
        return videos
    
    def get_best_video(self, query: str) -> Optional[dict]:
        """Get highest-quality video for query"""
        videos = self.search_videos(query, per_page=1)
        return videos[0] if videos else None
    
    def download_video(
        self,
        video_url: str,
        output_path: str,
        quality: str = "hd"
    ) -> str:
        """
        Download video file from URL
        
        Args:
            video_url: Direct video URL
            output_path: Where to save file
            quality: "sd" or "hd"
        
        Returns:
            Path to downloaded file
        """
        response = requests.get(video_url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✓ Downloaded: {output_path}")
        return output_path
    
    async def fetch_broll_for_scene(
        self,
        keywords: List[str],
        duration: int,
        output_dir: str = "./broll"
    ) -> List[BRollClip]:
        """
        Fetch B-roll clips for scene using multiple keywords
        
        Args:
            keywords: Search keywords
            duration: Total duration needed
            output_dir: Where to save clips
        
        Returns:
            List of BRollClip objects
        """
        Path(output_dir).mkdir(exist_ok=True)
        clips = []
        
        for keyword in keywords:
            video = self.get_best_video(keyword)
            if not video:
                continue
            
            # Get HD video URL
            video_files = video.get("video_files", [])
            hd_file = next(
                (f for f in video_files if f.get("quality") == "hd"),
                video_files[0] if video_files else None
            )
            
            if not hd_file:
                continue
            
            url = hd_file.get("link")
            clip_path = Path(output_dir) / f"{keyword.replace(' ', '_')}.mp4"
            
            # Download if not exists
            if not clip_path.exists():
                self.download_video(url, str(clip_path))
            
            clips.append(BRollClip(
                url=url,
                keyword=keyword,
                duration=min(duration, 30),  # Cap at 30s per clip
                path=str(clip_path)
            ))
            
            if len(clips) * 30 >= duration:
                break
        
        return clips


class BackgroundMusicSelector:
    """Select/provide background music based on mood/BPM"""
    
    # Local music library paths or URLs
    MUSIC_LIBRARY = {
        "fast-paced electronic pulse": {
            "bpm": 130,
            "url": None,  # Provide local path
            "local_path": "./music/fast_electronic.mp3"
        },
        "tension-building dramatic synth": {
            "bpm": 115,
            "local_path": "./music/tension_dramatic.mp3"
        },
        "focused analytical cinematic": {
            "bpm": 110,
            "local_path": "./music/analytical_cinematic.mp3"
        },
        "powerful building momentum": {
            "bpm": 125,
            "local_path": "./music/powerful_momentum.mp3"
        },
        "triumphant energetic": {
            "bpm": 140,
            "local_path": "./music/triumphant_energy.mp3"
        }
    }
    
    @classmethod
    def get_music_for_scene(cls, mood: str, bpm: int) -> Optional[str]:
        """
        Get music file path for scene
        
        Args:
            mood: Music mood description
            bpm: Beats per minute
        
        Returns:
            Path to music file or None
        """
        if mood not in cls.MUSIC_LIBRARY:
            print(f"⚠ No music found for mood: {mood}")
            return None
        
        music_info = cls.MUSIC_LIBRARY[mood]
        local_path = music_info.get("local_path")
        
        if local_path and Path(local_path).exists():
            return local_path
        
        print(f"⚠ Music file not found: {local_path}")
        return None


class ThumbnailGenerator:
    """Generate YouTube-ready thumbnails"""
    
    # YouTube thumbnail specs
    WIDTH = 1280
    HEIGHT = 720
    SAFE_MARGIN = 40
    
    def __init__(self):
        self.font_large = None
        self.font_medium = None
        self.font_small = None
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts for text rendering"""
        try:
            # Try to use system fonts
            font_size_large = 80
            font_size_medium = 60
            font_size_small = 40
            
            # Fallback to default if fonts unavailable
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
        except Exception as e:
            print(f"⚠ Font loading issue: {e}")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
    def create_thumbnail(
        self,
        text: str,
        bg_color: tuple = (255, 0, 0),  # Red background
        text_color: tuple = (255, 255, 255),  # White text
        accent_color: tuple = (255, 255, 0),  # Yellow accent
        output_path: str = "thumbnail.png"
    ) -> str:
        """
        Create YouTube thumbnail with text
        
        Args:
            text: Main text (5 words max)
            bg_color: Background RGB color
            text_color: Text RGB color
            accent_color: Accent stripe RGB color
            output_path: Output file path
        
        Returns:
            Path to generated thumbnail
        """
        # Create base image with background color
        img = Image.new("RGB", (self.WIDTH, self.HEIGHT), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Add accent stripe at bottom
        stripe_height = 80
        draw.rectangle(
            [(0, self.HEIGHT - stripe_height), (self.WIDTH, self.HEIGHT)],
            fill=accent_color
        )
        
        # Wrap text for multiple lines
        lines = self._wrap_text(text, max_width=12)
        
        # Calculate text positioning
        total_text_height = len(lines) * 70
        start_y = (self.HEIGHT - total_text_height) // 2
        
        # Draw text with outline for visibility
        outline_width = 3
        for line in lines:
            x = self.WIDTH // 2
            y = start_y
            
            # Draw outline
            for adj_x in range(-outline_width, outline_width + 1):
                for adj_y in range(-outline_width, outline_width + 1):
                    draw.text(
                        (x + adj_x, y + adj_y),
                        line,
                        font=self.font_large,
                        fill=(0, 0, 0),
                        anchor="mm"
                    )
            
            # Draw main text
            draw.text(
                (x, y),
                line,
                font=self.font_large,
                fill=text_color,
                anchor="mm"
            )
            
            start_y += 70
        
        # Save
        img.save(output_path)
        print(f"✓ Thumbnail generated: {output_path}")
        return output_path
    
    @staticmethod
    def _wrap_text(text: str, max_width: int) -> List[str]:
        """Wrap text to fit thumbnail"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            current_line.append(word)
            if len(" ".join(current_line)) > max_width:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines


class FFmpegVideoAssembler:
    """Assemble video using FFmpeg"""
    
    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        """
        Initialize video assembler
        
        Args:
            ffmpeg_path: Path to ffmpeg executable
        """
        self.ffmpeg_path = ffmpeg_path
    
    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is installed"""
        try:
            subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                check=True
            )
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            print("❌ FFmpeg not found. Install with: apt-get install ffmpeg")
            return False
    
    def assemble_scene(
        self,
        scene: Scene,
        voiceover_path: str,
        output_path: str,
        music_path: Optional[str] = None,
        music_volume: float = 0.3
    ) -> str:
        """
        Assemble single scene video
        
        Args:
            scene: Scene specification with B-roll clips
            voiceover_path: Path to voiceover MP3
            output_path: Where to save assembled scene
            music_path: Optional background music
            music_volume: Background music volume (0-1)
        
        Returns:
            Path to assembled scene video
        """
        if not self.check_ffmpeg():
            raise RuntimeError("FFmpeg not available")
        
        if not scene.broll_clips:
            raise ValueError("No B-roll clips for scene")
        
        # Build FFmpeg command
        cmd = [self.ffmpeg_path, "-y"]  # Overwrite output
        
        # Input: B-roll (loop if needed)
        for i, clip in enumerate(scene.broll_clips):
            cmd.extend(["-i", clip.path])
        
        # Input: Voiceover
        cmd.extend(["-i", voiceover_path])
        
        # Input: Background music (optional)
        if music_path and Path(music_path).exists():
            cmd.extend(["-i", music_path])
        
        # Filter complex: concat + audio mix
        filter_complex = self._build_filter_complex(
            scene,
            has_music=bool(music_path)
        )
        
        cmd.extend(["-filter_complex", filter_complex])
        
        # Output settings
        cmd.extend([
            "-c:v", "libx264",          # H.264 codec
            "-preset", "fast",          # Speed/quality tradeoff
            "-crf", "23",               # Quality (18-28, lower=better)
            "-c:a", "aac",              # Audio codec
            "-b:a", "128k",             # Audio bitrate
            "-ar", "48000",             # Sample rate
            "-r", "60",                 # Frame rate
            output_path
        ])
        
        # Run FFmpeg
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✓ Scene assembled: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            print(f"❌ FFmpeg error: {e.stderr.decode()}")
            raise
    
    def _build_filter_complex(
        self,
        scene: Scene,
        has_music: bool = False
    ) -> str:
        """
        Build FFmpeg filter complex for scene assembly
        
        Handles:
        - Multiple B-roll clips
        - Voiceover audio sync
        - Background music mixing
        """
        filters = []
        
        # Concat B-roll clips if multiple
        if len(scene.broll_clips) > 1:
            concat_inputs = "".join([f"[{i}:v]" for i in range(len(scene.broll_clips))])
            filters.append(f"{concat_inputs}concat=n={len(scene.broll_clips)}:v=1:a=0[v]")
            video_out = "[v]"
        else:
            video_out = "[0:v]"
        
        # Resize to 1080p
        filters.append(f"{video_out}scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2[v_scaled]")
        
        # Audio: voiceover + music
        voiceover_idx = len(scene.broll_clips)
        if has_music:
            music_idx = voiceover_idx + 1
            # Mix voiceover (loud) + music (quiet)
            filters.append(f"[{voiceover_idx}:a][{music_idx}:a]amix=inputs=2:duration=first:weights=1 0.3[a]")
            audio_out = "[a]"
        else:
            audio_out = f"[{voiceover_idx}:a]"
        
        return ";".join(filters) + f"[v_scaled]{audio_out}"
    
    def assemble_full_video(
        self,
        scenes_with_clips: List[Scene],
        voiceover_path: str,
        output_path: str,
        temp_dir: str = "./temp_scenes"
    ) -> str:
        """
        Assemble full video from multiple scenes
        
        Args:
            scenes_with_clips: List of Scene objects with B-roll clips
            voiceover_path: Path to full voiceover (already synced)
            output_path: Final video output path
            temp_dir: Temporary directory for scene files
        
        Returns:
            Path to final video
        """
        Path(temp_dir).mkdir(exist_ok=True)
        scene_files = []
        
        # Assemble each scene
        current_time = 0
        for i, scene in enumerate(scenes_with_clips):
            scene_output = Path(temp_dir) / f"scene_{i:02d}.mp4"
            
            # Extract voiceover segment for this scene
            scene_audio = Path(temp_dir) / f"voiceover_scene_{i:02d}.mp3"
            self._extract_audio_segment(
                voiceover_path,
                str(scene_audio),
                current_time,
                scene.duration_seconds
            )
            
            # Assemble scene
            self.assemble_scene(
                scene,
                str(scene_audio),
                str(scene_output)
            )
            
            scene_files.append(str(scene_output))
            current_time += scene.duration_seconds
        
        # Concat all scenes
        self._concat_videos(scene_files, output_path)
        
        print(f"✓ Full video assembled: {output_path}")
        return output_path
    
    def _extract_audio_segment(
        self,
        audio_path: str,
        output_path: str,
        start_time: int,
        duration: int
    ):
        """Extract audio segment using FFmpeg"""
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", audio_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    
    def _concat_videos(self, video_files: List[str], output_path: str):
        """Concatenate video files using FFmpeg"""
        
        # Create concat file
        concat_file = "concat_list.txt"
        with open(concat_file, 'w') as f:
            for video in video_files:
                f.write(f"file '{video}'\n")
        
        cmd = [
            self.ffmpeg_path, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
        
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        finally:
            # Cleanup
            Path(concat_file).unlink(missing_ok=True)


class VideoAssemblyOrchestrator:
    """Orchestrate complete Stage 3 pipeline"""
    
    def __init__(
        self,
        pexels_api_key: Optional[str] = None,
        output_dir: str = "./videos_assembled"
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.broll_fetcher = PexelsVideoFetcher(pexels_api_key)
        self.thumbnail_gen = ThumbnailGenerator()
        self.video_assembler = FFmpegVideoAssembler()
    
    async def assemble_video_from_stage2_outputs(
        self,
        script_path: str,
        voiceover_path: str,
        scenes_json_path: str,
        seo_json_path: str,
        angle: str = "bearish"
    ) -> dict:
        """
        Complete Stage 3 pipeline: convert Stage 2 outputs to final video
        
        Args:
            script_path: Path to stage 2 script file
            voiceover_path: Path to stage 2 voiceover MP3
            scenes_json_path: Path to stage 2 scenes.json
            seo_json_path: Path to stage 2 seo.json
            angle: Video angle name
        
        Returns:
            dict with paths to video, thumbnail, and metadata
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Load specifications
        with open(scenes_json_path) as f:
            scenes_spec = json.load(f)
        
        with open(seo_json_path) as f:
            seo_data = json.load(f)
        
        print(f"\n📹 Starting Stage 3 Assembly: {angle}_{timestamp}")
        print("=" * 60)
        
        # Step 1: Fetch B-roll for each scene
        print("\n[1/4] Fetching B-roll...")
        scenes_with_clips = []
        for scene_spec in scenes_spec:
            print(f"  • Fetching for: {scene_spec['name']}")
            
            clips = await self.broll_fetcher.fetch_broll_for_scene(
                keywords=scene_spec["broll_keywords"],
                duration=scene_spec["duration_seconds"],
                output_dir=str(self.output_dir / "broll")
            )
            
            scene_obj = Scene(
                name=scene_spec["name"],
                duration_seconds=scene_spec["duration_seconds"],
                start_time=scene_spec["start_time"],
                broll_keywords=scene_spec["broll_keywords"],
                voiceover_tone=scene_spec["voiceover_tone"],
                music_mood=scene_spec["music_mood"],
                music_bpm=scene_spec["music_bpm"],
                broll_clips=clips
            )
            scenes_with_clips.append(scene_obj)
        
        # Step 2: Select background music
        print("\n[2/4] Selecting background music...")
        music_path = BackgroundMusicSelector.get_music_for_scene(
            scenes_spec[0]["music_mood"],
            scenes_spec[0]["music_bpm"]
        )
        if music_path:
            print(f"  ✓ Music selected: {music_path}")
        else:
            print("  ⚠ No music available - video will be voiceover + B-roll only")
        
        # Step 3: Assemble video
        print("\n[3/4] Assembling video (this may take a few minutes)...")
        video_output = self.output_dir / f"crypto_{angle}_{timestamp}.mp4"
        
        self.video_assembler.assemble_full_video(
            scenes_with_clips=scenes_with_clips,
            voiceover_path=voiceover_path,
            output_path=str(video_output)
        )
        
        # Step 4: Generate thumbnail
        print("\n[4/4] Generating thumbnail...")
        thumbnail_text = seo_data["thumbnail_texts"][0]
        thumbnail_output = self.output_dir / f"thumbnail_{angle}_{timestamp}.png"
        
        self.thumbnail_gen.create_thumbnail(
            text=thumbnail_text,
            bg_color=(255, 0, 0),      # Red for crypto urgency
            text_color=(255, 255, 255),  # White text
            accent_color=(255, 255, 0),  # Yellow accent
            output_path=str(thumbnail_output)
        )
        
        print("\n" + "=" * 60)
        print("✅ STAGE 3 COMPLETE")
        print("=" * 60)
        
        return {
            "angle": angle,
            "video": str(video_output),
            "thumbnail": str(thumbnail_output),
            "metadata": {
                "title": seo_data["titles"][0],
                "description": seo_data["description"],
                "tags": seo_data["tags"],
                "thumbnail_text": thumbnail_text
            },
            "timestamp": timestamp,
            "video_size_mb": Path(video_output).stat().st_size / (1024 * 1024)
        }


# CLI Usage
async def main():
    """Example usage"""
    
    # Requires Stage 2 outputs
    stage2_outputs = {
        "script": "./crypto_videos/script_bearish_20260817_143022.txt",
        "voiceover": "./crypto_videos/voiceover_bearish_20260817_143022.mp3",
        "scenes": "./crypto_videos/scenes_bearish_20260817_143022.json",
        "seo": "./crypto_videos/seo_bearish_20260817_143022.json"
    }
    
    # Check if Stage 2 outputs exist
    for key, path in stage2_outputs.items():
        if not Path(path).exists():
            print(f"❌ Missing: {path}")
            print("Run Stage 2 first: python crypto_video_generator.py")
            return
    
    # Run Stage 3
    orchestrator = VideoAssemblyOrchestrator(
        pexels_api_key=os.getenv("PEXELS_API_KEY"),
        output_dir="./videos_assembled"
    )
    
    result = await orchestrator.assemble_video_from_stage2_outputs(
        script_path=stage2_outputs["script"],
        voiceover_path=stage2_outputs["voiceover"],
        scenes_json_path=stage2_outputs["scenes"],
        seo_json_path=stage2_outputs["seo"],
        angle="bearish"
    )
    
    print("\n📦 Output Package:")
    for key, value in result.items():
        if key != "metadata":
            print(f"  {key}: {value}")
    
    print("\n📋 Video Metadata:")
    print(json.dumps(result["metadata"], indent=2))


if __name__ == "__main__":
    asyncio.run(main())
