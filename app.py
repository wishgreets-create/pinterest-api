from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yt_dlp
import os
import urllib.parse
import urllib.request

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'status': 'running'})

@app.route('/download')
def download():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            'format': 'best',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({'success': False, 'error': 'No media found'})
            
            title = info.get('title', 'Pinterest Media')
            thumbnail = info.get('thumbnail', None)
            formats = info.get('formats', [])
            
            # Collect all video URLs with quality info
            all_videos = []
            
            for f in formats:
                fu = f.get('url','')
                fv = f.get('vcodec','none')
                fh = f.get('height', 0) or 0
                fext = f.get('ext','')
                fa = f.get('acodec','none')
                
                if not fu or fv == 'none':
                    continue
                    
                all_videos.append({
                    'url': fu,
                    'height': fh,
                    'ext': fext,
                    'has_audio': fa != 'none',
                    'is_hls': 'm3u8' in fu or 'm3u8' in f.get('protocol','')
                })
            
            # Sort: prefer audio+video, highest quality first
            all_videos.sort(
                key=lambda x: (
                    x['has_audio'],
                    not x['is_hls'],
                    x['height']
                ),
                reverse=True
            )
            
            if not all_videos:
                direct = info.get('url')
                if direct:
                    all_videos = [{'url': direct, 'height': 0, 'has_audio': True, 'is_hls': 'm3u8' in direct}]
            
            if not all_videos:
                return jsonify({'success': False, 'error': 'No video found'})
            
            best = all_videos[0]
            second = all_videos[-1] if len(all_videos) > 1 else None
            
            base = request.host_url.rstrip('/')
            
            return jsonify({
                'success': True,
                'type': 'video',
                'title': title,
                'thumbnail': thumbnail,
                'hd': best['url'],
                'sd': second['url'] if second and second['url'] != best['url'] else None,
                'url': best['url'],
                'is_hls': best['is_hls'],
                'has_audio': best['has_audio'],
                'player_url': f"{base}/player?url={urllib.parse.quote(url, safe='')}"
            })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/player')
def player():
    """HTML5 video player page for the Pinterest video"""
    pin_url = request.args.get('url')
    if not pin_url:
        return "No URL provided", 400
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'best',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(pin_url, download=False)
            
            formats = info.get('formats', [])
            title = info.get('title', 'Pinterest Video')
            
            # Find best MP4 URL
            video_url = None
            for f in reversed(formats):
                fu = f.get('url','')
                fv = f.get('vcodec','none')
                if fu and fv != 'none':
                    video_url = fu
                    break
            
            if not video_url:
                video_url = info.get('url','')
            
            html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #000; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; font-family: sans-serif; }}
video {{ max-width: 100%; max-height: 80vh; }}
h3 {{ color: #fff; margin: 16px; text-align: center; font-size: 14px; }}
.btn {{ background: #e60023; color: #fff; border: none; padding: 12px 28px; border-radius: 8px; font-size: 16px; cursor: pointer; margin: 12px; text-decoration: none; display: inline-block; }}
p {{ color: #aaa; font-size: 12px; margin: 8px; text-align: center; }}
</style>
</head>
<body>
<h3>{title}</h3>
<video controls autoplay playsinline>
  <source src="{video_url}" type="video/mp4">
  Your browser does not support video.
</video>
<p>On mobile: tap and hold the video → Save Video</p>
<a href="{video_url}" download="pinterest_video.mp4" class="btn">⬇ Download MP4</a>
</body>
</html>"""
            
            return html
            
    except Exception as e:
        return f"Error: {str(e)}", 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
