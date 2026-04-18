
"""
Video Downloader API - Main Entry Point
Flask-based REST API for video download URL extraction
"""

import logging
import os
from datetime import datetime
from typing import Dict, Any

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from downloader_service import downloader_service

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure CORS for mobile app connectivity
CORS(app, resources={
    r"/api/*": {
        "origins": "*",  # Configure specific origins in production
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Request timeout configuration
app.config['TIMEOUT'] = 30


@app.before_request
def before_request():
    """Log incoming requests"""
    logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")


@app.after_request
def after_request(response):
    """Log response status"""
    logger.info(f"Response: {response.status_code} for {request.path}")
    return response


@app.errorhandler(404)
def not_found(error) -> Dict[str, Any]:
    """Handle 404 errors"""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'code': 404
    }), 404


@app.errorhandler(500)
def internal_error(error) -> Dict[str, Any]:
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'code': 500
    }), 500


@app.route('/health', methods=['GET'])
def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return jsonify({
        'success': True,
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })


@app.route('/api/extract', methods=['POST'])
def extract_video() -> Dict[str, Any]:
    """
    Extract video download URL
    
    Request body:
    {
        "url": "https://example.com/video",
        "quality": "best"  # optional: 'best', 'video_only', 'audio_only'
    }
    
    Response:
    {
        "success": true,
        "data": {
            "title": "...",
            "download_url": "...",
            "duration": 123,
            "thumbnail": "...",
            "quality": "best",
            "ext": "mp4",
            "filesize": 1234567,
            "platform": "tiktok"
        }
    }
    """
    try:
        # Validate request body
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json',
                'code': 400
            }), 400
        
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: url',
                'code': 400
            }), 400
        
        url = data['url']
        quality = data.get('quality', 'best')
        
        # Validate quality parameter
        if quality not in ['best', 'video_only', 'audio_only']:
            quality = 'best'
        
        # Extract video information
        result = downloader_service.extract_video_info(url, quality)
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except ValueError as e:
        logger.warning(f"Validation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 400
        }), 400
        
    except Exception as e:
        logger.error(f"Extraction error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to extract video. Please check the URL and try again.',
            'details': str(e) if os.getenv('DEBUG', 'false').lower() == 'true' else None,
            'code': 500
        }), 500


@app.route('/api/extract/audio', methods=['POST'])
def extract_audio() -> Dict[str, Any]:
    """
    Extract audio-only stream URL
    
    Request body:
    {
        "url": "https://example.com/video"
    }
    """
    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json',
                'code': 400
            }), 400
        
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: url',
                'code': 400
            }), 400
        
        result = downloader_service.extract_audio_only(data['url'])
        
        return jsonify({
            'success': True,
            'data': result
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'code': 400
        }), 400
        
    except Exception as e:
        logger.error(f"Audio extraction error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to extract audio',
            'code': 500
        }), 500


@app.route('/api/supported', methods=['GET'])
def get_supported_platforms() -> Dict[str, Any]:
    """Get list of supported platforms"""
    return jsonify({
        'success': True,
        'supported_platforms': ['Facebook', 'Instagram', 'TikTok', 'Twitter'],
        'note': 'YouTube URLs are explicitly blocked'
    })


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    logger.info(f"Starting Video Downloader API on port {port}, debug={debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
