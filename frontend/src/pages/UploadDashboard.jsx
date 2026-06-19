import React, { useState, useRef } from 'react';
import { UploadCloud, Link as LinkIcon, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = 'http://localhost:8000';

const UploadDashboard = () => {
  const navigate = useNavigate();
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [recentVideos, setRecentVideos] = useState([]);
  
  const fileInputRef = useRef(null);

  const fetchRecentVideos = () => {
    fetch(`${API_BASE_URL}/api/videos`)
      .then(res => res.json())
      .then(data => setRecentVideos(data))
      .catch(err => console.error("Failed to load recent videos", err));
  };

  React.useEffect(() => {
    fetchRecentVideos();
  }, []);

  const handleYoutubeImport = async () => {
    if (!youtubeUrl.trim()) {
      setErrorMsg("Please enter a valid YouTube URL.");
      return;
    }
    
    setIsImporting(true);
    setErrorMsg('');
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/clip`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: youtubeUrl,
          num_clips: 3,
          whisper_model: "base",
          campaign_rules: "",
          enable_subtitles: false
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.task_id) {
        setYoutubeUrl('');
        fetchRecentVideos();
      } else {
        throw new Error("No task ID returned from server.");
      }
    } catch (error) {
      console.error(error);
      setErrorMsg(`Import failed: ${error.message}`);
    } finally {
      setIsImporting(false);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file) return;
    
    setIsUploading(true);
    setErrorMsg('');
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("num_clips", 3);
    formData.append("whisper_model", "base");
    formData.append("campaign_rules", "");
    formData.append("enable_subtitles", false);

    try {
      const response = await fetch(`${API_BASE_URL}/api/clip/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      if (data.task_id) {
        if (fileInputRef.current) fileInputRef.current.value = '';
        fetchRecentVideos();
      } else {
        throw new Error("No task ID returned from server.");
      }
    } catch (error) {
      console.error(error);
      setErrorMsg(`Upload failed: ${error.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const onDragOver = (e) => {
    e.preventDefault();
  };

  const onDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
      e.dataTransfer.clearData();
    }
  };

  const onFileSelect = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  };

  return (
    <div className="container mx-auto py-10 px-4">
      <h1 className="text-3xl font-bold tracking-tight mb-8">Dashboard</h1>
      
      {errorMsg && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
          <span className="block sm:inline">{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
        {/* Upload Zone */}
        <div 
          onClick={() => !isUploading && fileInputRef.current.click()}
          onDragOver={onDragOver}
          onDrop={onDrop}
          className={`border-2 border-dashed border-muted-foreground/25 rounded-lg p-12 flex flex-col items-center justify-center bg-muted/10 hover:bg-muted/20 transition-colors ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={onFileSelect} 
            className="hidden" 
            accept="video/*" 
          />
          <div className="rounded-full bg-primary/10 p-4 mb-4">
            {isUploading ? <Loader2 className="w-8 h-8 text-primary animate-spin" /> : <UploadCloud className="w-8 h-8 text-primary" />}
          </div>
          <h3 className="text-xl font-semibold mb-2">{isUploading ? 'Uploading Video...' : 'Upload Video'}</h3>
          <p className="text-sm text-muted-foreground text-center mb-6">
            {isUploading ? 'Please wait while we transfer your file.' : 'Drag and drop your video file here, or click to browse.'}
          </p>
        </div>

        {/* YouTube Import Zone */}
        <div className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-12 flex flex-col items-center justify-center bg-muted/10 hover:bg-muted/20 transition-colors">
          <div className="rounded-full bg-primary/10 p-4 mb-4">
            {isImporting ? <Loader2 className="w-8 h-8 text-primary animate-spin" /> : <LinkIcon className="w-8 h-8 text-primary" />}
          </div>
          <h3 className="text-xl font-semibold mb-2">{isImporting ? 'Importing...' : 'Import from YouTube'}</h3>
          <p className="text-sm text-muted-foreground text-center mb-6">Paste a YouTube URL to automatically download and analyze.</p>
          <div className="w-full max-w-sm flex space-x-2">
            <input 
              type="text" 
              placeholder="https://youtube.com/watch?v=..." 
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" 
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.target.value)}
              disabled={isImporting}
              onKeyDown={(e) => e.key === 'Enter' && handleYoutubeImport()}
            />
            <button 
              onClick={handleYoutubeImport}
              disabled={isImporting}
              className="inline-flex items-center justify-center rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2 disabled:opacity-50"
            >
              {isImporting ? 'Processing' : 'Import'}
            </button>
          </div>
        </div>
      </div>

      <h2 className="text-2xl font-bold tracking-tight mb-6">Recent Videos</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {recentVideos.length === 0 && (
          <p className="text-muted-foreground col-span-full">No videos processed yet. Upload one above!</p>
        )}
        {recentVideos.map((video) => (
          <div key={video.task_id} className="border rounded-lg overflow-hidden bg-card text-card-foreground shadow-sm cursor-pointer hover:shadow-md transition-all" onClick={() => navigate(`/analyze/${video.task_id}`)}>
            <div className="aspect-video bg-muted relative flex flex-col items-center justify-center">
              <UploadCloud className="w-8 h-8 text-muted-foreground mb-2 opacity-50" />
            </div>
            <div className="p-4">
              <h4 className="font-semibold truncate" title={video.name}>{video.name}</h4>
              <p className="text-xs text-muted-foreground mt-1">Status: {video.status}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UploadDashboard;
