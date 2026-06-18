import re
import os

with open("d:/CODES/ClippingAI/free_clipper.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Add imports at the top
text = text.replace("import cv2", "import subprocess\\nfrom moviepy import CompositeAudioClip, concatenate_videoclips")

# 2. Extract out the exact block from def compose_vertical_layout to def run_clipping_pipeline
start_marker = "def compose_vertical_layout"
end_marker = "def run_clipping_pipeline"
start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx != -1 and end_idx != -1:
    pro_compositing = '''def get_words_for_clip(clip_start, clip_end, all_segments):
    words = []
    for seg in all_segments:
        if seg['start'] > clip_end:
            break
        if seg['end'] < clip_start:
            continue
        if 'words' in seg:
            for w in seg['words']:
                if w['start'] >= clip_start - 1.0 and w['end'] <= clip_end + 1.0:
                    words.append(w)
    return words

def generate_ass_file(words_list, output_path, video_width=1080, video_height=1920, overlay_text="", clip_duration=0.0):
    chunks = []
    current_chunk = []
    for w in words_list:
        current_chunk.append(w)
        if len(current_chunk) >= 3 or w['word'].endswith(('.', '!', '?')):
            chunks.append(current_chunk)
            current_chunk = []
    if current_chunk:
        chunks.append(current_chunk)

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,80,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,6,0,2,10,10,{int(video_height * 0.25)},1
"""
    if overlay_text:
        ass_header += f"Style: Overlay,Impact,70,&H00FFFFFF,&H000000FF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,6,0,8,10,10,{int(video_height * 0.15)},1\\n"

    ass_header += "\\n[Events]\\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\\n"

    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"
    
    events = []
    if words_list:
        clip_start_time = words_list[0]['start']
        for chunk in chunks:
            if not chunk: continue
            for i, active_w in enumerate(chunk):
                line_parts = []
                for j, w in enumerate(chunk):
                    w_text = w['word'].strip()
                    if j == i:
                        line_parts.append(f"{{\\\\c&H00FFFF&}}{w_text}{{\\\\c&HFFFFFF&}}")
                    else:
                        line_parts.append(w_text)
                
                sub_start = max(0.0, active_w['start'] - clip_start_time)
                sub_end = max(0.0, chunk[i+1]['start'] - clip_start_time) if i + 1 < len(chunk) else max(0.0, active_w['end'] - clip_start_time)
                if sub_end < sub_start: sub_end = sub_start + 0.1
                
                text = " ".join(line_parts)
                events.append(f"Dialogue: 0,{format_time(sub_start)},{format_time(sub_end)},Default,,0,0,0,,{text}")

    if overlay_text:
        events.append(f"Dialogue: 1,0:00:00.00,{format_time(clip_duration)},Overlay,,0,0,0,,{overlay_text}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_header)
        f.write("\\n".join(events))

def make_duck_function(clip_start_time, global_segments):
    import numpy as np
    intervals = [(max(0, s['start'] - clip_start_time - 0.2), s['end'] - clip_start_time + 0.5) for s in global_segments]
    def duck_vol(t):
        t_arr = np.atleast_1d(t)
        vols = np.full(t_arr.shape, 0.8)
        for start_t, end_t in intervals:
            mask = (t_arr >= start_t) & (t_arr <= end_t)
            vols[mask] = 0.15
        return vols[0] if np.isscalar(t) else vols
    return duck_vol

def render_pro_clip(primary_clip, bg_clip=None, target_w=1080, target_h=1920):
    import random
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
    if bg_clip is None:
        from moviepy import ColorClip
        bg_clip = ColorClip(size=(target_w, target_h), color=(0, 0, 0), duration=primary_clip.duration)
    else:
        bg_clip = bg_clip.resized(height=target_h).subclipped(0, primary_clip.duration)

    from moviepy import CompositeVideoClip
    final_composite = CompositeVideoClip([bg_clip, dynamic_primary_pos], size=(target_w, target_h))
    return final_composite

'''
    text = text[:start_idx] + pro_compositing + text[end_idx:]


# 3. Replace Rendering Loop in run_clipping_pipeline
import re

old_loop_regex = re.compile(r"# Slicing structural segment frames out of the parent video handler.*?generated_files\.append\(out_path\)", re.DOTALL)

new_loop_text = """# Slicing structural segment frames out of the parent video handler
            sub_clip = main_clip.subclipped(target['start_time'], target['end_time'])
            
            # Choose a background
            bg_dir_full = os.path.join(workspace_dir, "assets", "backgrounds")
            bg_clip = None
            if os.path.exists(bg_dir_full):
                bg_options = [os.path.join(bg_dir_full, f) for f in os.listdir(bg_dir_full) if f.endswith('.mp4')]
                if bg_options:
                    chosen_bg_path = random.choice(bg_options)
                    bg_clip = VideoFileClip(chosen_bg_path)
            
            # Render visual layer with punch-ins
            formatted_canvas = render_pro_clip(sub_clip, bg_clip)
            
            # Handle audio ducking if background audio exists
            final_audio = sub_clip.audio
            if bg_clip and bg_clip.audio:
                duck_func = make_duck_function(target['start_time'], segments)
                # Try handling volumex / with_volume across moviepy versions
                try:
                    ducked_bg = bg_clip.audio.subclipped(0, sub_clip.duration).with_volume(duck_func)
                except AttributeError:
                    ducked_bg = bg_clip.audio.subclipped(0, sub_clip.duration).volumex(duck_func)
                
                try:
                    main_audio = sub_clip.audio.with_volume(1.5)
                except AttributeError:
                    main_audio = sub_clip.audio.volumex(1.5)
                    
                final_audio = CompositeAudioClip([main_audio, ducked_bg])
                final_audio.duration = sub_clip.duration
                
            formatted_canvas.audio = final_audio
            
            # 1. Export intermediate temp file without subtitles
            temp_out = os.path.join(output_dir, f"temp_{idx+1}.mp4")
            formatted_canvas.write_videofile(
                temp_out,
                fps=sub_clip.fps if sub_clip.fps else 30,
                codec="libx264",
                audio_codec="aac",
                preset="ultrafast",
                logger=None
            )
            
            # 2. Generate .ASS Subtitles
            ass_path = os.path.join(output_dir, f"subs_{idx+1}.ass")
            if target.get("add_captions", False) or overlay:
                words = get_words_for_clip(target['start_time'], target['end_time'], segments) if target.get("add_captions", False) else []
                generate_ass_file(words, ass_path, overlay_text=overlay, clip_duration=sub_clip.duration)
                
                # 3. Burn subtitles using ffmpeg directly
                safe_ass = ass_path.replace('\\\\', '/').replace(':', '\\\\:')
                ffmpeg_cmd = [
                    ffmpeg_exe if os.path.exists(ffmpeg_exe) else "ffmpeg",
                    "-y", "-i", temp_out,
                    "-vf", f"subtitles='{safe_ass}'",
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "copy", out_path
                ]
                print(f"[Render Core] Burning subtitles via FFmpeg: {' '.join(ffmpeg_cmd)}")
                subprocess.run(ffmpeg_cmd, check=True)
                os.remove(temp_out)
                os.remove(ass_path)
            else:
                os.rename(temp_out, out_path)
                
            sub_clip.close()
            formatted_canvas.close()
            if bg_clip: bg_clip.close()
            generated_files.append(out_path)"""
            
text = old_loop_regex.sub(new_loop_text.replace('\\', '\\\\'), text) # Safe string replacement

with open("d:/CODES/ClippingAI/free_clipper.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Rewrite successful.")
