from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yt_dlp
import os
import urllib.parse

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'status': 'running', 'message': 'Pinterest API'})

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
        return jsonify({'error': 'No URL'}), 400
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            outpath = os.path.join(tmpdir, 'out.mp4')
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'outtmpl': outpath,
                'format': 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
                'socket_timeout': 60,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([pin_url])
            # Find file
            actual = outpath
            if not os.path.exists(actual):
                files = [f for f in os.listdir(tmpdir) if f.endswith('.mp4')]
                if files:
                    actual = os.path.join(tmpdir, files[0])
                else:
                    files2 = os.listdir(tmpdir)
                    if files2:
                        actual = os.path.join(tmpdir, files2[0])
            if not os.path.exists(actual):
                return jsonify({'error': 'File not found after download'}), 500
            with open(actual, 'rb') as f:
                data = f.read()
        return Response(
            data,
            mimetype='video/mp4',
            headers={
                'Content-Disposition': 'attachment; filename="pinterest.mp4"',
                'Content-Length': str(len(data)),
                'Access-Control-Allow-Origin': '*',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/player')
def player():
    pin_url = request.args.get('url')
    if not pin_url:
        return 'No URL', 400
    base = request.host_url.rstrip('/')
    encoded = urllib.parse.quote(pin_url, safe='')
    merge_url = f'{base}/merge?url={encoded}'
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pinterest Video</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#111;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100vh;font-family:sans-serif;padding:20px}}
video{{max-width:100%;max-height:65vh;border-radius:12px;background:#000}}
h3{{color:#fff;margin:16px 0;text-align:center;font-size:15px;max-width:400px;line-height:1.4}}
.btn{{background:#e60023;color:#fff;border:none;padding:14px 32px;border-radius:10px;font-size:16px;font-weight:bold;cursor:pointer;margin:12px 0;text-decoration:none;display:block;text-align:center;width:100%;max-width:300px}}
p{{color:#888;font-size:12px;margin:8px;text-align:center;max-width:300px}}
</style>
</head>
<body>
<h3>Pinterest Video — with Sound</h3>
<video controls autoplay playsinline preload="auto">
  <source src="{merge_url}" type="video/mp4">
</video>
<p>⏳ Video may take 30-60 seconds to load on first play</p>
<a href="{merge_url}" download="pinterest_video.mp4" class="btn">⬇ Download MP4 with Sound</a>
<p>📱 Mobile: tap Download button → file saves to your phone</p>
</body>
</html>"""
    return html


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
