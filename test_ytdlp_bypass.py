import yt_dlp

url = 'https://www.youtube.com/watch?v=4bcPNT3J1f8'
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'test.m4a',
    'quiet': False,
    'extractor_args': {'youtube': {'player_client': ['android']}}
}
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print("Success")
except Exception as e:
    print("Error:", e)
