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
            # Force MP4 with audio — no HLS streams
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({
                    'success': False,
                    'error': 'No media found'
                })
            
            formats = info.get('formats', [])
            title = info.get('title', 'Pinterest Media')
            thumbnail = info.get('thumbnail', None)
            
            hd_url = None
            sd_url = None

            # Filter only MP4 formats with both video and audio
            mp4_av = [
                f for f in formats
                if f.get('ext') == 'mp4'
                and f.get('vcodec', 'none') != 'none'
                and f.get('acodec', 'none') != 'none'
                and f.get('url')
                and 'm3u8' not in f.get('url', '')
                and 'm3u8' not in f.get('protocol', '')
            ]

            # Sort by height (quality)
            mp4_av.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)

            if mp4_av:
                hd_url = mp4_av[0].get('url')
                if len(mp4_av) > 1:
                    sd_url = mp4_av[-1].get('url')

            # If no combined format, try video only MP4 (Pinterest usually has audio in it)
            if not hd_url:
                mp4_video = [
                    f for f in formats
                    if f.get('ext') == 'mp4'
                    and f.get('vcodec', 'none') != 'none'
                    and f.get('url')
                    and 'm3u8' not in f.get('url', '')
                    and 'm3u8' not in f.get('protocol', '')
                ]
                mp4_video.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
                if mp4_video:
                    hd_url = mp4_video[0].get('url')
                    if len(mp4_video) > 1:
                        sd_url = mp4_video[-1].get('url')

            # Last resort — any non-HLS URL
            if not hd_url:
                for f in reversed(formats):
                    fu = f.get('url', '')
                    fp = f.get('protocol', '')
                    if fu and 'm3u8' not in fu and 'm3u8' not in fp and f.get('vcodec','none') != 'none':
                        hd_url = fu
                        break

            # Absolute fallback
            if not hd_url:
                hd_url = info.get('url')

            if hd_url:
                return jsonify({
                    'success': True,
                    'type': 'video',
                    'title': title,
                    'thumbnail': thumbnail,
                    'hd': hd_url,
                    'sd': sd_url if sd_url and sd_url != hd_url else None,
                    'url': hd_url
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'No MP4 video found'
                })
                
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
