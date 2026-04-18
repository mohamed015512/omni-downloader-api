
"""
Video Downloader Service - Core yt-dlp integration
Handles video URL extraction without downloading files to server
"""

import logging
import re
from typing import Dict, Optional, Any
from urllib.parse import urlparse

import yt_dlp

# Configure logging
logger = logging.getLogger(__name__)


class VideoDownloaderService:
    """Service class for extracting video download URLs using yt-dlp"""
    
    # Supported platforms
    SUPPORTED_PLATFORMS = {
        'facebook', 'fb', 'instagram', 'ig', 'tiktok', 'twitter', 'x'
    }
    
    # Blocked platforms (YouTube)
    BLOCKED_PLATFORMS = {
        'youtube', 'youtu.be', 'yewtu.be'
    }
    
    def __init__(self):
        """Initialize the downloader service with custom configuration"""
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Base yt-dlp options
        self.base_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'user_agent': self.user_agent,
            'headers': {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'nocheckcertificate': True,
            'prefer_insecure': False,
        }
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL for platform validation"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www prefix
            domain = re.sub(r'^www\.', '', domain)
            # Get main domain (remove subdomains)
            parts = domain.split('.')
            if len(parts) >= 2:
                return parts[-2] if len(parts) > 2 else parts[0]
            return domain
        except Exception:
            return None
    
    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is from YouTube or related platforms"""
        url_lower = url.lower()
        for blocked in self.BLOCKED_PLATFORMS:
            if blocked in url_lower:
                return True
        return False
    
    def _is_supported_platform(self, url: str) -> bool:
        """Check if URL is from a supported platform"""
        domain = self._extract_domain(url)
        if not domain:
            return False
        
        url_lower = url.lower()
        for platform in self.SUPPORTED_PLATFORMS:
            if platform in url_lower or platform in domain:
                return True
        return False
    
    def _get_format_options(self, quality: str = 'best') -> Dict[str, Any]:
        """Get format selection options based on quality preference"""
        formats = {
            'best': {'format': 'best[ext=mp4]/best'},
            'video_only': {'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'},
            'audio_only': {'format': 'bestaudio[ext=m4a]/bestaudio'},
        }
        return formats.get(quality, formats['best'])
    
    def extract_video_info(self, url: str, quality: str = 'best') -> Dict[str, Any]:
        """
        Extract video information and direct download URLs
        
        Args:
            url: Video URL to extract
            quality: Quality preference ('best', 'video_only', 'audio_only')
            
        Returns:
            Dictionary containing video info and download URLs
            
        Raises:
            ValueError: For blocked or unsupported URLs
            Exception: For extraction errors
        """
        # Validate URL
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")
        
        url = url.strip()
        
        # Block YouTube URLs
        if self._is_youtube_url(url):
            raise ValueError("YouTube URLs are not supported due to platform policies")
        
        # Check platform support
        if not self._is_supported_platform(url):
            raise ValueError(
                f"URL not supported. Supported platforms: Facebook, Instagram, TikTok, Twitter"
            )
        
        # Prepare extraction options
        format_opts = self._get_format_options(quality)
        ydl_opts = {**self.base_opts, **format_opts}
        
        try:
            logger.info(f"Extracting video info for URL: {url[:100]}...")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info without downloading
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise Exception("Failed to extract video information")
                
                # Extract download URL
                download_url = None
                if 'url' in info:
                    download_url = info['url']
                elif 'requested_formats' in info:
                    # Combined formats (video + audio)
                    for fmt in info['requested_formats']:
                        if 'url' in fmt:
                            download_url = fmt['url']
                            break
                elif 'formats' in info and info['formats']:
                    # Get best format URL
                    for fmt in info['formats']:
                        if fmt.get('url') and fmt.get('vcodec') != 'none':
                            download_url = fmt['url']
                            break
                    if not download_url and info['formats']:
                        download_url = info['formats'][0].get('url')
                
                if not download_url:
                    raise Exception("No downloadable URL found in extracted info")
                
                # Build response
                response = {
                    'success': True,
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                    'download_url': download_url,
                    'quality': quality,
                    'ext': info.get('ext', 'mp4'),
                    'filesize': info.get('filesize'),
                    'platform': self._extract_domain(url),
                }
                
                # Add available formats if needed
                if 'formats' in info and quality != 'best':
                    response['available_formats'] = [
                        {
                            'format_id': f.get('format_id'),
                            'ext': f.get('ext'),
                            'resolution': f.get('resolution'),
                            'filesize': f.get('filesize'),
                        }
                        for f in info.get('formats', [])
                        if f.get('vcodec') != 'none' or f.get('acodec') != 'none'
                    ][:10]  # Limit to 10 formats
                
                logger.info(f"Successfully extracted video: {response['title'][:50]}...")
                return response
                
        except Exception as e:
            logger.error(f"Extraction failed for URL {url}: {str(e)}")
            raise Exception(f"Video extraction failed: {str(e)}")
    
    def extract_audio_only(self, url: str) -> Dict[str, Any]:
        """Extract audio-only stream URL"""
        return self.extract_video_info(url, quality='audio_only')


# Singleton instance
downloader_service = VideoDownloaderService()
