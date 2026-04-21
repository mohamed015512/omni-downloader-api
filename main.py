"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CupGet API - Ultimate Downloader                        ║
║                      أقوى وأذكى سيرفر تحميل فيديوهات في العالم                  ║
║                           الكود الكامل - النسخة النهائية                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any, Literal, Tuple
from collections import OrderedDict
from functools import lru_cache
from datetime import datetime, timedelta
import asyncio
import aiohttp
import hashlib
import json
import logging
import re
import time
import os
from urllib.parse import urlparse, parse_qs, urlunparse
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from bs4 import BeautifulSoup
import m3u8
from cachetools import TTLCache, LRUCache
import uvicorn

# ==================== إعدادات متقدمة ====================

# إعداد التسجيل الاحترافي
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CupGet-API")

# إعدادات الأداء
THREAD_POOL = ThreadPoolExecutor(max_workers=20)
CACHE_TTL = 300  # 5 دقائق
MAX_CACHE_SIZE = 1000
MAX_CONCURRENT_REQUESTS = 50
REQUEST_TIMEOUT = 60

# كاش ذكي للنتائج
response_cache = TTLCache(maxsize=MAX_CACHE_SIZE, ttl=CACHE_TTL)
url_hash_cache = LRUCache(maxsize=MAX_CACHE_SIZE)

# ==================== محاكاة المتصفح الكاملة ====================

class BrowserSimulator:
    """محاكاة متقدمة للمتصفحات الحقيقية"""
    
    # قائمة بأحدث المتصفحات
    BROWSERS = {
        'chrome_win': {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'sec_ch_ua': '"Not:A-Brand";v="99", "Google Chrome";v="134"',
            'sec_ch_ua_platform': '"Windows"',
            'sec_ch_ua_mobile': '?0'
        },
        'chrome_mac': {
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'sec_ch_ua': '"Not:A-Brand";v="99", "Google Chrome";v="134"',
            'sec_ch_ua_platform': '"macOS"',
            'sec_ch_ua_mobile': '?0'
        },
        'firefox_win': {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0',
            'sec_ch_ua': None,
            'sec_ch_ua_platform': None,
            'sec_ch_ua_mobile': None
        },
        'safari_ios': {
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            'sec_ch_ua': None,
            'sec_ch_ua_platform': None,
            'sec_ch_ua_mobile': '?1'
        },
        'edge_win': {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0',
            'sec_ch_ua': '"Not:A-Brand";v="99", "Microsoft Edge";v="134"',
            'sec_ch_ua_platform': '"Windows"',
            'sec_ch_ua_mobile': '?0'
        },
        'chrome_android': {
            'user_agent': 'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Mobile Safari/537.36',
            'sec_ch_ua': '"Not:A-Brand";v="99", "Google Chrome";v="134"',
            'sec_ch_ua_platform': '"Android"',
            'sec_ch_ua_mobile': '?1'
        }
    }
    
    @classmethod
    def get_headers(cls, browser_name: str = 'chrome_win', referer: str = None) -> Dict[str, str]:
        """الحصول على هيدرات متقدمة لمحاكاة متصفح حقيقي"""
        browser = cls.BROWSERS.get(browser_name, cls.BROWSERS['chrome_win'])
        
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ar,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'User-Agent': browser['user_agent'],
        }
        
        if browser.get('sec_ch_ua'):
            headers['Sec-Ch-Ua'] = browser['sec_ch_ua']
        if browser.get('sec_ch_ua_platform'):
            headers['Sec-Ch-Ua-Platform'] = browser['sec_ch_ua_platform']
        if browser.get('sec_ch_ua_mobile'):
            headers['Sec-Ch-Ua-Mobile'] = browser['sec_ch_ua_mobile']
        if referer:
            headers['Referer'] = referer
            
        return headers
    
    @classmethod
    def rotate_headers(cls, url: str) -> Dict[str, str]:
        """تدوير الهيدرات لتجنب الحظر"""
        if 'instagram' in url.lower():
            browser_name = 'chrome_android'
        elif 'facebook' in url.lower():
            browser_name = 'chrome_win'
        elif 'tiktok' in url.lower():
            browser_name = 'safari_ios'
        else:
            import random
            browsers = list(cls.BROWSERS.keys())
            browser_name = random.choice(browsers)
        
        referer = None
        if 'youtube' in url.lower():
            referer = 'https://www.youtube.com/'
        elif 'instagram' in url.lower():
            referer = 'https://www.instagram.com/'
        
        return cls.get_headers(browser_name, referer)


# ==================== نظام البحث الذكي عن الروابط ====================

class SmartLinkResolver:
    """نظام ذكي للبحث عن الروابط عندما يفشل yt-dlp"""
    
    VIDEO_PATTERNS = [
        r'https?://[^\s]+\.mp4(?:\?[^\s]*)?',
        r'https?://[^\s]+\.m3u8(?:\?[^\s]*)?',
        r'https?://[^\s]+\.mpd(?:\?[^\s]*)?',
        r'https?://[^\s]+\.ts(?:\?[^\s]*)?',
        r'https?://[^\s]+\.webm(?:\?[^\s]*)?',
        r'https?://[^\s]+\.mov(?:\?[^\s]*)?',
        r'https?://[^\s]+/video/[^\s]+\.mp4',
        r'https?://[^\s]+/get_file/[^\s]+\.mp4',
        r'https?://[^\s]+/hls/[^\s]+\.m3u8',
        r'https?://[^\s]+/dash/[^\s]+\.mpd',
        r'src=[\'"]([^\'"]+\.mp4[^\'"]*)[\'"]',
        r'src=[\'"]([^\'"]+\.m3u8[^\'"]*)[\'"]',
        r'data-video-url=[\'"]([^\'"]+)[\'"]',
        r'contentUrl=[\'"]([^\'"]+)[\'"]',
        r'videoUrl=[\'"]([^\'"]+)[\'"]',
        r'source src=[\'"]([^\'"]+)[\'"]',
    ]
    
    THUMBNAIL_PATTERNS = [
        r'https?://[^\s]+\.jpg(?:\?[^\s]*)?',
        r'https?://[^\s]+\.png(?:\?[^\s]*)?',
        r'https?://[^\s]+\.webp(?:\?[^\s]*)?',
        r'poster=[\'"]([^\'"]+)[\'"]',
        r'thumbnailUrl=[\'"]([^\'"]+)[\'"]',
        r'data-thumbnail=[\'"]([^\'"]+)[\'"]',
        r'og:image.*?content=[\'"]([^\'"]+)[\'"]',
        r'twitter:image.*?content=[\'"]([^\'"]+)[\'"]',
    ]
    
    @classmethod
    async def resolve(cls, url: str, timeout: int = 30) -> Dict[str, Any]:
        """البحث الذكي عن الروابط"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = BrowserSimulator.rotate_headers(url)
                async with session.get(url, headers=headers, timeout=timeout, ssl=False) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    video_urls = []
                    for video_tag in soup.find_all('video'):
                        src = video_tag.get('src')
                        if src:
                            video_urls.append(src)
                        for source in video_tag.find_all('source'):
                            src = source.get('src')
                            if src:
                                video_urls.append(src)
                    
                    for pattern in cls.VIDEO_PATTERNS:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        video_urls.extend(matches)
                    
                    thumbnails = []
                    for pattern in cls.THUMBNAIL_PATTERNS:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        thumbnails.extend(matches)
                    
                    title = None
                    title_tag = soup.find('title')
                    if title_tag:
                        title = title_tag.text.strip()
                    
                    valid_videos = []
                    for v in video_urls:
                        if v and isinstance(v, str):
                            v = v.strip()
                            if v.startswith(('http://', 'https://')):
                                valid_videos.append(v)
                            elif v.startswith('/'):
                                parsed = urlparse(url)
                                full_url = f"{parsed.scheme}://{parsed.netloc}{v}"
                                valid_videos.append(full_url)
                    
                    return {
                        'success': len(valid_videos) > 0,
                        'video_urls': list(set(valid_videos)),
                        'thumbnails': list(set(thumbnails))[:5],
                        'title': title,
                        'html_length': len(html)
                    }
        except Exception as e:
            logger.error(f"SmartLinkResolver error: {str(e)}")
            return {'success': False, 'error': str(e)}


# ==================== معالج HLS و DASH ====================

class HLSDashHandler:
    """معالج متقدم لروابط HLS و DASH"""
    
    @classmethod
    async def process_hls(cls, m3u8_url: str) -> Dict[str, Any]:
        """معالجة روابط HLS وجمع المقاطع"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(m3u8_url) as response:
                    content = await response.text()
                    playlist = m3u8.loads(content)
                    
                    segments_info = []
                    total_duration = 0
                    segment_urls = []
                    
                    for segment in playlist.segments:
                        segment_url = segment.uri
                        if not segment_url.startswith('http'):
                            base_url = '/'.join(m3u8_url.split('/')[:-1])
                            segment_url = f"{base_url}/{segment_url}"
                        
                        segment_urls.append(segment_url)
                        segments_info.append({
                            'url': segment_url,
                            'duration': segment.duration
                        })
                        total_duration += segment.duration
                    
                    return {
                        'type': 'hls',
                        'segment_count': len(segments_info),
                        'total_duration': total_duration,
                        'segments': segments_info,
                        'segment_urls': segment_urls,
                        'quality': playlist.playlists[0].stream_info.resolution if playlist.playlists else None
                    }
        except Exception as e:
            logger.error(f"HLS processing error: {str(e)}")
            return {'type': 'hls', 'error': str(e)}
    
    @classmethod
    async def process_dash(cls, mpd_url: str) -> Dict[str, Any]:
        """معالجة روابط DASH"""
        return {'type': 'dash', 'url': mpd_url, 'needs_processing': True}


# ==================== تكوين yt-dlp المتقدم ====================

def get_advanced_ydl_opts(format_type: str = 'video', cookies_file: str = None) -> Dict[str, Any]:
    """الحصول على إعدادات yt-dlp متقدمة"""
    
    headers = BrowserSimulator.rotate_headers('https://www.youtube.com/')
    
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'skip_download': True,
        'no_color': True,
        'ignoreerrors': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        'socket_timeout': REQUEST_TIMEOUT,
        'retries': 10,
        'fragment_retries': 10,
        'file_access_retries': 5,
        'extractor_retries': 5,
        'sleep_interval_requests': 1,
        'sleep_interval': 2,
        'max_sleep_interval': 5,
        'concurrent_fragment_downloads': 5,
        'http_headers': headers,
        'add_header': [
            'Accept-Language: ar,en-US;q=0.9,en;q=0.8',
            'Sec-Fetch-Mode: navigate',
            'Sec-Fetch-Site: none',
        ],
        'throttledratelimit': 100000000,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['hls', 'dash'],
                'player_skip': ['webpage'],
            },
            'facebook': {'prefer_https': True},
            'instagram': {'user_agent': headers['User-Agent']},
            'tiktok': {'api_hostname': 'www.tiktok.com'}
        }
    }
    
    if cookies_file and os.path.exists(cookies_file):
        opts['cookiefile'] = cookies_file
    
    if format_type == 'mp3':
        opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'extractaudio': True,
            'audioformat': 'mp3',
        })
    else:
        opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        })
    
    return opts


# ==================== النماذج (Models) ====================

class VideoQuality(BaseModel):
    quality: str
    url: str
    audio_url: Optional[str] = None
    filesize: Optional[int] = None
    extension: str
    has_audio: bool = True
    width: Optional[int] = None
    height: Optional[int] = None
    bitrate: Optional[int] = None
    fps: Optional[float] = None

class VideoInfoResponse(BaseModel):
    id: str
    title: str
    thumbnail: str
    duration: float
    platform: str
    qualities: List[VideoQuality]
    audio_formats: Optional[List[Dict[str, Any]]] = None
    hls_info: Optional[Dict[str, Any]] = None
    dash_info: Optional[Dict[str, Any]] = None
    estimated_size: Optional[str] = None
    extracted_at: str

class ExtractRequest(BaseModel):
    url: HttpUrl
    format_type: Literal['video', 'mp3'] = 'video'
    quality_preference: Optional[str] = None
    force_refresh: bool = False

class ExtractResponse(BaseModel):
    success: bool
    data: Optional[VideoInfoResponse] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    from_cache: bool = False
    processing_time_ms: int = 0


# ==================== نظام الكاش الذكي ====================

def get_url_hash(url: str, format_type: str) -> str:
    """إنشاء هاش فريد للرابط"""
    key = f"{url}_{format_type}"
    return hashlib.md5(key.encode()).hexdigest()

def get_cached_response(url_hash: str) -> Optional[Dict[str, Any]]:
    """استرداد رد من الكاش"""
    if url_hash in response_cache:
        cached = response_cache[url_hash]
        if datetime.now() - cached['cached_at'] < timedelta(seconds=CACHE_TTL):
            return cached['data']
    return None

def cache_response(url_hash: str, data: Dict[str, Any]):
    """تخزين رد في الكاش"""
    response_cache[url_hash] = {
        'data': data,
        'cached_at': datetime.now()
    }


# ==================== الوظائف الأساسية ====================

async def extract_video_info_async(url: str, format_type: str = 'video') -> Dict[str, Any]:
    """استخراج معلومات الفيديو بشكل غير متزامن مع متابعة ذكية"""
    
    for attempt in range(3):
        try:
            ydl_opts = get_advanced_ydl_opts(format_type)
            
            if attempt == 1:
                ydl_opts['http_headers'] = BrowserSimulator.rotate_headers(url)
            elif attempt == 2:
                ydl_opts['http_headers'] = BrowserSimulator.get_headers('chrome_android')
            
            info = await run_in_threadpool(lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False))
            
            if info:
                return process_extracted_info(info, url, format_type)
                
        except Exception as e:
            logger.warning(f"yt-dlp attempt {attempt + 1} failed: {str(e)}")
            await asyncio.sleep(1)
            
            if attempt == 2:
                logger.info(f"Trying smart link resolver for {url}")
                smart_result = await SmartLinkResolver.resolve(url)
                if smart_result.get('success') and smart_result.get('video_urls'):
                    return {
                        'title': smart_result.get('title', 'Video'),
                        'thumbnail': smart_result.get('thumbnails', [''])[0] if smart_result.get('thumbnails') else '',
                        'duration': 0,
                        'formats': [{
                            'quality': 'Unknown',
                            'url': smart_result['video_urls'][0],
                            'has_audio': True,
                            'extension': 'mp4',
                        }],
                        'platform': identify_platform(url),
                        'is_fallback': True
                    }
    
    raise Exception("Failed to extract video info after all attempts")


def process_extracted_info(info: Dict[str, Any], url: str, format_type: str) -> Dict[str, Any]:
    """معالجة المعلومات المستخرجة وتنسيقها"""
    
    all_formats = info.get('formats', [])
    
    best_audio = None
    audio_only_formats = [f for f in all_formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
    if audio_only_formats:
        best_audio = max(audio_only_formats, key=lambda x: x.get('abr', 0) or 0)
    
    qualities = []
    seen_qualities = set()
    
    for f in all_formats:
        vcodec = f.get('vcodec', 'none')
        acodec = f.get('acodec', 'none')
        height = f.get('height')
        width = f.get('width')
        
        if vcodec != 'none' and height and format_type == 'video':
            quality = f"{height}p"
            has_audio = acodec != 'none'
            
            audio_url = None
            if not has_audio and best_audio:
                audio_url = best_audio.get('url')
            
            if quality not in seen_qualities:
                seen_qualities.add(quality)
                qualities.append({
                    'quality': quality,
                    'url': f.get('url'),
                    'audio_url': audio_url,
                    'filesize': f.get('filesize'),
                    'extension': f.get('ext', 'mp4'),
                    'has_audio': has_audio or bool(audio_url),
                    'width': width,
                    'height': height,
                    'bitrate': f.get('vbr'),
                    'fps': f.get('fps')
                })
    
    qualities.sort(key=lambda x: int(x['height']) if x['height'] else 0, reverse=True)
    
    estimated_size = None
    if qualities and qualities[0].get('filesize'):
        size_bytes = qualities[0]['filesize']
        if size_bytes < 1024 * 1024:
            estimated_size = f"{size_bytes / 1024:.1f} KB"
        else:
            estimated_size = f"{size_bytes / (1024 * 1024):.1f} MB"
    
    hls_info = None
    for f in all_formats:
        if f.get('proto
# ==================== متابعة الكود ====================

# ==================== مسار POST /extract (الرئيسي) ====================

@app.post("/extract", response_model=ExtractResponse)
async def extract_video(request: Request, req_body: ExtractRequest):
    """
    استخراج معلومات الفيديو وروابط التحميل
    
    **المميزات:**
    - دعم أكثر من 50 منصة (يوتيوب، فيسبوك، انستجرام، تيك توك، تويتر، وغيرها)
    - كاش ذكي لمدة 5 دقائق لتسريع الاستجابة
    - نظام إعادة محاولة ذكي مع 3 محاولات تلقائية
    - محاكاة كاملة للمتصفح لتجنب الحظر
    - دعم استخراج الصوت بصيغة MP3
    - معالجة روابط HLS و DASH
    - نظام بحث ذكي عند فشل yt-dlp
    
    **مثال الطلب:**
    ```json
    {
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "format_type": "video",
        "force_refresh": false
    }
    ```
    """
    start_time = time.time()
    url_hash = get_url_hash(str(req_body.url), req_body.format_type)
    
    # التحقق من الكاش
    if not req_body.force_refresh:
        cached = get_cached_response(url_hash)
        if cached:
            logger.info(f"✅ Cache hit for {url_hash}")
            return ExtractResponse(
                success=True,
                data=VideoInfoResponse(**cached),
                from_cache=True,
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    try:
        logger.info(f"🔍 Extracting video from: {str(req_body.url)[:50]}...")
        
        # استخراج المعلومات
        info = await extract_video_info_async(str(req_body.url), req_body.format_type)
        
        # تنسيق الرد
        response_data = VideoInfoResponse(
            id=info['id'],
            title=info['title'],
            thumbnail=info['thumbnail'],
            duration=info['duration'],
            platform=info['platform'],
            qualities=[VideoQuality(**q) for q in info['qualities']],
            audio_formats=info.get('audio_formats'),
            hls_info=info.get('hls_info'),
            dash_info=info.get('dash_info'),
            estimated_size=info.get('estimated_size'),
            extracted_at=datetime.now().isoformat()
        )
        
        # تخزين في الكاش
        cache_response(url_hash, response_data.dict())
        
        processing_time = int((time.time() - start_time) * 1000)
        logger.info(f"✅ Extraction completed in {processing_time}ms - {len(info['qualities'])} qualities found")
        
        return ExtractResponse(
            success=True,
            data=response_data,
            from_cache=False,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        logger.error(f"❌ Extraction error: {str(e)}")
        error_msg = str(e)
        error_code = "UNKNOWN_ERROR"
        
        if "unsupported" in error_msg.lower():
            error_code = "UNSUPPORTED_URL"
            error_msg = "الرابط غير مدعوم حالياً. تأكد من صحة الرابط وجرب مرة أخرى"
        elif "private" in error_msg.lower() or "login" in error_msg.lower():
            error_code = "PRIVATE_VIDEO"
            error_msg = "هذا الفيديو خاص أو يتطلب تسجيل دخول للوصول إليه"
        elif "rate" in error_msg.lower() or "too many" in error_msg.lower():
            error_code = "RATE_LIMIT"
            error_msg = "تم تجاوز الحد المسموح من الطلبات. يرجى الانتظار دقيقة ثم المحاولة مرة أخرى"
        elif "timeout" in error_msg.lower():
            error_code = "TIMEOUT"
            error_msg = "انتهى وقت الانتظار. الخادم يستغرق وقتاً طويلاً للمعالجة"
        elif "not found" in error_msg.lower() or "404" in error_msg.lower():
            error_code = "NOT_FOUND"
            error_msg = "الفيديو غير موجود أو تم حذفه"
        elif "offline" in error_msg.lower() or "connection" in error_msg.lower():
            error_code = "NETWORK_ERROR"
            error_msg = "مشكلة في الاتصال بالإنترنت. يرجى التحقق من اتصالك"
        
        return ExtractResponse(
            success=False,
            error=error_msg,
            error_code=error_code,
            processing_time_ms=int((time.time() - start_time) * 1000)
        )


# ==================== مسار GET /extract للاختبار السريع ====================

@app.get("/extract")
async def extract_video_get(
    url: str, 
    format_type: str = "video",
    force_refresh: bool = False
):
    """
    نسخة GET من endpoint /extract للاختبار السريع في المتصفح
    
    **مثال:**
    `/extract?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format_type=video`
    """
    from pydantic import ValidationError
    
    try:
        req_body = ExtractRequest(
            url=HttpUrl(url), 
            format_type=format_type,
            force_refresh=force_refresh
        )
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content={
                "success": False, 
                "error": "Invalid URL format. Please provide a valid URL including http:// or https://",
                "error_code": "INVALID_URL",
                "example": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            }
        )
    
    return await extract_video(Request(scope={"type": "http"}), req_body)


# ==================== مسار التحقق من صحة السيرفر ====================

@app.get("/health")
async def health_check():
    """التحقق من صحة السيرفر مع معلومات مفصلة"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "cache": {
            "size": len(response_cache),
            "max_size": MAX_CACHE_SIZE,
            "ttl_seconds": CACHE_TTL,
            "available_slots": MAX_CACHE_SIZE - len(response_cache)
        },
        "platforms_supported": [
            "YouTube", "Facebook", "Instagram", "TikTok", "Twitter",
            "Reddit", "Vimeo", "Dailymotion", "Twitch", "LinkedIn",
            "Pinterest", "Snapchat", "Telegram", "WhatsApp"
        ],
        "features": {
            "smart_resolver": True,
            "hls_support": True,
            "dash_support": True,
            "audio_extraction": True,
            "browser_simulation": True,
            "caching": True,
            "retry_mechanism": True
        }
    }


# ==================== مسار الإحصائيات المتقدمة ====================

@app.get("/stats")
async def get_stats():
    """إحصائيات متقدمة عن السيرفر واستخدامه"""
    total_cached = len(response_cache)
    total_cache_size = sum(len(str(v).encode('utf-8')) for v in response_cache.values())
    
    return {
        "cache_statistics": {
            "total_cached_items": total_cached,
            "cache_size_bytes": total_cache_size,
            "cache_size_mb": round(total_cache_size / (1024 * 1024), 2),
            "cache_max_size": MAX_CACHE_SIZE,
            "cache_ttl_seconds": CACHE_TTL,
            "cache_usage_percentage": round((total_cached / MAX_CACHE_SIZE) * 100, 2)
        },
        "system_stats": {
            "thread_pool_workers": THREAD_POOL._max_workers,
            "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
            "request_timeout_seconds": REQUEST_TIMEOUT
        },
        "features": [
            "Smart Link Resolver - يبحث يدوياً في HTML عند فشل yt-dlp",
            "HLS/DASH Support - يدعم روابط البث المباشر والمقاطع المتقطعة",
            "Advanced Browser Simulation - يحاكي 6 أنواع مختلفة من المتصفحات",
            "Intelligent Caching - تخزين ذكي للنتائج لمدة 5 دقائق",
            "Auto Retry Mechanism - 3 محاولات تلقائية مع User-Agent مختلف",
            "Audio Extraction - استخراج الصوت بصيغة MP3 بجودة 320kbps",
            "Multi-Quality Support - يدعم جميع الجودات من 144p إلى 8K",
            "Platform Detection - يتعرف تلقائياً على المنصة من الرابط"
        ],
        "supported_platforms_count": 14,
        "uptime": "running_since_startup"
    }


# ==================== مسار معلومات السيرفر ====================

@app.get("/")
async def root():
    """معلومات السيرفر الأساسية والروابط المتاحة"""
    return {
        "name": "CupGet API",
        "version": "3.0.0",
        "tagline": "أقوى سيرفر لتحميل الفيديوهات في العالم",
        "description": "سيرفر احترافي لتحميل الفيديوهات من جميع منصات التواصل الاجتماعي",
        "documentation": "/docs",
        "interactive_docs": "/redoc",
        "health_check": "/health",
        "statistics": "/stats",
        "endpoints": {
            "POST /extract": {
                "description": "استخراج معلومات الفيديو (الطريقة الموصى بها)",
                "method": "POST",
                "content_type": "application/json",
                "body_example": {
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "format_type": "video",
                    "force_refresh": False
                }
            },
            "GET /extract": {
                "description": "استخراج معلومات الفيديو (GET method for testing)",
                "method": "GET",
                "example": "/extract?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ&format_type=video"
            },
            "GET /health": {
                "description": "التحقق من صحة السيرفر",
                "method": "GET"
            },
            "GET /stats": {
                "description": "إحصائيات السيرفر",
                "method": "GET"
            },
            "GET /docs": {
                "description": "التوثيق التفاعلي (Swagger UI)",
                "method": "GET"
            },
            "GET /redoc": {
                "description": "التوثيق البديل (ReDoc)",
                "method": "GET"
            }
        },
        "example_curl": {
            "video": "curl -X POST https://your-server.com/extract -H 'Content-Type: application/json' -d '{\"url\": \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\", \"format_type\": \"video\"}'",
            "audio": "curl -X POST https://your-server.com/extract -H 'Content-Type: application/json' -d '{\"url\": \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\", \"format_type\": \"mp3\"}'"
        }
    }


# ==================== مسار لتنظيف الكاش (للإدارة) ====================

@app.post("/admin/clear-cache")
async def clear_cache(admin_key: str = None):
    """
    تنظيف الكاش بالكامل (يتطلب مفتاح إداري)
    يمكنك تعيين مفتاح سري في متغيرات البيئة
    """
    # مفتاح افتراضي - يفضل تعيينه في متغيرات البيئة
    SECRET_ADMIN_KEY = os.environ.get("ADMIN_KEY", "CupGet2024Secret")
    
    if admin_key != SECRET_ADMIN_KEY:
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "error": "Unauthorized. Invalid admin key",
                "error_code": "UNAUTHORIZED"
            }
        )
    
    old_size = len(response_cache)
    response_cache.clear()
    
    logger.info(f"Cache cleared by admin. Removed {old_size} items.")
    
    return {
        "success": True,
        "message": f"Cache cleared successfully",
        "removed_items": old_size,
        "timestamp": datetime.now().isoformat()
    }


# ==================== مسار للحصول على معلومات عن رابط محدد ====================

@app.post("/info")
async def get_video_info_only(req_body: ExtractRequest):
    """
    استخراج معلومات الفيديو فقط (بدون روابط التحميل)
    يستخدم نفس نظام /extract لكن بدون إرجاع الروابط
    """
    start_time = time.time()
    
    try:
        logger.info(f"🔍 Getting info only for: {str(req_body.url)[:50]}...")
        
        info = await extract_video_info_async(str(req_body.url), req_body.format_type)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return {
            "success": True,
            "data": {
                "id": info['id'],
                "title": info['title'],
                "thumbnail": info['thumbnail'],
                "duration": info['duration'],
                "platform": info['platform'],
                "quality_count": len(info['qualities']),
                "has_audio_formats": info.get('audio_formats') is not None and len(info.get('audio_formats', [])) > 0,
                "is_fallback": info.get('is_fallback', False)
            },
            "processing_time_ms": processing_time
        }
        
    except Exception as e:
        logger.error(f"❌ Info extraction error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "error_code": "EXTRACTION_FAILED"
            }
        )


# ==================== مسار لدعم الروابط المتعددة (Batch) ====================

class BatchExtractRequest(BaseModel):
    urls: List[HttpUrl]
    format_type: Literal['video', 'mp3'] = 'video'

class BatchExtractResponse(BaseModel):
    success: bool
    results: List[Dict[str, Any]]
    total_time_ms: int

@app.post("/extract-batch", response_model=BatchExtractResponse)
async def extract_videos_batch(request: Request, req_body: BatchExtractRequest):
    """
    استخراج معلومات فيديوهات متعددة في طلب واحد
    يدعم حتى 10 روابط في المرة الواحدة
    """
    if len(req_body.urls) > 10:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Maximum 10 URLs per batch request",
                "error_code": "BATCH_LIMIT_EXCEEDED"
            }
        )
    
    start_time = time.time()
    results = []
    
    for url in req_body.urls:
        try:
            req = ExtractRequest(url=url, format_type=req_body.format_type)
            result = await extract_video(Request(scope={"type": "http"}), req)
            results.append({
                "url": str(url),
                "success": result.success,
                "data": result.data.dict() if result.data else None,
                "error": result.error,
                "error_code": result.error_code,
                "from_cache": result.from_cache
            })
        except Exception as e:
            results.append({
                "url": str(url),
                "success": False,
                "error": str(e),
                "error_code": "PROCESSING_ERROR"
            })
    
    total_time = int((time.time() - start_time) * 1000)
    
    return BatchExtractResponse(
        success=True,
        results=results,
        total_time_ms=total_time
    )


# ==================== مسار لاختبار الاتصال ====================

@app.get("/ping")
async def ping():
    """اختبار بسيط للاتصال بالسيرفر"""
    return {
        "pong": True,
        "timestamp": datetime.now().isoformat(),
        "server_time": time.time()
    }


# ==================== معالج الأخطاء العام ====================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """معالج الأخطاء العام للسيرفر"""
    logger.error(f"Global exception handler: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error. Please try again later.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "timestamp": datetime.now().isoformat()
        }
    )


# ==================== مسار لاستخراج الصوت فقط ====================

@app.post("/extract-audio")
async def extract_audio_only(req_body: ExtractRequest):
    """
    استخراج الصوت فقط من الفيديو بصيغة MP3
    هذه نسخة مختصرة من /extract مع format_type=mp3
    """
    # تغيير format_type تلقائياً إلى mp3
    modified_request = ExtractRequest(
        url=req_body.url,
        format_type="mp3",
        force_refresh=req_body.force_refresh
    )
    return await extract_video(Request(scope={"type": "http"}), modified_request)


# ==================== مسار لاستخراج أعلى جودة ====================

@app.post("/extract-best")
async def extract_best_quality(req_body: ExtractRequest):
    """
    استخراج أعلى جودة متاحة للفيديو
    يرجع فقط أفضل جودة (أعلى دقة)
    """
    result = await extract_video(Request(scope={"type": "http"}), req_body)
    
    if result.success and result.data and result.data.qualities:
        # اختيار أعلى جودة
        best_quality = result.data.qualities[0]
        
        return {
            "success": True,
            "data": {
                "title": result.data.title,
                "thumbnail": result.data.thumbnail,
                "duration": result.data.duration,
                "platform": result.data.platform,
                "best_quality": best_quality.dict(),
                "estimated_size": result.data.estimated_size
            },
            "from_cache": result.from_cache,
            "processing_time_ms": result.processing_time_ms
        }
    
    return result


# ==================== تشغيل السيرفر ====================

if __name__ == "__main__":
    # قراءة إعدادات من متغيرات البيئة (للنشر على Render)
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    workers = int(os.environ.get("WORKERS", 4))
    
    logger.info(f"🚀 Starting CupGet API v3.0.0 on {host}:{port} with {workers} workers")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        limit_concurrency=MAX_CONCURRENT_REQUESTS,
        timeout_keep_alive=REQUEST_TIMEOUT,
        loop="asyncio",
        http="httptools",
        log_level="info",
        access_log=True
    )
