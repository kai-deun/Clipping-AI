import os
import sys
import gc
import json
import time
import requests
import re

# CRITICAL FIX for CTranslate2 (Faster-Whisper backend) failing to find cuBLAS
# on Windows since we uninstalled PyTorch. We manually add the nvidia bin directories
# to the DLL search path before any deep learning libraries are imported.
if os.name == 'nt':
    import site
    for site_pkg in site.getsitepackages():
        nvidia_path = os.path.join(site_pkg, 'nvidia')
        if os.path.exists(nvidia_path):
            for pkg in os.listdir(nvidia_path):
                bin_dir = os.path.join(nvidia_path, pkg, 'bin')
                if os.path.exists(bin_dir):
                    try:
                        os.add_dll_directory(bin_dir)
                    except Exception:
                        pass

import argparse
import numpy as np
import subprocess
from moviepy import CompositeAudioClip, concatenate_videoclips
import random
import gc

# ==============================================================================
# FFmpeg environment configuration (Must be executed before importing moviepy)
# ==============================================================================
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ffmpeg_dir = os.path.join(workspace_dir, "dependencies", "bin")
ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")

# Inject ffmpeg into PATH for yt-dlp and other tools
if os.path.exists(ffmpeg_dir) and ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = f"{ffmpeg_dir};{os.environ.get('PATH', '')}"

if os.path.exists(ffmpeg_exe):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
    os.environ["FFMPEG_BINARY"] = ffmpeg_exe
    print(f"[FFmpeg] Configured environment to use local FFmpeg: {ffmpeg_exe}")
else:
    print("[FFmpeg] Warning: Local FFmpeg binary not found at bin/ffmpeg.exe. Falling back to system paths.")

# Load NVIDIA CUDA DLLs globally for CTranslate2 (faster-whisper)
try:
    import site
    site_packages = site.getsitepackages()
except Exception:
    site_packages = [os.path.join(workspace_dir, "venv", "Lib", "site-packages")]

for sp in site_packages + sys.path:
    nvidia_path = os.path.join(sp, "nvidia")
    if os.path.exists(nvidia_path):
        for pkg in os.listdir(nvidia_path):
            bin_path = os.path.join(nvidia_path, pkg, "bin")
            if os.path.exists(bin_path):
                os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
                try: os.add_dll_directory(bin_path)
                except Exception: pass

from moviepy import VideoFileClip, CompositeVideoClip, ColorClip

# Ensure media/assets/backgrounds directory exists
os.makedirs(os.path.join(workspace_dir, "media", "assets", "backgrounds"), exist_ok=True)

# ==============================================================================
# Helper Functions
# ==============================================================================

def download_youtube_video(url, output_filename):
    import yt_dlp
    print(f"\n[yt-dlp] Downloading video from: {url}")
    out_tmpl = output_filename.rsplit('.', 1)[0] + '.%(ext)s'
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'quiet': False,
        'overwrites': True,
        'nooverwrites': False,
        'extractor_args': {'youtube': {'player_client': ['android']}}
    }
    if os.path.exists(ffmpeg_exe):
        ydl_opts['ffmpeg_location'] = ffmpeg_exe
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_file = ydl.prepare_filename(info)
        base, ext = os.path.splitext(downloaded_file)
        if ext != '.mp4' and os.path.exists(base + '.mp4'):
            downloaded_file = base + '.mp4'
            
    print(f"[yt-dlp] Successfully downloaded to: {downloaded_file}")
    return downloaded_file

def download_youtube_audio(url, output_filename):
    import yt_dlp
    print(f"\n[yt-dlp] Downloading audio from: {url}")
    out_tmpl = output_filename.rsplit('.', 1)[0] + '.%(ext)s'
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out_tmpl,
        'quiet': False,
        'overwrites': True,
        'nooverwrites': False,
        'extractor_args': {'youtube': {'player_client': ['android']}}
    }
    if os.path.exists(ffmpeg_exe):
        ydl_opts['ffmpeg_location'] = ffmpeg_exe
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_file = ydl.prepare_filename(info)
        base, ext = os.path.splitext(downloaded_file)
        if ext != '.m4a' and os.path.exists(base + '.m4a'):
            downloaded_file = base + '.m4a'
            
    print(f"[yt-dlp] Successfully downloaded audio to: {downloaded_file}")
    return downloaded_file

def download_youtube_video_section(url, start_time, end_time, output_filename):
    import yt_dlp
    print(f"\n[yt-dlp] Downloading video section ({start_time}s - {end_time}s) from: {url}")
    out_tmpl = output_filename.rsplit('.', 1)[0] + '.%(ext)s'
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': out_tmpl,
        'merge_output_format': 'mp4',
        'quiet': False,
        'overwrites': True,
        'nooverwrites': False,
        'download_ranges': yt_dlp.utils.download_range_func(None, [(start_time, end_time)]),
        'force_keyframes_at_cuts': True,
        'extractor_args': {'youtube': {'player_client': ['android']}}
    }
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise Exception("yt-dlp failed to extract info or download the video.")
        downloaded_file = ydl.prepare_filename(info)
        base, ext = os.path.splitext(downloaded_file)
        if ext != '.mp4' and os.path.exists(base + '.mp4'):
            downloaded_file = base + '.mp4'
            
    if not downloaded_file or not os.path.exists(downloaded_file):
        raise Exception(f"Video section failed to download. Expected file at: {downloaded_file}")
            
    print(f"[yt-dlp] Successfully downloaded section to: {downloaded_file}")
    return downloaded_file


def extract_audio_for_transcription(video_path, audio_path="temp_audio.wav"):
    print(f"\n[Audio] Extracting audio track to: {audio_path}")
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(
        audio_path,
        fps=16000,
        nbytes=2,
        codec='pcm_s16le',
        logger=None
    )
    clip.close()
    print("[Audio] Audio extraction complete.")
    return audio_path

# ==============================================================================
# GPU WhisperX Transcription Layer
# REFACTOR NOTE: We transitioned from `faster_whisper` to `whisperx` because 
# faster_whisper only provides phrase-level timestamps, which break interactive 
# transcripts. WhisperX utilizes forced alignment (Wav2Vec2) to generate highly 
# precise word-level boundaries and implements Pyannote for speaker diarization.
# ==============================================================================
def transcribe_audio_locally(audio_path, model_size="large-v3"):
    """
    Transcribes audio using pure Faster-Whisper with strict float16 CUDA settings.
    Bypasses PyTorch entirely to ensure compatibility with RTX 5000 series GPUs.
    """
    print(f"\n[Faster-Whisper] Loading Model ({model_size}) on GPU (float16)...")
    from faster_whisper import WhisperModel
    
    device = "cuda"
    compute_type = "float16"
    
    # Transcribe with faster-whisper directly and request word-level timestamps
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=True)
    
    transcript_segments = []
    for segment in segments:
        mapped_words = []
        if segment.words:
            for w in segment.words:
                mapped_words.append({'word': w.word, 'start': w.start, 'end': w.end})
                
        transcript_segments.append({
            'start': segment.start,
            'end': segment.end,
            'text': segment.text,
            'words': mapped_words,
            'speaker': 'SPEAKER_00'
        })
        
    # Flush model from memory
    del model
    gc.collect()
    
    return transcript_segments

# ==============================================================================
# YouTube Heatmap Scraper Layer (Tier 1)
# ==============================================================================

def get_youtube_heatmap(video_url):
    try:
        print(f"[Heatmap Extractor] Fetching heatmap via yt-dlp: {video_url}")
        import yt_dlp
        ydl_opts = {'quiet': True}
        if os.path.exists(ffmpeg_exe):
            ydl_opts['ffmpeg_location'] = ffmpeg_exe
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            raw_heatmap = info.get('heatmap')
            if raw_heatmap:
                processed_heatmap = []
                for entry in raw_heatmap:
                    processed_heatmap.append({
                        "start_time": entry.get("start_time", 0.0),
                        "end_time": entry.get("end_time", 0.0),
                        "score": entry.get("value", 0.0)
                    })
                print(f"[Heatmap Extractor] Extracted {len(processed_heatmap)} heatmap markers via yt-dlp.")
                return processed_heatmap
    except Exception as e:
        print(f"[Heatmap Extractor Warning] yt-dlp heatmap extraction failed: {e}")

    # Regex Fallback
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        print(f"[Heatmap Extractor] Falling back to regex HTML scraper for: {video_url}")
        response = requests.get(video_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None

        match = re.search(r"ytInitialData\s*=\s*({.+?});", response.text, re.S)
        if not match:
            match = re.search(r"var ytInitialData\s*=\s*({.+?});</script>", response.text, re.S)
        if not match:
            return None

        data = json.loads(match.group(1))
        framework = data.get("playerOverlays", {}).get("playerOverlayRenderer", {})
        heat_seeker = framework.get("decoratedPlayerBarRenderer", {}).get("decoratedPlayerBarRenderer", {}).get("playerBar", {}).get("multiMarkersPlayerBarRenderer", {})
        markers = heat_seeker.get("markersMap", [])
        heatmap_entries = next((marker.get("value", {}).get("chapters", []) for marker in markers if marker.get("key") == "HEATSEEKER"), [])
                
        processed_heatmap = []
        for entry in heatmap_entries:
            renderer = entry.get("heatSeekerChapterRenderer", {})
            start_ms = float(renderer.get("startMillis", 0))
            duration_ms = float(renderer.get("durationMillis", 0))
            score = float(renderer.get("intensityScoreNormalized", 0.0))
            
            processed_heatmap.append({
                "start_time": start_ms / 1000.0,
                "end_time": (start_ms + duration_ms) / 1000.0,
                "score": score
            })
        print(f"[Heatmap Extractor] Extracted {len(processed_heatmap)} heatmap markers via regex fallback.")
        return processed_heatmap if processed_heatmap else None

    except Exception as e:
        print(f"[Heatmap Extractor Exception] Analysis error: {e}")
        return None

def snap_to_sentence_boundary(start_idx, end_idx, whisper_segments, max_duration):
    """
    Expands or contracts the end_idx to ensure the clip doesn't end mid-sentence.
    Looks for '.', '!', '?' AND conversational pauses to find a natural conclusion.
    """
    def is_natural_conclusion(idx):
        text = whisper_segments[idx]['text'].strip()
        has_punct = any(text.endswith(p) for p in ['.', '!', '?'])
        if idx >= len(whisper_segments) - 1:
            return True
        pause = whisper_segments[idx+1]['start'] - whisper_segments[idx]['end']
        
        # A natural conclusion is a strong punctuation OR a significant pause in speaking
        return (has_punct and pause > 0.3) or pause > 1.0

    current_idx = end_idx
    
    # Try to expand forward to find a solid conclusion
    while current_idx < len(whisper_segments):
        if is_natural_conclusion(current_idx):
            if (whisper_segments[current_idx]['end'] - whisper_segments[start_idx]['start']) <= max_duration:
                return current_idx
            else:
                break
        current_idx += 1
        
    # If we couldn't expand without hitting max_duration, contract backward
    current_idx = end_idx
    while current_idx > start_idx:
        if is_natural_conclusion(current_idx):
            return current_idx
        current_idx -= 1
        
    return end_idx

def sync_heatmap_with_whisper(heatmap_entries, whisper_segments, min_duration=50, max_duration=90, add_captions=False):
    if not whisper_segments:
        return []

    print("[Heatmap Sync] Syncing heatmap segments with whisper sentence boundaries...")
    sorted_heatmap = sorted(heatmap_entries, key=lambda x: x['score'], reverse=True)
    
    candidates = []
    for peak in sorted_heatmap:
        peak_center = (peak['start_time'] + peak['end_time']) / 2.0
        
        closest_seg_idx = min(range(len(whisper_segments)), key=lambda i: abs((whisper_segments[i]['start'] + whisper_segments[i]['end'])/2.0 - peak_center))
        
        start_idx = closest_seg_idx
        end_idx = closest_seg_idx
        
        while start_idx > 0 and (whisper_segments[end_idx]['end'] - whisper_segments[start_idx]['start']) < min_duration:
            start_idx -= 1
        while end_idx < len(whisper_segments) - 1 and (whisper_segments[end_idx]['end'] - whisper_segments[start_idx]['start']) < min_duration:
            end_idx += 1
            
        while (whisper_segments[end_idx]['end'] - whisper_segments[start_idx]['start']) > max_duration and end_idx > start_idx:
            end_idx -= 1
            
        end_idx = snap_to_sentence_boundary(start_idx, end_idx, whisper_segments, max_duration)
        
        start_time = whisper_segments[start_idx]['start']
        end_time = whisper_segments[end_idx]['end']
        duration = end_time - start_time
        
        clip_text = " ".join([whisper_segments[k]['text'] for k in range(start_idx, end_idx + 1)])
        
        candidates.append({
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'score': peak['score'],
            'text': clip_text,
            'overlay_text': "",
            'add_captions': add_captions
        })
        
    return candidates

def generate_title_with_ollama(text):
    print(f"\n[LLM] Generating catchy title for clip...")
    prompt = f"Generate a short, catchy, and viral video title (under 6 words) for the following transcript segment. Output ONLY the title, no quotes, no markdown, no explanations.\n\nTranscript: {text}"
    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        })
        if response.status_code == 200:
            title = response.json().get('response', '').strip().strip('"').strip("'")
            # If it hallucinated and outputted a lot of text, truncate it
            if len(title) > 60:
                title = title[:57] + "..."
            return title
    except Exception as e:
        print(f"[LLM Error] Local Ollama parsing failed: {e}")
    return None

# ==============================================================================
# NLP Heuristics Fallback (Tier 3)
# ==============================================================================
def detect_hooks_nlp(segments, min_duration=50, max_duration=90, add_captions=False):
    print("\n[NLP] Analyzing transcript segments for logical hooks (50-90 seconds)...")
    candidates = []
    n = len(segments)
    
    hook_keywords = [
        "actually", "imagine", "did you know", "but", "so", "why", "secret", "look", 
        "listen", "first", "most", "this is", "never", "always", "how", "what if"
    ]
    
    for i in range(n):
        start_seg = segments[i]
        start_time = start_seg['start']
        
        for j in range(i, n):
            end_seg = segments[j]
            end_time = end_seg['end']
            duration = end_time - start_time
            
            if min_duration <= duration <= max_duration:
                j_snapped = snap_to_sentence_boundary(i, j, segments, max_duration)
                snapped_end_time = segments[j_snapped]['end']
                snapped_duration = snapped_end_time - start_time
                
                if min_duration <= snapped_duration <= max_duration:
                    text = " ".join([segments[k]['text'] for k in range(i, j_snapped + 1)])
                    score = 10.0
                    
                    lower_text = text.lower()
                    for kw in hook_keywords:
                        if lower_text.startswith(kw) or f" {kw}" in lower_text:
                            score += 5.0
                            
                    candidates.append({
                        'start_time': start_time,
                        'end_time': snapped_end_time,
                        'duration': snapped_duration,
                        'text': text,
                        'score': score,
                        'overlay_text': "",
                        'add_captions': add_captions
                    })
                break
            elif duration > max_duration:
                break
                
    return candidates

def filter_overlapping_clips(candidates):
    candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
    selected_clips = []
    for cand in candidates:
        overlap = False
        for sel in selected_clips:
            if cand['start_time'] < sel['end_time'] and sel['start_time'] < cand['end_time']:
                overlap = True
                break
        if not overlap:
            selected_clips.append(cand)
            
    selected_clips.sort(key=lambda x: x['start_time'])
    return selected_clips

# ==============================================================================
# Conditional Layout Compositing & Rendering (MoviePy 2.x Adapted)
# REFACTOR NOTE: MoviePy 2.x `transform` signature bugs have been fixed by wrapping
# callbacks in explicit `lambda gf, t:` functions. Subtitle generation now parses
# precise WhisperX word-level timings and renders multi-line text at the bottom 75%.
# ==============================================================================

import cv2

def make_caption_frame_modifier(clip_start_time, local_transcript_segments):
    """
    Parses exact word-level WhisperX timings. 
    Renders karaoke-style subtitles: displays a batch of words and highlights the currently spoken word.
    """
    all_words = []
    for seg in local_transcript_segments:
        if 'words' in seg:
            for w in seg['words']:
                if 'start' in w and 'end' in w:
                    all_words.append(w)
                    
    # Group words into logical batches (4-7 words, breaking on punctuation)
    batches = []
    current_batch = []
    for w in all_words:
        current_batch.append(w)
        text = w['word'].strip()
        has_punct = any(text.endswith(p) for p in ['.', '!', '?', ','])
        
        if len(current_batch) >= 6 or (has_punct and len(current_batch) >= 3):
            batches.append({
                'words': current_batch,
                'start': current_batch[0]['start'],
                'end': current_batch[-1]['end']
            })
            current_batch = []
            
    if current_batch:
        batches.append({
            'words': current_batch,
            'start': current_batch[0]['start'],
            'end': current_batch[-1]['end']
        })
        
    # Connect batch display times to prevent flickering
    for i in range(len(batches)-1):
        batches[i]['display_end'] = batches[i+1]['start']
    if batches:
        batches[-1]['display_end'] = batches[-1]['end'] + 1.0

    def draw_captions_filter(get_frame, t):
        frame = np.copy(get_frame(t))
        current_global_time = clip_start_time + t
        h, w, _ = frame.shape
        
        # Find the active batch
        active_batch = None
        for b in batches:
            if b['start'] <= current_global_time < b['display_end']:
                active_batch = b
                break
                
        if not active_batch:
            return frame
            
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = w / 550.0
        thickness = max(2, int(font_scale * 3.5))
        max_width = int(w * 0.85)
        space_width = cv2.getTextSize(" ", font, font_scale, thickness)[0][0]
        
        # Wrap words into lines
        lines = []
        current_line_words = []
        current_line_width = 0
        
        for w_obj in active_batch['words']:
            word_str = w_obj['word'].strip()
            word_width = cv2.getTextSize(word_str, font, font_scale, thickness)[0][0]
            
            if current_line_width + word_width + space_width > max_width and current_line_words:
                lines.append(current_line_words)
                current_line_words = [w_obj]
                current_line_width = word_width
            else:
                current_line_words.append(w_obj)
                if current_line_width == 0:
                    current_line_width = word_width
                else:
                    current_line_width += space_width + word_width
                    
        if current_line_words:
            lines.append(current_line_words)
            
        # Determine exactly which word is currently being spoken
        active_word_obj = None
        for w_obj in active_batch['words']:
            if current_global_time >= w_obj['start']:
                active_word_obj = w_obj
            else:
                break
                
        # Calculate Y starting position
        line_heights = [cv2.getTextSize(lw[0]['word'].strip(), font, font_scale, thickness)[0][1] for lw in lines if lw]
        total_block_height = sum(lh + int(15 * font_scale) for lh in line_heights)
        
        start_y = int(h * 0.75) - (total_block_height // 2)
        current_y = start_y
        
        for i, line_words in enumerate(lines):
            if not line_words: continue
            
            # Center the line
            line_w = sum(cv2.getTextSize(lw['word'].strip(), font, font_scale, thickness)[0][0] for lw in line_words)
            line_w += space_width * (len(line_words) - 1)
            
            current_x = (w - line_w) // 2
            line_h = line_heights[i]
            
            for lw in line_words:
                word_str = lw['word'].strip()
                is_active = (lw == active_word_obj)
                
                # Active word is Yellow (BGR: 0, 255, 255), others White
                color = (0, 255, 255) if is_active else (255, 255, 255)
                
                # Drop shadow
                cv2.putText(frame, word_str, (current_x + 3, current_y + 3), font, font_scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
                # Main text
                cv2.putText(frame, word_str, (current_x, current_y), font, font_scale, color, thickness, cv2.LINE_AA)
                
                word_width = cv2.getTextSize(word_str, font, font_scale, thickness)[0][0]
                current_x += word_width + space_width
                
            current_y += line_h + int(15 * font_scale)
            
        return frame
    return draw_captions_filter

def render_pro_clip(primary_clip, target_w=1080, target_h=1920):
    orig_w, orig_h = primary_clip.size
    orig_ratio = orig_w / orig_h
    target_ratio = target_w / target_h

    primary_scaled = primary_clip.resized(width=target_w)
    
    if abs(orig_ratio - target_ratio) < 0.05:
        return primary_scaled

    dynamic_primary_pos = primary_scaled.with_position(('center', 'center'))
    from moviepy import ColorClip
    bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=primary_clip.duration)

    final_composite = CompositeVideoClip([bg_clip, dynamic_primary_pos], size=(target_w, target_h))
    return final_composite

def transcribe_video(url="", input_video_path="", model_size="large-v3", callback=None):
    download_dir = os.path.join(workspace_dir, "media", "downloaded_videos")
    os.makedirs(download_dir, exist_ok=True)
    
    pipeline_start = time.time()
    def log(stage, progress, msg):
        elapsed = time.time() - pipeline_start
        print(f"[{stage}] [{elapsed:.2f}s] {msg}")
        if callback:
            callback(stage, progress, msg)
            
    if input_video_path and os.path.exists(input_video_path):
        log("Downloading", 10, f"Using provided local video: {input_video_path}")
        raw_video = input_video_path
        log("Transcribing", 20, "Extracting audio for local transcription...")
        audio_path = "temp_audio.wav"
        extract_audio_for_transcription(raw_video, audio_path)
    elif url:
        log("Downloading", 5, "Downloading AUDIO ONLY from YouTube...")
        unique_audio = os.path.join(download_dir, f"downloaded_audio_{int(time.time())}.m4a")
        audio_path = download_youtube_audio(url, unique_audio)
    else:
        raise ValueError("Either url or input_video_path must be provided")
    
    log("Transcribing", 30, f"Transcribing locally with GPU Faster-Whisper ({model_size})...")
    try:
        segments = transcribe_audio_locally(audio_path, model_size=model_size)
    except Exception as e:
        log("Transcribing", 40, f"Transcription failed: {e}. Cannot continue without timings.")
        return []
            
    log("Complete", 100, "Transcription complete.")
    gc.collect()
    return segments

def analyze_hooks(segments, url="", campaign_rules=None, num_clips=3, callback=None):
    pipeline_start = time.time()
    def log(stage, progress, msg):
        elapsed = time.time() - pipeline_start
        print(f"[{stage}] [{elapsed:.2f}s] {msg}")
        if callback:
            callback(stage, progress, msg)
            
    hooks = []
    
    if url and ("youtube.com" in url or "youtu.be" in url):
        log("Tracking", 50, "Fetching YouTube Heatmap data...")
        heatmap_entries = get_youtube_heatmap(url)
        if heatmap_entries:
            log("Tracking", 53, "Heatmap retrieved. Syncing with whisper segments...")
            candidates = sync_heatmap_with_whisper(heatmap_entries, segments, min_duration=50, max_duration=90)
            hooks = filter_overlapping_clips(candidates)
            
    if not hooks:
        log("Tracking", 50, "Invoking NLP heuristics hook selector to find 50-90s clips...")
        candidates = detect_hooks_nlp(segments, min_duration=50, max_duration=90)
        hooks = filter_overlapping_clips(candidates)
        
    if not hooks:
        clip_dur = 55.0
        hooks = [{'start_time': 0.0, 'end_time': clip_dur, 'duration': clip_dur, 'overlay_text': "", 'score': 1.0, 'text': 'Default clip text'}]
        
    log("Tracking", 80, "Generating viral titles for clips using local Ollama Llama-3...")
    for idx, h in enumerate(hooks):
        if not h.get('title') and h.get('text'):
            title = generate_title_with_ollama(h['text'])
            if title:
                h['title'] = title
            else:
                h['title'] = f"Generated Clip {idx+1}"
        elif not h.get('title'):
            h['title'] = f"Generated Clip {idx+1}"
            
    log("Complete", 100, f"Analysis complete. Found {len(hooks)} hooks.")
    return hooks


def generate_single_clip(target_hook, segments, url="", input_video_path="", output_filename="clip.mp4", enable_subtitles=False, callback=None):
    output_dir = os.path.join(workspace_dir, "media", "clips")
    os.makedirs(output_dir, exist_ok=True)
    download_dir = os.path.join(workspace_dir, "media", "downloaded_videos")
    os.makedirs(download_dir, exist_ok=True)
    target_w, target_h = 1080, 1920
    
    out_path = os.path.join(output_dir, output_filename)
    pipeline_start = time.time()
    
    def log(stage, progress, msg):
        elapsed = time.time() - pipeline_start
        print(f"[{stage}] [{elapsed:.2f}s] {msg}")
        if callback:
            callback(stage, progress, msg)
            
    overlay = target_hook.get('overlay_text', "")
    log("Rendering", 10, f"Rendering clip (length: {int(target_hook['end_time'] - target_hook['start_time'])}s)")
    
    try:
        if url:
            section_filename = os.path.join(download_dir, f"section_{int(time.time())}.mp4")
            pad_start = max(0, target_hook['start_time'] - 5)
            pad_end = target_hook['end_time'] + 5
            
            log("Rendering", 30, "Downloading video section...")
            local_raw_video = download_youtube_video_section(url, pad_start, pad_end, section_filename)
            
            main_clip = VideoFileClip(local_raw_video)
            local_start = target_hook['start_time'] - pad_start
            local_end = target_hook['end_time'] - pad_start
            local_start = max(0, min(local_start, main_clip.duration))
            local_end = max(local_start + 1.0, min(local_end, main_clip.duration))
            sub_clip = main_clip.subclipped(local_start, local_end)
        else:
            main_clip = VideoFileClip(input_video_path)
            sub_clip = main_clip.subclipped(target_hook['start_time'], target_hook['end_time'])
        
        log("Rendering", 60, "Compositing video and formatting...")
        formatted_canvas = render_pro_clip(sub_clip, target_w=target_w, target_h=target_h)
        
        if overlay:
            formatted_canvas = formatted_canvas.transform(lambda gf, t: add_cta_overlay(np.copy(gf(t)), overlay))
            
        if enable_subtitles or target_hook.get("add_captions", False):
            caption_callback = make_caption_frame_modifier(
                clip_start_time=target_hook['start_time'],
                local_transcript_segments=segments
            )
            formatted_canvas = formatted_canvas.transform(lambda gf, t: caption_callback(gf, t))
        
        log("Rendering", 80, "Writing final file...")
        formatted_canvas.write_videofile(
            out_path,
            fps=sub_clip.fps if sub_clip.fps else 30,
            codec="h264_nvenc",
            audio_codec="aac",
            preset="fast",
            threads=4,
            logger=None
        )
        
        sub_clip.close()
        main_clip.close()
        formatted_canvas.close()
        
        if url and os.path.exists(local_raw_video):
            try: os.remove(local_raw_video)
            except: pass
            
        log("Complete", 100, "Rendering complete.")
        return out_path
    except Exception as e:
        log("Rendering", 100, f"Failed to render clip: {e}")
        return None

if __name__ == "__main__":
    pass
