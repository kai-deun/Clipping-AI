from moviepy import ColorClip
import traceback

try:
    c = ColorClip(size=(100, 100), color=(0,0,0), duration=1)
    
    def draw_captions_filter(get_frame, t):
        return get_frame(t)
        
    c2 = c.transform(draw_captions_filter)
    c2.get_frame(0.5)
    print("SUCCESS")
except Exception as e:
    traceback.print_exc()
