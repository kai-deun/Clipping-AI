import yt_dlp
import os

url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # test url
start_time = 10
end_time = 20
output_filename = "test_section.mp4"

out_tmpl = output_filename.rsplit('.', 1)[0] + '.%(ext)s'

ydl_opts = {
    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'outtmpl': out_tmpl,
    'merge_output_format': 'mp4',
    'quiet': False,
    'overwrites': True,
    'nooverwrites': False,
    'download_ranges': yt_dlp.utils.download_range_func(None, [(start_time, end_time)]),
    'force_keyframes_at_cuts': True
}

ffmpeg_exe = r"D:\CODES\ClippingAI\dependencies\bin\ffmpeg.exe"
if os.path.exists(ffmpeg_exe):
    ydl_opts['ffmpeg_location'] = ffmpeg_exe
    print(f"Using ffmpeg at {ffmpeg_exe}")
else:
    print("ffmpeg not found")

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_file = ydl.prepare_filename(info)
        print("PREPARED FILENAME:", downloaded_file)
        
        base, ext = os.path.splitext(downloaded_file)
        if ext != '.mp4' and os.path.exists(base + '.mp4'):
            downloaded_file = base + '.mp4'
            
        print("FINAL FILENAME:", downloaded_file)
        print("FILE EXISTS?", os.path.exists(downloaded_file))
except Exception as e:
    print("ERROR:", e)
