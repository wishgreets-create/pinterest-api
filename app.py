from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'message': 'Pinterest Downloader API'
    })

@app.route('/download')
def download():
    url = request.args.get('url')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'No URL provided'
        })
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({
                    'success': False,
                    'error': 'No media found'
                })
            
            formats = info.get('formats', [])
            hd_url = None
            sd_url = None
            thumbnail = info.get('thumbnail', None)
            title = info.get('title', 'Pinterest Media')
            media_type = 'video'
            
            # Get best quality videos
            video_formats = [
                f for f in formats
                if f.get('vcodec') != 'none'
                and f.get('url')
                and '.mp4' in f.get('url', '')
            ]
            
            if not video_formats:
                video_formats = [
                    f for f in formats
                    if f.get('vcodec') != 'none'
                    and f.get('url')
                ]
            
            # Sort by quality
            video_formats.sort(
                key=lambda x: x.get('height', 0) or 0,
                reverse=True
            )
            
            if video_formats:
                hd_url = video_formats[0].get('url')
                if len(video_formats) > 1:
                    sd_url = video_formats[-1].get('url')
            
            # Fallback
            if not hd_url:
                hd_url = info.get('url')
            
            if not hd_url:
                # Try direct URL from formats
                for f in formats:
                    if f.get('url'):
                        hd_url = f['url']
                        break
            
            if hd_url:
                return jsonify({
                    'success': True,
                    'type': media_type,
                    'title': title,
                    'thumbnail': thumbnail,
                    'hd': hd_url,
                    'sd': sd_url if sd_url != hd_url else None,
                    'url': hd_url
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No downloadable video found'
                })
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
