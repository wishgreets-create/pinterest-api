from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yt_dlp
import os
import subprocess
import tempfile
import threading

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return jsonify({'status': 'running', 'message': 'Pinterest Downloader API'})

@app.route('/download')
def download():
    url = request.args.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'No URL provided'})
    
    try:
        # First extract info
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
            
            # Find best HLS or MP4 URL
            hd_url = None
            sd_url = None
            hd_height = 0
            sd_height = 0

            for f in formats:
                fu = f.get('url', '')
                fh = f.get('height', 0) or 0
                fv = f.get('vcodec', 'none')
                
                if not fu or fv == 'none':
                    continue
                
                if fh >= hd_height:
                    sd_url = hd_url
                    sd_height = hd_height
                    hd_url = fu
                    hd_height = fh
                elif fh > sd_height and fh < hd_height:
                    sd_url = fu
                    sd_height = fh

            if not hd_url:
                hd_url = info.get('url')

            if not hd_url:
                return jsonify({'success': False, 'error': 'No video URL found'})

            # Return the stream URL with a proxy endpoint
            return jsonify({
                'success': True,
                'type': 'video',
                'title': title,
                'thumbnail': thumbnail,
                'hd': f'/proxy?url={hd_url}' if '.m3u8' in hd_url else hd_url,
                'sd': (f'/proxy?url={sd_url}' if sd_url and '.m3u8' in sd_url else sd_url) if sd_url else None,
                'url': f'/proxy?url={hd_url}' if '.m3u8' in hd_url else hd_url,
                'stream': hd_url
            })
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/proxy')
def proxy_stream():
    """Stream HLS video as MP4 using ffmpeg"""
    stream_url = request.args.get('url')
    if not stream_url:
        return jsonify({'error': 'No URL'}), 400

    def generate():
        try:
            cmd = [
                'ffmpeg',
                '-i', stream_url,
                '-c', 'copy',
                '-movflags', 'frag_keyframe+empty_moov+faststart',
                '-f', 'mp4',
                'pipe:1'
            ]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=10**6
            )
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                yield chunk
            process.wait()
        except Exception as e:
            print(f'Stream error: {e}')

    return Response(
        generate(),
        mimetype='video/mp4',
        headers={
            'Content-Disposition': 'attachment; filename="pinterest_video.mp4"',
            'Access-Control-Allow-Origin': '*'
        }
    )


@app.route('/getmp4')
def get_mp4():
    """Convert HLS to MP4 and return direct download"""
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'No URL'}), 400

    try:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            tmp_path = tmp.name

        cmd = [
            'ffmpeg', '-y',
            '-i', url,
            '-c', 'copy',
            '-movflags', 'faststart',
            tmp_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)

        def stream_and_delete():
            with open(tmp_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
            os.unlink(tmp_path)

        return Response(
            stream_and_delete(),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': 'attachment; filename="pinterest_video.mp4"',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
