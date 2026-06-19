import os
import time
import uuid
import threading
import shutil
from fastapi import FastAPI, BackgroundTasks, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Import the clipper logic
from . import free_clipper


app = FastAPI(title="Video Clipper API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# We will store active tasks here
TASKS = {}

class ClipRequest(BaseModel):
    url: str
    num_clips: int = 3
    whisper_model: str = "base"
    campaign_rules: str = None
    enable_subtitles: bool = False
    
@app.post("/api/clip")
async def start_clipping(request: ClipRequest):
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "status": "Running",
        "stage": "Initializing",
        "progress": 0,
        "logs": [],
        "hooks": [],
        "video_name": "YouTube Import",
        "youtube_url": request.url,
        "timestamp": time.time()
    }
    
    def progress_callback(stage, progress, msg):
        if task_id in TASKS:
            TASKS[task_id]["stage"] = stage
            TASKS[task_id]["progress"] = progress
            if msg:
                TASKS[task_id]["logs"].append(msg)
    
    def run_transcribe_job():
        try:
            # 1. Download full video locally
            progress_callback("Downloading", 5, "Downloading full video from YouTube...")
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "uploads")
            os.makedirs(uploads_dir, exist_ok=True)
            output_filename = os.path.join(uploads_dir, f"youtube_{int(time.time())}.mp4")
            
            local_video_path = free_clipper.download_youtube_video(request.url, output_filename)
            
            # Mimic a local upload
            TASKS[task_id]["video_path"] = local_video_path
            TASKS[task_id]["video_url"] = f"/media/uploads/{os.path.basename(local_video_path)}"
            if "youtube_url" in TASKS[task_id]:
                del TASKS[task_id]["youtube_url"]
            
            # 2. Transcribe the local video
            segments = free_clipper.transcribe_video(
                url="",
                input_video_path=local_video_path,
                model_size=request.whisper_model,
                callback=progress_callback
            )
            TASKS[task_id]["status"] = "Transcribed"
            TASKS[task_id]["stage"] = "Transcription Complete"
            TASKS[task_id]["transcript"] = segments
            TASKS[task_id]["progress"] = 100
        except Exception as e:
            TASKS[task_id]["status"] = "Failed"
            TASKS[task_id]["logs"].append(str(e))
    
    thread = threading.Thread(target=run_transcribe_job)
    thread.start()
    
    return {"task_id": task_id}

@app.post("/api/clip/upload")
async def start_clipping_upload(
    file: UploadFile = File(...),
    num_clips: int = Form(3),
    whisper_model: str = Form("base"),
    campaign_rules: str = Form(None),
    enable_subtitles: bool = Form(False)
):
    task_id = str(uuid.uuid4())
    
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    file_path = os.path.join(uploads_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    TASKS[task_id] = {
        "status": "Running",
        "stage": "Initializing",
        "progress": 0,
        "logs": [],
        "hooks": [],
        "video_name": file.filename,
        "video_path": file_path,
        "video_url": f"/media/uploads/{file.filename}",
        "whisper_model": whisper_model,
        "campaign_rules": campaign_rules,
        "timestamp": time.time()
    }
    
    def progress_callback(stage, progress, msg):
        if task_id in TASKS:
            TASKS[task_id]["stage"] = stage
            TASKS[task_id]["progress"] = progress
            if msg:
                TASKS[task_id]["logs"].append(msg)
                
    def run_transcribe_job():
        try:
            segments = free_clipper.transcribe_video(
                url="",
                input_video_path=file_path,
                model_size=whisper_model,
                callback=progress_callback
            )
            TASKS[task_id]["status"] = "Transcribed"
            TASKS[task_id]["stage"] = "Transcription Complete"
            TASKS[task_id]["transcript"] = segments
            TASKS[task_id]["progress"] = 100
        except Exception as e:
            TASKS[task_id]["status"] = "Failed"
            TASKS[task_id]["logs"].append(str(e))
            
    thread = threading.Thread(target=run_transcribe_job)
    thread.start()
    
    return {"task_id": task_id, "video_path": file_path}

@app.post("/api/analyze")
async def start_analysis(request: BaseModel = None, task_id: str = Form(...)):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
        
    TASKS[task_id]["status"] = "Analyzing"
    TASKS[task_id]["stage"] = "Initializing Hook Analysis"
    TASKS[task_id]["progress"] = 0
    
    file_path = TASKS[task_id].get("video_path", "")
    campaign_rules = TASKS[task_id].get("campaign_rules", None)
    segments = TASKS[task_id].get("transcript", [])
    
    def progress_callback(stage, progress, msg):
        TASKS[task_id]["stage"] = stage
        TASKS[task_id]["progress"] = progress
        if msg:
            TASKS[task_id]["logs"].append(msg)
                
    def run_analyze_job():
        try:
            hooks = free_clipper.analyze_hooks(
                segments=segments,
                url="",
                campaign_rules=campaign_rules,
                callback=progress_callback
            )
            TASKS[task_id]["status"] = "Completed"
            TASKS[task_id]["stage"] = "Analysis Complete"
            TASKS[task_id]["hooks"] = hooks
            TASKS[task_id]["progress"] = 100
        except Exception as e:
            TASKS[task_id]["status"] = "Failed"
            TASKS[task_id]["logs"].append(str(e))
            
    thread = threading.Thread(target=run_analyze_job)
    thread.start()
    
    return {"status": "started"}

@app.get("/api/videos")
async def get_recent_videos():
    videos = []
    for tid, data in TASKS.items():
        if "video_name" in data:
            videos.append({
                "task_id": tid,
                "name": data["video_name"],
                "status": data["status"],
                "timestamp": data.get("timestamp", 0)
            })
    videos.sort(key=lambda x: x["timestamp"], reverse=True)
    return videos

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@app.post("/api/tasks/{task_id}/clear")
async def clear_task_hooks(task_id: str):
    if task_id in TASKS:
        TASKS[task_id]["hooks"] = []
        TASKS[task_id]["status"] = "Transcribed"
        TASKS[task_id]["stage"] = "Transcription Complete"
    return {"status": "cleared"}

class GenerateClipRequest(BaseModel):
    task_id: str
    hook: dict
    video_path: str = ""
    url: str = ""
    enable_subtitles: bool = False

@app.post("/api/generate_clip")
async def generate_clip(request: GenerateClipRequest):
    if request.task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task_data = TASKS[request.task_id]
    segments = task_data.get("transcript", [])
    
    # We create a sub-task for generating the clip to track progress
    gen_task_id = str(uuid.uuid4())
    TASKS[gen_task_id] = {
        "status": "Running",
        "stage": "Initializing",
        "progress": 0,
        "logs": [],
        "clip_url": None
    }
    
    def progress_callback(stage, progress, msg):
        TASKS[gen_task_id]["stage"] = stage
        TASKS[gen_task_id]["progress"] = progress
        if msg:
            TASKS[gen_task_id]["logs"].append(msg)
            
    def run_generate_job():
        try:
            out_filename = f"clip_{gen_task_id[:8]}.mp4"
            out_path = free_clipper.generate_single_clip(
                target_hook=request.hook,
                segments=segments,
                url=task_data.get("youtube_url", ""),
                input_video_path=task_data.get("video_path", ""),
                output_filename=out_filename,
                enable_subtitles=request.enable_subtitles,
                callback=progress_callback
            )
            if out_path:
                TASKS[gen_task_id]["status"] = "Completed"
                TASKS[gen_task_id]["stage"] = "Complete"
                TASKS[gen_task_id]["progress"] = 100
                TASKS[gen_task_id]["clip_url"] = f"/media/clips/{out_filename}"
            else:
                TASKS[gen_task_id]["status"] = "Failed"
                TASKS[gen_task_id]["logs"].append("Rendering returned None")
        except Exception as e:
            TASKS[gen_task_id]["status"] = "Failed"
            TASKS[gen_task_id]["logs"].append(str(e))
            
    thread = threading.Thread(target=run_generate_job)
    thread.start()
    
    return {"gen_task_id": gen_task_id}

# Mount the current directory or clips directory to serve files
# In this case we assume clips are saved in the root or a 'clips' folder. 
# We'll just serve from root for now, or create an endpoint to download a specific clip.

@app.get("/api/clips/{filename}")
async def get_clip(filename: str):
    clips_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media", "clips")
    filepath = os.path.join(clips_dir, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)

# Mount the entire media directory to serve uploaded and generated videos
media_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "media")
if os.path.exists(media_dir):
    app.mount("/media", StaticFiles(directory=media_dir), name="media")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
