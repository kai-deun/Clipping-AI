from moviepy import ColorClip
import traceback

try:
    c = ColorClip(size=(100, 100), color=(0,0,0), duration=1)
    
    def my_transform(gf, t):
        return gf(t)
        
    c2 = c.transform(my_transform)
    c2.get_frame(0.5)
    print("SUCCESS with (gf, t)")
except Exception as e:
    traceback.print_exc()

try:
    c = ColorClip(size=(100, 100), color=(0,0,0), duration=1)
    
    def my_transform2(t):
        return c.get_frame(t)
        
    c2 = c.transform(my_transform2)
    c2.get_frame(0.5)
    print("SUCCESS with (t)")
except Exception as e:
    traceback.print_exc()
