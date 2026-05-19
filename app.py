from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yt_dlp
import os
import subprocess
import tempfile
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
            'socket_timeout': 30,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({'success': False, 'error': 'No media found'})
            
            title = info.get('title', 'Pinterest Media')
            thumbnail = info.get('thumbnail', None)
            base = request.host_url.rstrip('/')
            encoded = urllib.parse.quote(url, safe='')
            
            return jsonify({
                'success': True,
                'type': 'video',
                'title': title,
                'thumbnail': thumbnail,
                'hd': f'{base}/merge?url={encoded}&q=best',
                'sd': f'{base}/merge?url={encoded}&q=worst',
                'url': f'{base}/merge?url={encoded}&q=best',
                'player_url': f'{base}/player?url={encoded}'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/merge')
def merge():
    """Download + merge audio+video using yt-dlp+ffmpeg, stream to user"""
    pin_url = request.args.get('url')
    quality = request.args.get('q', 'best')
    if not pin_url:
        return jsonify({'error': 'No URL'}), 400

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            outpath = os.path.join(tmpdir, 'video.mp4')
            
            fmt = 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best'
            if quality == 'worst':
                fmt = 'worstvideo[ext=mp4]+worstaudio/worst[ext=mp4]/worst'
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'outtmpl': outpath,
                'format': fmt,
                'merge_output_format': 'mp4',
                'socket_timeout': 60,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([pin_url])
            
            # Find output file
            actual = outpath
            if not os.path.exists(actual):
                files = os.listdir(tmpdir)
                if files:
                    actual = os.path.join(tmpdir, files[0])
            
            if not os.path.exists(actual):
                return jsonify({'error': 'Merge failed'}), 500
            
            filesize = os.path.getsize(actual)
            
            with open(actual, 'rb') as f:
                data = f.read()
        
        return Response(
            data,
            mimetype='video/mp4',
            headers={
                'Content-Disposition': 'attachment; filename="pinterest_video.mp4"',
                'Content-Length': str(filesize),
                'Access-Control-Allow-Origin': '*',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/player')
def player():
    pin_url = request.args.get('url')
    if not pin_url:
        return "No URL", 400
    base = request.host_url.rstrip('/')
    encoded = urllib.parse.quote(pin_url, safe='')
    merge_url = f'{base}/merge?url={encoded}&q=best'
    
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pinterest Video</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#000;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif;padding:16px}}
video{{max-width:100%;max-height:70vh;border-radius:12px}}
h3{{color:#fff;margin:16px;text-align:center;font-size:14px;max-width:400px}}
.btn{{background:#e60023;color:#fff;border:none;padding:14px 32px;border-radius:10px;font-size:16px;cursor:pointer;margin:12px;text-decoration:none;display:inline-block;font-weight:bold}}
p{{color:#aaa;font-size:12px;margin:8px;text-align:center}}
.loading{{color:#fff;font-size:14px;margin:20px}}
</style>
</head>
<body>
<h3>Pinterest Video</h3>
<video controls autoplay playsinline id="vid">
  <source src="{merge_url}" type="video/mp4">
</video>
<p>⏳ First load may take 30-60 seconds (free server)</p>
<a href="{merge_url}" download="pinterest_video.mp4" class="btn">⬇ Download with Sound</a>
<p>On mobile: tap Download button above to save</p>
</body>
</html>"""
    return html


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
