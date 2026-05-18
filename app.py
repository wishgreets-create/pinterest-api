from flask import Flask, jsonify, request, Response, redirect
from flask_cors import CORS
import yt_dlp
import os
import urllib.parse

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
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({'success': False, 'error': 'No media found'})
            
            formats = info.get('formats', [])
            title = info.get('title', 'Pinterest Media')
            thumbnail = info.get('thumbnail', None)
            
            hd_url = None
            sd_url = None

            # First try: MP4 with audio (best case)
            mp4_audio = [
                f for f in formats
                if f.get('ext') == 'mp4'
                and f.get('vcodec','none') != 'none'
                and f.get('acodec','none') != 'none'
                and f.get('url')
                and 'm3u8' not in f.get('url','')
            ]
            mp4_audio.sort(key=lambda x: x.get('height',0) or 0, reverse=True)
            
            if mp4_audio:
                hd_url = mp4_audio[0]['url']
                if len(mp4_audio) > 1:
                    sd_url = mp4_audio[-1]['url']

            # Second try: any MP4 without HLS
            if not hd_url:
                mp4_any = [
                    f for f in formats
                    if f.get('ext') == 'mp4'
                    and f.get('vcodec','none') != 'none'
                    and f.get('url')
                    and 'm3u8' not in f.get('url','')
                ]
                mp4_any.sort(key=lambda x: x.get('height',0) or 0, reverse=True)
                if mp4_any:
                    hd_url = mp4_any[0]['url']
                    if len(mp4_any) > 1:
                        sd_url = mp4_any[-1]['url']

            # Third try: HLS stream (has audio in it)
            if not hd_url:
                hls = [
                    f for f in formats
                    if f.get('vcodec','none') != 'none'
                    and f.get('url')
                ]
                hls.sort(key=lambda x: x.get('height',0) or 0, reverse=True)
                if hls:
                    hd_url = hls[0]['url']
                    if len(hls) > 1:
                        sd_url = hls[-1]['url']

            if not hd_url:
                hd_url = info.get('url')

            if hd_url:
                # Proxy the video through our server to fix CORS
                base = request.host_url.rstrip('/')
                hd_proxied = f"{base}/proxy?url={urllib.parse.quote(hd_url, safe='')}"
                sd_proxied = f"{base}/proxy?url={urllib.parse.quote(sd_url, safe='')}" if sd_url else None
                
                return jsonify({
                    'success': True,
                    'type': 'video',
                    'title': title,
                    'thumbnail': thumbnail,
                    'hd': hd_proxied,
                    'sd': sd_proxied,
                    'url': hd_proxied,
                    'direct_hd': hd_url,
                    'is_hls': '.m3u8' in hd_url
                })
            else:
                return jsonify({'success': False, 'error': 'No video found'})
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/proxy')
def proxy():
    """Proxy video bytes to fix CORS and allow download"""
    video_url = request.args.get('url')
    if not video_url:
        return jsonify({'error': 'No URL'}), 400

    try:
        import urllib.request as urlreq
        
        req = urlreq.Request(
            video_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.pinterest.com/',
            }
        )
        
        response = urlreq.urlopen(req, timeout=30)
        content_type = response.headers.get('Content-Type', 'video/mp4')
        
        def generate():
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                yield chunk
        
        return Response(
            generate(),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': 'attachment; filename="pinterest_video.mp4"',
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
