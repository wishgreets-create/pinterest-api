from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yt_dlp
import os
import urllib.parse
import tempfile

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'status': 'running'})

@app.route('/download')
def download():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'No URL'})
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'socket_timeout': 30}) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return jsonify({'success': False, 'error': 'Not found'})
            base = request.host_url.rstrip('/')
            encoded = urllib.parse.quote(url, safe='')
            return jsonify({
                'success': True,
                'type': 'video',
                'title': info.get('title', 'Pinterest Video'),
                'thumbnail': info.get('thumbnail'),
                'hd': f'{base}/merge?url={encoded}',
                'sd': None,
                'url': f'{base}/merge?url={encoded}',
                'player_url': f'{base}/player?url={encoded}'
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/merge')
def merge():
    pin_url = request.args.get('url')
    if not pin_url:
        return 'No URL', 400
    try:
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'v.mp4')
            opts = {
                'quiet': True,
                'outtmpl': out,
                'format': 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'socket_timeout': 60,
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([pin_url])
            # Find output
            f = out
            if not os.path.exists(f):
                files = os.listdir(d)
                if files:
                    f = os.path.join(d, files[0])
            if not os.path.exists(f):
                return 'File not found', 500
            with open(f, 'rb') as fh:
                data = fh.read()
        return Response(data, mimetype='video/mp4', headers={
            'Content-Disposition': 'attachment; filename="video.mp4"',
            'Content-Length': str(len(data)),
            'Access-Control-Allow-Origin': '*'
        })
    except Exception as e:
        return str(e), 500

@app.route('/player')
def player():
    pin_url = request.args.get('url')
    if not pin_url:
        return 'No URL', 400
    base = request.host_url.rstrip('/')
    enc = urllib.parse.quote(pin_url, safe='')
    mu = f'{base}/merge?url={enc}'
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pinterest Video</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#111;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif;padding:20px}}
video{{max-width:100%;max-height:65vh;border-radius:12px}}
h3{{color:#fff;margin:16px 0;text-align:center;font-size:15px}}
.btn{{background:#e60023;color:#fff;border:none;padding:14px 32px;border-radius:10px;font-size:16px;font-weight:bold;cursor:pointer;margin:12px 0;text-decoration:none;display:block;text-align:center;width:100%;max-width:300px}}
p{{color:#888;font-size:12px;margin:8px;text-align:center}}
</style>
</head>
<body>
<h3>Pinterest Video</h3>
<video controls autoplay playsinline>
<source src="{mu}" type="video/mp4">
</video>
<p>⏳ First load takes 30-60 seconds</p>
<a href="{mu}" download="video.mp4" class="btn">⬇ Download with Sound</a>
<p>📱 Mobile: tap Download → saves to phone</p>
</body>
</html>'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
