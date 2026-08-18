"""
Enhanced TikTok Automation Module for Jarvis1
Handles direct Downloads folder video upload with auto-description & hashtag generation
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List
import subprocess
from datetime import datetime

# For TikTok API / Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - TikTok Automation - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tiktok_automation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TikTokAutomation:
    def __init__(self, config_path: str = "config.json"):
        """Initialize TikTok automation with config"""
        self.config = self._load_config(config_path)
        self.downloads_folder = Path.home() / "Downloads"
        self.client = anthropic.Anthropic(api_key=self.config.get("anthropic_api_key"))
        logger.info("TikTok Automation initialized")

    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file not found: {config_path}")
            return {
                "tiktok_username": "",
                "tiktok_password": "",
                "anthropic_api_key": "",
                "auto_hashtags": True,
                "hashtag_count": 10
            }

    def list_downloads_videos(self) -> List[Dict[str, str]]:
        """List all video files in Downloads folder"""
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
        videos = []
        
        try:
            for file in self.downloads_folder.iterdir():
                if file.is_file() and file.suffix.lower() in video_extensions:
                    videos.append({
                        'name': file.name,
                        'path': str(file),
                        'size_mb': round(file.stat().st_size / (1024 * 1024), 2),
                        'created': datetime.fromtimestamp(file.stat().st_ctime).strftime("%Y-%m-%d %H:%M")
                    })
            logger.info(f"Found {len(videos)} videos in Downloads")
            return sorted(videos, key=lambda x: x['created'], reverse=True)
        except Exception as e:
            logger.error(f"Error listing videos: {str(e)}")
            return []

    def generate_description_and_hashtags(self, video_name: str) -> Dict[str, str]:
        """Use Claude API to generate TikTok description and hashtags"""
        try:
            prompt = f"""
            You are a TikTok content expert. Based on this video filename: "{video_name}"
            
            Generate:
            1. A catchy, engaging TikTok description (max 150 chars, Urdu/English mix acceptable)
            2. {self.config.get('hashtag_count', 10)} relevant trending TikTok hashtags
            
            Return ONLY valid JSON:
            {{
                "description": "your description here",
                "hashtags": ["#hashtag1", "#hashtag2", ...]
            }}
            """
            
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            # Parse JSON response
            try:
                result = json.loads(response_text)
                logger.info(f"Generated description and hashtags for: {video_name}")
                return result
            except json.JSONDecodeError:
                # Fallback if Claude returns non-JSON
                logger.warning("Claude response was not valid JSON, using defaults")
                return {
                    "description": f"Check out this video: {video_name}",
                    "hashtags": ["#TikTok", "#Video", "#Viral", "#NewVideo"]
                }
        except Exception as e:
            logger.error(f"Error generating description: {str(e)}")
            return {
                "description": f"Video: {video_name}",
                "hashtags": ["#TikTok", "#Video"]
            }

    def upload_to_tiktok_selenium(self, video_path: str, description: str, hashtags: List[str]) -> bool:
        """
        Upload video to TikTok using Selenium
        Requires TikTok account credentials in config.json
        """
        driver = None
        try:
            logger.info(f"Starting TikTok upload for: {video_path}")
            
            # Initialize Chrome driver
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            driver = webdriver.Chrome(options=options)
            
            # Navigate to TikTok
            driver.get("https://www.tiktok.com/upload")
            
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
            )
            
            # Upload video file
            file_input = driver.find_element(By.XPATH, "//input[@type='file']")
            file_input.send_keys(os.path.abspath(video_path))
            logger.info("Video file uploaded to TikTok UI")
            
            # Wait for upload to process
            import time
            time.sleep(5)
            
            # Add description
            desc_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//textarea[@placeholder='Add description']"))
            )
            desc_field.click()
            desc_field.send_keys(description)
            logger.info("Description added")
            
            # Add hashtags to description if not already included
            hashtag_text = " ".join(hashtags)
            desc_field.send_keys(f"\n\n{hashtag_text}")
            logger.info(f"Hashtags added: {hashtag_text}")
            
            # Click Post button
            post_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Post')]"))
            )
            post_button.click()
            logger.info("Posted to TikTok successfully")
            
            # Wait for confirmation
            time.sleep(3)
            logger.info(f"Upload complete for: {os.path.basename(video_path)}")
            return True
            
        except Exception as e:
            logger.error(f"Selenium upload failed: {str(e)}")
            return False
        finally:
            if driver:
                driver.quit()

    def upload_to_tiktok_api(self, video_path: str, description: str, hashtags: List[str]) -> bool:
        """
        Upload video to TikTok using TikTok API (if credentials available)
        Requires TikTok API access token
        """
        try:
            if not self.config.get("tiktok_api_token"):
                logger.warning("TikTok API token not configured, falling back to Selenium")
                return self.upload_to_tiktok_selenium(video_path, description, hashtags)
            
            # TikTok API implementation would go here
            # This is a placeholder for API-based upload
            logger.info("TikTok API upload not yet fully implemented, using Selenium fallback")
            return self.upload_to_tiktok_selenium(video_path, description, hashtags)
            
        except Exception as e:
            logger.error(f"API upload failed: {str(e)}")
            return False

    def process_and_upload(self, video_name: str, use_description: bool = True, use_hashtags: bool = True) -> Dict:
        """
        Main workflow: Find video → Generate content → Upload to TikTok
        """
        result = {
            "success": False,
            "video_name": video_name,
            "message": "",
            "description": "",
            "hashtags": []
        }
        
        try:
            # Find video in Downloads
            videos = self.list_downloads_videos()
            video_match = next((v for v in videos if v['name'].lower() == video_name.lower()), None)
            
            if not video_match:
                result["message"] = f"Video '{video_name}' not found in Downloads folder"
                logger.error(result["message"])
                return result
            
            video_path = video_match['path']
            logger.info(f"Found video: {video_path}")
            
            # Generate description and hashtags
            generated_content = self.generate_description_and_hashtags(video_name)
            description = generated_content.get('description', '')
            hashtags = generated_content.get('hashtags', [])
            
            result["description"] = description
            result["hashtags"] = hashtags
            
            logger.info(f"Description: {description}")
            logger.info(f"Hashtags: {hashtags}")
            
            # Upload to TikTok
            upload_success = self.upload_to_tiktok_api(video_path, description, hashtags)
            
            if upload_success:
                result["success"] = True
                result["message"] = f"Video '{video_name}' successfully uploaded and posted to TikTok!"
            else:
                result["message"] = f"Upload failed for '{video_name}'. Check logs for details."
            
            return result
            
        except Exception as e:
            logger.error(f"Process failed: {str(e)}")
            result["message"] = f"Error during upload: {str(e)}"
            return result


# Integration with Jarvis voice commands
class TikTokVoiceIntegration:
    """Handles voice commands for TikTok automation"""
    
    def __init__(self):
        self.tiktok = TikTokAutomation()
    
    def handle_list_videos_command(self):
        """Voice command: 'List videos in Downloads'"""
        videos = self.tiktok.list_downloads_videos()
        if not videos:
            return "No videos found in Downloads folder."
        
        response = f"Found {len(videos)} videos:\n"
        for i, v in enumerate(videos[:5], 1):  # Show top 5
            response += f"{i}. {v['name']} ({v['size_mb']}MB)\n"
        return response
    
    def handle_upload_command(self, video_name: str):
        """Voice command: 'Upload [video_name] to TikTok'"""
        logger.info(f"Processing upload command for: {video_name}")
        result = self.tiktok.process_and_upload(video_name)
        
        if result['success']:
            return f"✓ {result['message']}\n\nDescription: {result['description']}\nHashtags: {' '.join(result['hashtags'])}"
        else:
            return f"✗ {result['message']}"


# Example usage
if __name__ == "__main__":
    # Initialize
    automation = TikTokAutomation()
    
    # List available videos
    print("Available videos in Downloads:")
    videos = automation.list_downloads_videos()
    for v in videos[:3]:
        print(f"  - {v['name']} ({v['size_mb']}MB)")
    
    # Example: Upload a video
    # result = automation.process_and_upload("example_video.mp4")
    # print(f"Upload result: {result}")
