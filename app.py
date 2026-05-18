from flask import Flask, jsonify, request, Response, redirect
from flask_cors import CORS
import yt_dlp
import os
import urllib.parse

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
        # Extract all formats
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
            webpage_url = info.get('webpage_url', url)
            
            hd_url = None
            sd_url = None
            hd_height = 0

            # Pinterest videos: find formats with BOTH video+audio in mp4
            combined = []
            video_only = []
            
            for f in formats:
                fu = f.get('url', '')
                fext = f.get('ext', '')
                fv = f.get('vcodec', 'none')
                fa = f.get('acodec', 'none')
                fh = f.get('height', 0) or 0
                fp = f.get('protocol', '')
                
                if not fu or fv == 'none':
                    continue
                    
                # Skip HLS/DASH streams
                if 'm3u8' in fp or 'dash' in fp:
                    continue
                if 'm3u8' in fu:
                    continue
                    
                if fa != 'none':
                    combined.append(f)
                else:
                    video_only.append(f)

            # Sort by height descending
            combined.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)
            video_only.sort(key=lambda x: x.get('height', 0) or 0, reverse=True)

            if combined:
                hd_url = combined[0].get('url')
                if len(combined) > 1:
                    sd_url = combined[-1].get('url')
            elif video_only:
                hd_url = video_only[0].get('url')
                if len(video_only) > 1:
                    sd_url = video_only[-1].get('url')

            # If still nothing - Pinterest HLS only - use getmp4 endpoint
            if not hd_url:
                # Get best HLS URL
                all_formats = info.get('formats', [])
                for f in reversed(all_formats):
                    fu = f.get('url', '')
                    fv = f.get('vcodec', 'none')
                    if fu and fv != 'none':
                        hls_url = fu
                        base = request.host_url.rstrip('/')
                        # Return getmp4 endpoint which uses yt-dlp to merge
                        encoded = urllib.parse.quote(webpage_url, safe='')
                        return jsonify({
                            'success': True,
                            'type': 'video',
                            'title': title,
                            'thumbnail': thumbnail,
                            'hd': f'{base}/getmp4?url={encoded}',
                            'sd': None,
                            'url': f'{base}/getmp4?url={encoded}'
                        })

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
                return jsonify({'success': False, 'error': 'No video found'})
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/getmp4')
def get_mp4():
    """Download Pinterest video with audio using yt-dlp and stream it"""
    pin_url = request.args.get('url')
    if not pin_url:
        return jsonify({'error': 'No URL'}), 400

    try:
        import tempfile
        import subprocess
        
        # Create temp file
        with tempfile.NamedTemporaryFile(
            suffix='.mp4', 
            delete=False,
            dir='/tmp'
        ) as tmp:
            tmp_path = tmp.name

        # Use yt-dlp to download with audio merged
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'outtmpl': tmp_path,
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'socket_timeout': 60,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([pin_url])

        # Check if file exists
        # yt-dlp may add extension
        actual_path = tmp_path
        if not os.path.exists(actual_path):
            actual_path = tmp_path + '.mp4'
        if not os.path.exists(actual_path):
            actual_path = tmp_path.replace('.mp4', '') + '.mp4'

        if not os.path.exists(actual_path):
            return jsonify({'error': 'Download failed'}), 500

        def stream_file():
            with open(actual_path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.unlink(actual_path)
            except:
                pass

        file_size = os.path.getsize(actual_path)
        
        return Response(
            stream_file(),
            mimetype='video/mp4',
            headers={
                'Content-Disposition': 'attachment; filename="pinterest_video.mp4"',
                'Content-Length': str(file_size),
                'Access-Control-Allow-Origin': '*',
                'Cache-Control': 'no-cache'
            }
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
