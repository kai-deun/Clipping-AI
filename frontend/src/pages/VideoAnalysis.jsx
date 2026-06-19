import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactPlayer from 'react-player';
import { Play, Sparkles, CheckCircle2, AlertCircle, Loader2, Video, Download, Crop } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const VideoAnalysis = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [taskData, setTaskData] = useState(null);
  const [error, setError] = useState('');
  const playerRef = useRef(null);
  
  // State for tracking generation tasks: { hookIndex: "gen_task_id" }
  const [generationTasks, setGenerationTasks] = useState({});
  // State for tracking generated clip URLs: { hookIndex: "clip_url" }
  const [generatedClips, setGeneratedClips] = useState({});

  const pollInterval = useRef(null);
  const genPollIntervals = useRef({});

  // 1. Poll the main Analysis Task
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/tasks/${id}`);
        if (!response.ok) throw new Error('Task not found');
        const data = await response.json();
        setTaskData(data);

        if (data.status === 'Completed' || data.status === 'Failed') {
          if (pollInterval.current) clearInterval(pollInterval.current);
        }
      } catch (err) {
        setError(err.message);
        if (pollInterval.current) clearInterval(pollInterval.current);
      }
    };

    fetchStatus();
    pollInterval.current = setInterval(fetchStatus, 2000);

    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, [id]);

  // 2. Poll individual Generation Tasks
  const pollGenerationTask = async (genTaskId, hookIndex) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/tasks/${genTaskId}`);
      if (!response.ok) return;
      const data = await response.json();
      
      if (data.status === 'Completed') {
        clearInterval(genPollIntervals.current[hookIndex]);
        setGeneratedClips(prev => ({ ...prev, [hookIndex]: `${API_BASE_URL}${data.clip_url}` }));
        setGenerationTasks(prev => {
          const next = { ...prev };
          delete next[hookIndex];
          return next;
        });
      } else if (data.status === 'Failed') {
        clearInterval(genPollIntervals.current[hookIndex]);
        setGenerationTasks(prev => {
          const next = { ...prev };
          delete next[hookIndex];
          return next;
        });
        alert(`Generation failed for clip ${hookIndex + 1}: ${data.logs.join(', ')}`);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleGenerateClip = async (hook, index) => {
    setGenerationTasks(prev => ({ ...prev, [index]: 'initializing' }));
    try {
      const response = await fetch(`${API_BASE_URL}/api/generate_clip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: id,
          hook: hook,
          enable_subtitles: true // Always true for now based on default behavior
        }),
      });

      if (!response.ok) throw new Error('Failed to start generation');
      const data = await response.json();
      
      setGenerationTasks(prev => ({ ...prev, [index]: data.gen_task_id }));
      
      genPollIntervals.current[index] = setInterval(() => {
        pollGenerationTask(data.gen_task_id, index);
      }, 2000);
      
    } catch (err) {
      alert(err.message);
      setGenerationTasks(prev => {
        const next = { ...prev };
        delete next[index];
        return next;
      });
    }
  };

  const handleStartAnalysis = async () => {
    try {
      const formData = new FormData();
      formData.append('task_id', id);
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        body: formData
      });
      if (!response.ok) throw new Error('Failed to start analysis');
      // Optimistically update UI so it shows Analyzing immediately
      setTaskData(prev => ({ ...prev, status: 'Running', stage: 'Initializing Analysis' }));
    } catch (err) {
      alert(err.message);
    }
  };

  const handleClearClips = async () => {
    try {
      await fetch(`${API_BASE_URL}/api/tasks/${id}/clear`, { method: 'POST' });
      setTaskData(prev => ({ ...prev, hooks: [], status: 'Transcribed', stage: 'Transcription Complete' }));
    } catch (err) {
      console.error(err);
    }
  };

  const formatTime = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const isTranscribing = taskData?.status === 'Running';
  const hasTranscript = !!taskData?.transcript?.length;
  const isAnalyzing = taskData?.status === 'Analyzing';
  const isAnalysisComplete = taskData?.status === 'Completed';

  const handlePreview = (startTime) => {
    if (playerRef.current) {
      if (taskData?.youtube_url) {
        playerRef.current.seekTo(startTime, 'seconds');
      } else {
        playerRef.current.currentTime = startTime;
        playerRef.current.play();
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex justify-center py-10 px-4 font-sans text-gray-900">
      <div className="w-full max-w-6xl flex flex-col lg:flex-row gap-6">
        
        {/* Left Column: Video & Suggestions */}
        <div className="flex-1 flex flex-col space-y-6">
          
          <button onClick={() => navigate('/')} className="text-sm font-medium text-gray-600 bg-white border border-gray-300 rounded-md px-4 py-2 hover:bg-gray-100 self-start">
            Back to Dashboard
          </button>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold mb-2">{taskData?.video_name || "clip.mp4"}</h2>
            <p className="text-xs text-gray-500 mb-4">Processed on {taskData?.timestamp ? new Date(taskData.timestamp * 1000).toLocaleString() : new Date().toLocaleString()}</p>
            
            <div className="w-full aspect-video bg-black rounded-lg overflow-hidden mb-6 flex items-center justify-center">
               {taskData?.youtube_url ? (
                 <ReactPlayer ref={playerRef} url={taskData.youtube_url} controls width="100%" height="100%" playing />
               ) : taskData?.video_url ? (
                 <video ref={playerRef} src={`${API_BASE_URL}${taskData.video_url}`} controls className="w-full h-full object-contain" />
               ) : (
                 <div className="text-white opacity-50 flex flex-col items-center">
                    <Video className="w-12 h-12 mb-2" />
                    <span>Video unavailable</span>
                 </div>
               )}
            </div>

            <div className="flex justify-between items-center mb-4 border-t pt-6">
              <div>
                <h3 className="text-xl font-bold">Clip Analysis & Generation</h3>
                {!isAnalysisComplete && !isAnalyzing && hasTranscript && (
                  <p className="text-sm text-gray-500 mt-1">Transcript ready! Click "Analyze for Clips" to get AI clip suggestions.</p>
                )}
                {!hasTranscript && isTranscribing && (
                  <p className="text-sm text-gray-500 mt-1">Waiting for transcription to finish before analysis can begin...</p>
                )}
                {isAnalyzing && (
                  <p className="text-sm text-blue-500 flex items-center mt-1">
                    <Loader2 className="w-4 h-4 mr-1 animate-spin" /> Analyzing hooks using LLM...
                  </p>
                )}
              </div>
              
              <div className="flex space-x-3">
                <button 
                  onClick={handleStartAnalysis}
                  disabled={!hasTranscript || isAnalyzing || isAnalysisComplete}
                  className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors ${
                    !hasTranscript || isAnalyzing ? 'bg-gray-100 text-gray-500 border border-gray-200 cursor-not-allowed' 
                    : isAnalysisComplete ? 'hidden' 
                    : 'bg-white border border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {isAnalyzing ? 'Analyzing...' : 'Analyze for Clips'}
                </button>
                <button 
                  onClick={handleClearClips}
                  disabled={!isAnalysisComplete}
                  className={`px-4 py-2 bg-red-50 text-red-600 border border-red-200 rounded-md text-sm font-semibold hover:bg-red-100 transition-colors ${!isAnalysisComplete ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  Clear Clips
                </button>
              </div>
            </div>

            {/* Clip Suggestions List */}
            {isAnalysisComplete && (
              <div className="space-y-4">
                {taskData.hooks.map((hook, idx) => {
                  const isGenerating = !!generationTasks[idx];
                  const generatedUrl = generatedClips[idx];
                  
                  return (
                    <div key={idx} className="border border-gray-200 rounded-lg p-5 flex flex-col bg-white">
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-bold text-gray-800">{hook.title || `Generated Clip ${idx + 1}`}</h4>
                          <div className="text-xs text-gray-500 mt-1 font-mono">
                            {formatTime(hook.start_time)} - {formatTime(hook.end_time)}
                            <br/>
                            Duration: {Math.round(hook.duration)}s
                          </div>
                          <button onClick={() => handlePreview(hook.start_time)} className="text-xs text-blue-600 mt-2 hover:underline">Preview in Player</button>
                        </div>
                        
                        {!generatedUrl ? (
                          <button 
                            onClick={() => handleGenerateClip(hook, idx)}
                            disabled={isGenerating}
                            className={`px-4 py-2 rounded-md text-sm font-semibold transition-colors ${
                              isGenerating 
                                ? 'bg-gray-100 text-gray-500 border border-gray-200 cursor-not-allowed'
                                : 'bg-gray-900 text-white hover:bg-gray-800'
                            }`}
                          >
                            {isGenerating ? 'Generating...' : 'Generate Clip'}
                          </button>
                        ) : (
                          <div className="flex space-x-2">
                             <button className="px-3 py-1.5 border border-gray-300 rounded-md text-xs font-semibold flex items-center hover:bg-gray-50">
                               <Crop className="w-3 h-3 mr-1" /> Reframe
                             </button>
                             <a href={generatedUrl} download className="px-3 py-1.5 bg-gray-900 text-white rounded-md text-xs font-semibold flex items-center hover:bg-gray-800">
                               <Download className="w-3 h-3 mr-1" /> Download
                             </a>
                          </div>
                        )}
                      </div>
                      
                      {generatedUrl && (
                        <div className="mt-4 pt-4 border-t border-gray-100">
                          <p className="text-xs font-semibold text-green-600 mb-2 flex items-center">
                            <CheckCircle2 className="w-3 h-3 mr-1" /> Generated Clip
                          </p>
                          <video src={generatedUrl} controls className="w-full max-w-sm rounded-md bg-black aspect-[9/16] object-contain mx-auto" />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Transcript */}
        <div className="w-full lg:w-80 bg-white rounded-xl shadow-sm border border-gray-200 p-6 flex flex-col h-[600px]">
          <h3 className="text-lg font-bold mb-4">Transcript</h3>
          <div className="flex-1 overflow-y-auto space-y-4 pr-2">
            {!hasTranscript ? (
              isTranscribing ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                  <p className="text-sm">Transcribing audio... this may take a few minutes depending on length.</p>
                </div>
              ) : (
                <p className="text-sm text-gray-400 italic text-center mt-10">Transcript will appear here.</p>
              )
            ) : (
              taskData.transcript.map((seg, idx) => (
                <div key={idx} className="text-sm">
                  <span className="font-semibold text-gray-700 block mb-1">Speaker 1: {formatTime(seg.start)} - {formatTime(seg.end)}</span>
                  <p className="text-gray-600 leading-relaxed">{seg.text.trim()}</p>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default VideoAnalysis;
