"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CupGet API - Ultimate Downloader                        ║
║                      أقوى وأذكى سيرفر تحميل فيديوهات في العالم                  ║
║                           الكود الكامل - النسخة النهائية                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any, Literal
import asyncio
import aiohttp
import hashlib
import logging
import re
import time
import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
import yt_dlp
from bs4 import BeautifulSoup
import m3u8
from cachetools import TTLCache
import uvicorn

# ==================== إعدادات السيرفر ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CupGet-API")

CACHE_TTL = 300 
MAX_CACHE_SIZE = 1000
REQUEST_TIMEOUT = 60
response_cache = TTLCache(maxsize=MAX_CACHE_SIZE, ttl=CACHE_TTL)

# ==================== محاكاة المتصفح والبحث الذكي ====================
class BrowserSimulator:
    @classmethod
    def get_headers(cls, url: str) -> Dict[str, str]:
        ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        if 'tiktok' in url.lower() or 'instagram' in url.lower():
            ua = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'
        return {
            'User-Agent': ua,
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://www.google.com/'
        }

class SmartLinkResolver:
    @classmethod
    async def resolve(cls, url: str) -> Dict[str, Any]:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.get(url, headers=BrowserSimulator.get_headers(url), ssl=False) as response:
                    html = await response.text()
                    video_urls = re.findall(r'https?://[^\s]+\.mp4(?:\?[^\s]*)?', html)
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.find('title').text.strip() if soup.find('title') else "Video"
                    return {'success': len(video_urls) > 0, 'video_urls': list(set(video_urls)), 'title': title}
        except:
            return {'success': False}

# ==================== نماذج البيانات (Models) ====================
class VideoQuality(BaseModel):
    quality: str
    url: str
    audio_url: Optional[str] = None
    filesize: Optional[int] = None
    extension: str
    has_audio: bool = True

class VideoInfoResponse(BaseModel):
    id: str
    title: str
    thumbnail: str
    duration: float
    platform: str
    qualities: List[VideoQuality]
    hls_info: Optional[Dict[str, Any]] = None
    dash_info: Optional[Dict[str, Any]] = None
    extracted_at: str

class ExtractRequest(BaseModel):
    url: HttpUrl
    format_type: Literal['video', 'mp3'] = 'video'
    force_refresh: bool = False

class ExtractResponse(BaseModel):
    success: bool
    data: Optional[VideoInfoResponse] = None
    error: Optional[str] = None
    from_cache: bool = False
    processing_time_ms: int = 0

# ==================== وظائف المعالجة ====================
def identify_platform(url: str) -> str:
    u = str(url).lower()
    if 'youtube' in u or 'youtu.be' in u: return 'YouTube'
    if 'facebook' in u or 'fb.watch' in u: return 'Facebook'
    if 'instagram' in u: return 'Instagram'
    if 'tiktok' in u: return 'TikTok'
    if 'twitter' in u or 'x.com' in u: return 'Twitter'
    return 'Generic'

def process_extracted_info(info: Dict[str, Any], url: str, format_type: str) -> Dict[str, Any]:
    all_formats = info.get('formats', [])
    qualities = []
    seen = set()
    
    # البحث عن أفضل صوت لدمجه إذا لزم الأمر
    best_audio = None
    audio_only = [f for f in all_formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
    if audio_only:
        best_audio = max(audio_only, key=lambda x: x.get('abr', 0) or 0).get('url')

    for f in all_formats:
        height = f.get('height')
        if height and f.get('vcodec') != 'none' and format_type == 'video':
            q_name = f"{height}p"
            if q_name not in seen:
                seen.add(q_name)
                qualities.append({
                    'quality': q_name,
                    'url': f.get('url'),
                    'audio_url': best_audio if f.get('acodec') == 'none' else None,
                    'filesize': f.get('filesize'),
                    'extension': f.get('ext', 'mp4'),
                    'has_audio': f.get('acodec') != 'none' or best_audio is not None
                })

    qualities.sort(key=lambda x: int(x['quality'].replace('p','')), reverse=True)

    # معالجة HLS/DASH
    hls_info = None
    dash_info = None
    for f in all_formats:
        if '.m3u8' in f.get('url', '') or f.get('protocol') == 'm3u8_native':
            hls_info = {'url': f.get('url'), 'protocol': 'm3u8'}
        if '.mpd' in f.get('url', '') or f.get('protocol') == 'http_dash_segments':
            dash_info = {'url': f.get('url'), 'protocol': 'dash'}

    return {
        'id': info.get('id', 'unknown'),
        'title': info.get('title', 'Video'),
        'thumbnail': info.get('thumbnail', ''),
        'duration': float(info.get('duration', 0) or 0),
        'platform': identify_platform(url),
        'qualities': qualities,
        'hls_info': hls_info,
        'dash_info': dash_info,
        'extracted_at': datetime.now().isoformat()
    }

async def extract_video_info_async(url: str, format_type: str):
    def fetch():
        opts = {
            'quiet': True, 'skip_download': True,
            'http_headers': BrowserSimulator.get_headers(url),
            'format': 'bestvideo+bestaudio/best' if format_type == 'video' else 'bestaudio/best'
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await run_in_threadpool(fetch)
        return process_extracted_info(info, url, format_type)
    except Exception as e:
        logger.error(f"yt-dlp failed, trying smart resolver: {e}")
        smart = await SmartLinkResolver.resolve(url)
        if smart['success']:
            return {
                'id': 'smart', 'title': smart['title'], 'thumbnail': '', 'duration': 0,
                'platform': identify_platform(url),
                'qualities': [{'quality': 'Auto', 'url': smart['video_urls'][0], 'extension': 'mp4', 'has_audio': True}],
                'extracted_at': datetime.now().isoformat()
            }
        raise e

# ==================== FastAPI App Definition ====================
app = FastAPI(title="CupGet API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/extract", response_model=ExtractResponse)
async def extract_video(req_body: ExtractRequest):
    start_time = time.time()
    url_str = str(req_body.url)
    u_hash = hashlib.md5(f"{url_str}_{req_body.format_type}".encode()).hexdigest()
    
    if not req_body.force_refresh and u_hash in response_cache:
        return ExtractResponse(success=True, data=response_cache[u_hash], from_cache=True, processing_time_ms=int((time.time()-start_time)*1000))

    try:
        data = await extract_video_info_async(url_str, req_body.format_type)
        res_data = VideoInfoResponse(**data)
        response_cache[u_hash] = res_data
        return ExtractResponse(success=True, data=res_data, processing_time_ms=int((time.time()-start_time)*1000))
    except Exception as e:
        return ExtractResponse(success=False, error=str(e), processing_time_ms=int((time.time()-start_time)*1000))

@app.get("/health")
async def health(): return {"status": "healthy"}

@app.get("/")
async def root(): return {"message": "CupGet API v3 is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
