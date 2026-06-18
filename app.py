import os
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
import free_clipper


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
        "clips": []
    }
    
    # We will pass a custom logger to free_clipper to update the TASKS dict
    def progress_callback(stage, progress, msg):
        if task_id in TASKS:
            TASKS[task_id]["stage"] = stage
            TASKS[task_id]["progress"] = progress
            if msg:
                TASKS[task_id]["logs"].append(msg)
    
    def run_job():
        try:
            # We assume free_clipper has been modified or we adapt it to accept callbacks
            # For now, we will just call a function that we'll add to free_clipper
            clips = free_clipper.run_clipping_pipeline(
                url=request.url,
                model_size=request.whisper_model,
                campaign_rules=request.campaign_rules,
                enable_subtitles=request.enable_subtitles,
                callback=progress_callback
            )
            TASKS[task_id]["status"] = "Completed"
            TASKS[task_id]["stage"] = "Complete"
            TASKS[task_id]["clips"] = clips
            TASKS[task_id]["progress"] = 100
        except Exception as e:
            TASKS[task_id]["status"] = "Failed"
            TASKS[task_id]["logs"].append(str(e))
    
    # Start the job in a thread
    thread = threading.Thread(target=run_job)
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
    TASKS[task_id] = {
        "status": "Running",
        "stage": "Initializing",
        "progress": 0,
        "logs": [],
        "clips": []
    }
    
    # Save the uploaded file
    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    def progress_callback(stage, progress, msg):
        if task_id in TASKS:
            TASKS[task_id]["stage"] = stage
            TASKS[task_id]["progress"] = progress
            if msg:
                TASKS[task_id]["logs"].append(msg)
                
    def run_job():
        try:
            clips = free_clipper.run_clipping_pipeline(
                url="",
                input_video_path=file_path,
                model_size=whisper_model,
                campaign_rules=campaign_rules,
                enable_subtitles=enable_subtitles,
                callback=progress_callback
            )
            TASKS[task_id]["status"] = "Completed"
            TASKS[task_id]["stage"] = "Complete"
            TASKS[task_id]["clips"] = clips
            TASKS[task_id]["progress"] = 100
        except Exception as e:
            TASKS[task_id]["status"] = "Failed"
            TASKS[task_id]["logs"].append(str(e))
            
    thread = threading.Thread(target=run_job)
    thread.start()
    
    return {"task_id": task_id}



@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

# Mount the current directory or clips directory to serve files
# In this case we assume clips are saved in the root or a 'clips' folder. 
# We'll just serve from root for now, or create an endpoint to download a specific clip.

@app.get("/api/clips/{filename}")
async def get_clip(filename: str):
    filepath = os.path.join("clips", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
