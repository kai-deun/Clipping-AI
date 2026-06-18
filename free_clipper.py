import os
import sys
import time
import argparse
import numpy as np
import subprocess
from moviepy import CompositeAudioClip, concatenate_videoclips
import json
import random
import re
import requests
import gc

# ==============================================================================
# FFmpeg environment configuration (Must be executed before importing moviepy)
# ==============================================================================
workspace_dir = os.path.dirname(os.path.abspath(__file__))
bin_dir = os.path.join(workspace_dir, "bin")
if os.path.exists(bin_dir):
    os.environ["PATH"] = bin_dir + os.path.pathsep + os.environ["PATH"]

ffmpeg_exe = os.path.join(bin_dir, "ffmpeg.exe")
if os.path.exists(ffmpeg_exe):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_exe
    os.environ["FFMPEG_BINARY"] = ffmpeg_exe
    print(f"[FFmpeg] Configured environment to use local FFmpeg: {ffmpeg_exe}")
else:
    print("[FFmpeg] Warning: Local FFmpeg binary not found at bin/ffmpeg.exe. Falling back to system paths.")

from moviepy import VideoFileClip, CompositeVideoClip, ColorClip

# Ensure assets/backgrounds directory exists
os.makedirs(os.path.join(workspace_dir, "assets", "backgrounds"), exist_ok=True)

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
        'force_keyframes_at_cuts': True
    }
    if os.path.exists(ffmpeg_exe):
        ydl_opts['ffmpeg_location'] = ffmpeg_exe
        
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded_file = ydl.prepare_filename(info)
        base, ext = os.path.splitext(downloaded_file)
        if ext != '.mp4' and os.path.exists(base + '.mp4'):
            downloaded_file = base + '.mp4'
            
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
# GPU WhisperX Transcription Layer (REPLACES faster_whisper)
# ==============================================================================
def transcribe_audio_locally(audio_path, model_size="large-v3"):
    """
    Transcribes audio using WhisperX with strict float16 CUDA settings.
    Executes transcription, alignment, and diarization.
    """
    print(f"\n[WhisperX] Loading WhisperX Model ({model_size}) on GPU (float16)...")
    import whisperx
    import torch
    
    device = "cuda"
    compute_type = "float16"
    
    # 1. Transcribe with WhisperX
    model = whisperx.load_model(model_size, device, compute_type=compute_type)
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16)
    
    # Free base model to conserve VRAM for alignment and diarization
    del model
    gc.collect()
    torch.cuda.empty_cache()
    
    # 2. Align whisper output to get highly precise word-level timings
    print("[WhisperX] Aligning word timestamps...")
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
    
    # Free alignment model
    del model_a
    gc.collect()
    torch.cuda.empty_cache()
    
    # 3. Diarize to assign speakers (Offline, no auth token)
    print("[WhisperX] Diarizing speakers...")
    diarize_model = whisperx.DiarizationPipeline(use_auth_token=False, device=device)
    diarize_segments = diarize_model(audio)
    result = whisperx.assign_word_speakers(diarize_segments, result)
    
    # Free diarization model
    del diarize_model
    gc.collect()
    torch.cuda.empty_cache()
    
    # 4. Reconstruct dictionary
    transcript_segments = []
    for segment in result["segments"]:
        words = []
        if 'words' in segment:
            for w in segment['words']:
                if 'start' in w and 'end' in w:
                    words.append({'word': w['word'], 'start': w['start'], 'end': w['end']})
        transcript_segments.append({
            'start': segment['start'],
            'end': segment['end'],
            'text': segment['text'],
            'words': words,
            'speaker': segment.get('speaker', 'SPEAKER_00')
        })
    return transcript_segments

# ==============================================================================
# YouTube Heatmap Scraper Layer
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
    Looks for '.', '!', '?' near the end_idx.
    """
    def has_end_punct(text):
        return any(text.strip().endswith(p) for p in ['.', '!', '?'])

    current_idx = end_idx
    
    while current_idx < len(whisper_segments):
        if has_end_punct(whisper_segments[current_idx]['text']):
            if (whisper_segments[current_idx]['end'] - whisper_segments[start_idx]['start']) <= max_duration:
                return current_idx
            else:
                break
        current_idx += 1
        
    current_idx = end_idx
    while current_idx > start_idx:
        if has_end_punct(whisper_segments[current_idx]['text']):
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

# ==============================================================================
# Local Ollama Llama-3 Hook Selector (REPLACES Groq)
# ==============================================================================
def select_hooks_with_ollama(segments, rules, max_clips=3):
    """
    Passes the transcript to local Ollama Llama 3 to find engaging clips.
    Extracts the JSON payload with strict fallback parsing.
    """
    print("\n[LLM] Analyzing transcript against Campaign Rules using local Ollama (llama3)...")
    
    transcript_text = ""
    for idx, seg in enumerate(segments):
        transcript_text += f"[{seg['start']:.2f} - {seg['end']:.2f}] {seg['text']}\n"
        
    prompt = f"""
You are an expert video clip selector. Review the following video transcript and extract up to {max_clips} highly engaging clips of 50 to 90 seconds. 
They must comply with these campaign rules:
RULES: {rules}

Transcript:
{transcript_text}

Output ONLY valid JSON. No markdown backticks, no explanations. The output must be a list of dictionaries with this exact schema:
[
  {{
    "start_time": float,
    "end_time": float,
    "hook_reasoning": "string explaining why this is engaging",
    "cta_overlay_text": "short text under 20 chars",
    "requires_captions": boolean
  }}
]
"""
    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        })
        if response.status_code == 200:
            text = response.json().get('response', '').strip()
            
            # Robust fallback parsing mechanism for hallucinations
            if "```json" in text:
                match = re.search(r"```json\s*(.*?)\s*```", text, re.S)
                if match:
                    text = match.group(1)
            elif "```" in text:
                match = re.search(r"```\s*(.*?)\s*```", text, re.S)
                if match:
                    text = match.group(1)
            
            # Find JSON boundaries
            start_idx = text.find('[')
            end_idx = text.rfind(']')
            if start_idx != -1 and end_idx != -1:
                text = text[start_idx:end_idx+1]
                
            clips = json.loads(text)
            formatted_clips = []
            for c in clips:
                formatted_clips.append({
                    "start_time": c["start_time"],
                    "end_time": c["end_time"],
                    "duration": c["end_time"] - c["start_time"],
                    "score": 90.0,
                    "overlay_text": c.get("cta_overlay_text", ""),
                    "add_captions": c.get("requires_captions", False)
                })
            return formatted_clips
    except Exception as e:
        print(f"[LLM Error] Local Ollama parsing failed: {e}")
    return []

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
# Conditional Layout Compositing & Rendering (WhisperX timings)
# ==============================================================================

import cv2

def wrap_text_to_lines(text, font, font_scale, max_width, thickness):
    words = text.split(' ')
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        text_size = cv2.getTextSize(test_line, font, font_scale, thickness)[0]
        if text_size[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def add_cta_overlay(frame, text):
    if not text:
        return frame
    h, w, _ = frame.shape
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = w / 400.0
    thickness = max(2, int(font_scale * 3))
    
    text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
    text_x = (w - text_size[0]) // 2
    text_y = int(h * 0.15)
    
    cv2.putText(frame, text, (text_x+2, text_y+2), font, font_scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(frame, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return frame

def make_caption_frame_modifier(clip_start_time, local_transcript_segments):
    """
    Parses exact word-level WhisperX timings. Renders drop-shadowed, multi-line format 
    at the bottom 75% of the screen.
    """
    # Flatten all words into a timeline array
    all_words = []
    for seg in local_transcript_segments:
        if 'words' in seg:
            for w in seg['words']:
                all_words.append(w)
                
    def draw_captions_filter(get_frame, t):
        frame = np.copy(get_frame(t))
        current_global_time = clip_start_time + t
        h, w, _ = frame.shape
        
        # Find active word block (we'll show up to 5 words around the current time to build the phrase)
        active_words = []
        for w_obj in all_words:
            # We group words near the current time to form a sentence chunk
            if current_global_time - 1.5 <= w_obj['start'] and w_obj['start'] <= current_global_time + 1.5:
                active_words.append(w_obj['word'])
                
        # If no word exactly aligns, find the sentence segment
        if not active_words:
            for segment in local_transcript_segments:
                if segment['start'] <= current_global_time <= segment['end']:
                    active_words = [segment['text'].strip()]
                    break
                    
        active_text = " ".join(active_words)
        
        if not active_text:
            return frame
            
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = w / 550.0
        thickness = max(2, int(font_scale * 3.5))
        max_width = int(w * 0.85)
        
        lines = wrap_text_to_lines(active_text, font, font_scale, max_width, thickness)
        
        total_block_height = 0
        line_heights = []
        for line in lines:
            size = cv2.getTextSize(line, font, font_scale, thickness)[0]
            line_heights.append(size[1])
            total_block_height += size[1] + int(12 * font_scale)
            
        start_y = int(h * 0.75) - (total_block_height // 2)
        current_y = start_y
        
        for i, line in enumerate(lines):
            size = cv2.getTextSize(line, font, font_scale, thickness)[0]
            text_x = (w - size[0]) // 2
            
            cv2.putText(frame, line, (text_x + 3, current_y + 3), font, font_scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
            cv2.putText(frame, line, (text_x, current_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
            current_y += line_heights[i] + int(12 * font_scale)
            
        return frame
    return draw_captions_filter

def render_pro_clip(primary_clip, target_w=1080, target_h=1920):
    bg_clip = None
    orig_w, orig_h = primary_clip.size
    orig_ratio = orig_w / orig_h
    target_ratio = target_w / target_h

    if abs(orig_ratio - target_ratio) < 0.05:
        primary_scaled = primary_clip.resized(width=target_w)
    else:
        primary_scaled = primary_clip.resized(width=target_w)
    
    subclips = []
    t = 0
    zoom_in = False
    while t < primary_clip.duration:
        chunk_dur = random.uniform(3.0, 5.0)
        end_t = min(t + chunk_dur, primary_clip.duration)
        sub = primary_scaled.subclipped(t, end_t)
        
        if zoom_in and abs(orig_ratio - target_ratio) >= 0.05:
            w_new = int(target_w * 1.15)
            sub = sub.resized(width=w_new)
            x_center = w_new / 2
            y_center = sub.h / 2
            sub = sub.cropped(x1=x_center - target_w/2, y1=y_center - sub.h/2, x2=x_center + target_w/2, y2=y_center + sub.h/2)
            
        subclips.append(sub)
        t = end_t
        zoom_in = not zoom_in
        
    dynamic_primary = concatenate_videoclips(subclips)
    
    if abs(orig_ratio - target_ratio) < 0.05:
        return dynamic_primary

    dynamic_primary_pos = dynamic_primary.with_position(('center', 'center'))
    from moviepy import ColorClip
    bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=primary_clip.duration)

    final_composite = CompositeVideoClip([bg_clip, dynamic_primary_pos], size=(target_w, target_h))
    return final_composite

def run_clipping_pipeline(url="", input_video_path="", num_clips=3, model_size="large-v3", campaign_rules=None, enable_subtitles=False, layout="vertical", output_dir="clips", callback=None):
    os.makedirs(output_dir, exist_ok=True)
    target_w, target_h = 1080, 1920
    
    add_captions_flag = enable_subtitles
    
    for f in os.listdir(output_dir):
        if f.endswith('.mp4'):
            try:
                os.remove(os.path.join(output_dir, f))
            except Exception:
                pass
                
    download_dir = os.path.join(workspace_dir, "downloaded videos")
    os.makedirs(download_dir, exist_ok=True)
    for f in os.listdir(download_dir):
        if f.startswith('downloaded_') and f.endswith('.mp4'):
            try:
                os.remove(os.path.join(download_dir, f))
            except Exception:
                pass
                
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
    
    log("Transcribing", 30, f"Transcribing locally with GPU WhisperX ({model_size})...")
    try:
        segments = transcribe_audio_locally(audio_path, model_size="large-v3")
    except Exception as e:
        log("Transcribing", 40, f"Transcription failed: {e}. Cannot continue without timings.")
        return []
            
    hooks = []
    
    # Tier 1: YouTube player heatmap scores
    if url and ("youtube.com" in url or "youtu.be" in url):
        log("Tracking", 50, "Fetching YouTube Heatmap data...")
        heatmap_entries = get_youtube_heatmap(url)
        if heatmap_entries:
            log("Tracking", 53, "Heatmap retrieved. Syncing with whisper segments...")
            candidates = sync_heatmap_with_whisper(heatmap_entries, segments, min_duration=50, max_duration=90, add_captions=add_captions_flag)
            hooks = filter_overlapping_clips(candidates)
            
    # Tier 2: Local Ollama LLM Selector
    if not hooks and campaign_rules and campaign_rules.strip():
        log("Tracking", 50, "Invoking local Ollama Llama-3 hook selector...")
        candidates = select_hooks_with_ollama(segments, campaign_rules, max_clips=num_clips)
        # Ensure add_captions flag matches global if they didn't catch it
        for cand in candidates:
            cand["add_captions"] = cand.get("add_captions", False) or add_captions_flag
        hooks = filter_overlapping_clips(candidates)
        
    # Tier 3: NLP heuristics fallback
    if not hooks:
        log("Tracking", 50, "Invoking NLP heuristics hook selector...")
        candidates = detect_hooks_nlp(segments, min_duration=50, max_duration=90, add_captions=add_captions_flag)
        hooks = filter_overlapping_clips(candidates)
        
    if not hooks:
        clip_dur = 55.0
        hooks = [{'start_time': 0.0, 'end_time': clip_dur, 'duration': clip_dur, 'overlay_text': "", 'score': 1.0, 'add_captions': add_captions_flag}]
        
    generated_files = []
    total_hooks = min(len(hooks), num_clips)
    
    for idx, target in enumerate(hooks[:total_hooks]):
        out_filename = f"clip_{idx+1}.mp4"
        out_path = os.path.join(output_dir, out_filename)
        progress = int(60 + (idx / total_hooks) * 35)
        
        overlay = target.get('overlay_text', "")
        log("Rendering", progress, f"Rendering clip {idx+1}/{total_hooks} (length: {int(target['end_time'] - target['start_time'])}s) with overlay: '{overlay}'")
        
        local_raw_video = None
        try:
            if url:
                section_filename = os.path.join(download_dir, f"section_{idx+1}_{int(time.time())}.mp4")
                pad_start = max(0, target['start_time'] - 5)
                pad_end = target['end_time'] + 5
                
                log("Rendering", progress, f"Downloading video section for clip {idx+1}...")
                local_raw_video = download_youtube_video_section(url, pad_start, pad_end, section_filename)
                
                main_clip = VideoFileClip(local_raw_video)
                local_start = target['start_time'] - pad_start
                local_end = target['end_time'] - pad_start
                local_start = max(0, min(local_start, main_clip.duration))
                local_end = max(local_start + 1.0, min(local_end, main_clip.duration))
                sub_clip = main_clip.subclipped(local_start, local_end)
            else:
                local_raw_video = raw_video
                main_clip = VideoFileClip(local_raw_video)
                sub_clip = main_clip.subclipped(target['start_time'], target['end_time'])
            
            formatted_canvas = render_pro_clip(sub_clip, target_w=target_w, target_h=target_h)
            
            if overlay:
                formatted_canvas = formatted_canvas.transform(lambda get_frame, t: add_cta_overlay(np.copy(get_frame(t)), overlay))
                
            if target.get("add_captions", False):
                caption_callback = make_caption_frame_modifier(
                    clip_start_time=target['start_time'],
                    local_transcript_segments=segments
                )
                formatted_canvas = formatted_canvas.transform(caption_callback)
            
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
            generated_files.append(out_path)
            
            if url and os.path.exists(local_raw_video):
                try:
                    os.remove(local_raw_video)
                except:
                    pass
                    
        except Exception as e:
            log("Rendering", progress, f"Failed to render clip {idx+1}: {e}")
            
    # ==========================================================================
    # CRITICAL VRAM MEMORY MANAGEMENT
    # ==========================================================================
    log("Complete", 95, "Flushing PyTorch GPU VRAM Memory...")
    import torch
    gc.collect()
    torch.cuda.empty_cache()
    
    log("Complete", 100, f"Finished! Generated {len(generated_files)} clips.")
    return generated_files

if __name__ == "__main__":
    pass
