from flask import Flask, jsonify, request, Response
from flask_cors import CORS
import yt_dlp
import os
import urllib.request

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
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'socket_timeout': 30,
            # Get best format with audio
            'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio/best',
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

            # Try to find MP4 with audio first
            for f in reversed(formats):
                fu = f.get('url', '')
                fext = f.get('ext', '')
                fv = f.get('vcodec', 'none')
                fa = f.get('acodec', 'none')
                fh = f.get('height', 0) or 0
                
                if not fu or fv == 'none':
                    continue
                
                # Best: MP4 with both video and audio
                if fext == 'mp4' and fa != 'none' and not hd_url:
                    hd_url = fu
                    continue
                    
                if fext == 'mp4' and fa != 'none' and not sd_url and fu != hd_url:
                    sd_url = fu

            # If no MP4+audio found, get any video
            if not hd_url:
                for f in reversed(formats):
                    fu = f.get('url', '')
                    fv = f.get('vcodec', 'none')
                    if fu and fv != 'none':
                        hd_url = fu
                        break

            # Last fallback
            if not hd_url:
                hd_url = info.get('url')

            if hd_url:
                # Build download URL
                base_url = request.host_url.rstrip('/')
                
                # If HLS, use proxy to add audio
                if '.m3u8' in hd_url:
                    dl_url = f'{base_url}/stream?url={urllib.parse.quote(hd_url)}'
                else:
                    dl_url = hd_url

                sd_dl = None
                if sd_url:
                    if '.m3u8' in sd_url:
                        sd_dl = f'{base_url}/stream?url={urllib.parse.quote(sd_url)}'
                    else:
                        sd_dl = sd_url

                return jsonify({
                    'success': True,
                    'type': 'video',
                    'title': title,
                    'thumbnail': thumbnail,
                    'hd': dl_url,
                    'sd': sd_dl,
                    'url': dl_url
                })
            else:
                return jsonify({'success': False, 'error': 'No video found'})
                
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/stream')
def stream_video():
    """Stream HLS video with audio as MP4"""
    import urllib.parse
    stream_url = request.args.get('url')
    if not stream_url:
        return jsonify({'error': 'No URL'}), 400

    try:
        # Use yt-dlp to stream with audio merged
        ydl_opts = {
            'quiet': True,
            'format': 'best',
            'outtmpl': '-',
        }
        
        # Get the direct URL with audio
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try to find a direct URL from the m3u8
            info = ydl.extract_info(stream_url, download=False)
            if info:
                # Look for mp4 format specifically
                formats = info.get('formats', [])
                for f in reversed(formats):
                    fu = f.get('url', '')
                    fa = f.get('acodec', 'none')
                    fext = f.get('ext', '')
                    if fu and fa != 'none' and fext == 'mp4':
                        # Redirect to direct URL
                        from flask import redirect
                        return redirect(fu)
                
                # Fallback to best URL
                best_url = info.get('url') or (formats[-1].get('url') if formats else None)
                if best_url:
                    from flask import redirect
                    return redirect(best_url)

        return jsonify({'error': 'Could not process stream'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import urllib.parse
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
