import { useState, useEffect, useRef } from 'react'
import './index.css'
const API_BASE = 'http://localhost:8000/api'

function App() {
  const [mode, setMode] = useState('link') // 'link' or 'upload'
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  
  const [numClips, setNumClips] = useState(3)
  const [whisperModel, setWhisperModel] = useState('base')
  const [campaignRules, setCampaignRules] = useState('')
  const [enableSubtitles, setEnableSubtitles] = useState(false)
  
  const [taskId, setTaskId] = useState(null)
  const [status, setStatus] = useState('Idle')
  const [stage, setStage] = useState('')
  const [progress, setProgress] = useState(0)
  const [logs, setLogs] = useState([])
  const [clips, setClips] = useState([])
  
  const logsEndRef = useRef(null)

  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs])

  useEffect(() => {
    let interval = null;
    if (taskId && (status === 'Running' || status === 'Idle')) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/tasks/${taskId}`)
          const data = await res.json()
          setStatus(data.status)
          setStage(data.stage)
          setProgress(data.progress)
          setLogs(data.logs || [])
          
          if (data.status === 'Completed' || data.status === 'Failed') {
            setClips(data.clips || [])
            clearInterval(interval)
          }
        } catch (e) {
          console.error("Failed to fetch task status", e)
        }
      }, 2000)
    }
    return () => clearInterval(interval)
  }, [taskId, status])

  const handleStart = async () => {
    if (mode === 'link' && !url) return alert("Please enter a YouTube URL")
    if (mode === 'upload' && !file) return alert("Please select a video file")
    
    setTaskId(null)
    setStatus('Running')
    setStage('Initializing')
    setProgress(0)
    setLogs([])
    setClips([])
    
    try {
      let res;
      if (mode === 'link') {
        res = await fetch(`${API_BASE}/clip`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            url,
            num_clips: numClips,
            whisper_model: whisperModel,
            campaign_rules: campaignRules,
            enable_subtitles: enableSubtitles
          })
        })
      } else {
        // Upload mode
        const formData = new FormData();
        formData.append("file", file);
        formData.append("num_clips", numClips);
        formData.append("whisper_model", whisperModel);
        formData.append("campaign_rules", campaignRules);
        formData.append("enable_subtitles", enableSubtitles);
        
        res = await fetch(`${API_BASE}/clip/upload`, {
          method: 'POST',
          body: formData
        })
      }
      
      const data = await res.json()
      if (data.task_id) {
        setTaskId(data.task_id)
      } else {
        throw new Error(data.detail || "Unknown error")
      }
    } catch (e) {
      console.error(e)
      setStatus('Failed')
      setLogs(prev => [...prev, "Failed to start task: " + e.message])
    }
  }

  return (
    <div className="app-container">
      <header className="header">
        <h1>AI Auto-Clipper</h1>
        <p>Turn any long-form YouTube video or local file into viral 9:16 vertical shorts instantly.</p>
      </header>

      <main>
        {status === 'Idle' || status === 'Failed' || (status === 'Completed' && clips.length === 0) ? (
          <div className="glass-panel">
            <h2>Create New Clips</h2>
            
            <div className="mode-toggle" style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem', marginBottom: '1rem' }}>
              <button 
                onClick={() => setMode('link')} 
                style={{ flex: 1, backgroundColor: mode === 'link' ? 'var(--primary)' : 'var(--bg-card)' }}
              >
                YouTube Link
              </button>
              <button 
                onClick={() => setMode('upload')} 
                style={{ flex: 1, backgroundColor: mode === 'upload' ? 'var(--primary)' : 'var(--bg-card)' }}
              >
                Upload File
              </button>
            </div>
            
            {mode === 'link' ? (
              <div className="form-group">
                <label>YouTube URL</label>
                <input 
                  type="text" 
                  placeholder="https://www.youtube.com/watch?v=..." 
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                />
              </div>
            ) : (
              <div className="form-group">
                <label>Select Video File</label>
                <input 
                  type="file" 
                  accept="video/*"
                  onChange={e => setFile(e.target.files[0])}
                  style={{ padding: '8px', cursor: 'pointer' }}
                />
              </div>
            )}
            
            <div className="config-grid">
              <div className="form-group">
                <label>Number of Clips</label>
                <input 
                  type="number" 
                  min="1" max="10" 
                  value={numClips}
                  onChange={e => setNumClips(parseInt(e.target.value))}
                />
              </div>
              <div className="form-group">
                <label>Whisper Model</label>
                <select value={whisperModel} onChange={e => setWhisperModel(e.target.value)}>
                  <option value="tiny">Tiny (Fastest, Less Accurate)</option>
                  <option value="base">Base (Balanced)</option>
                  <option value="small">Small (Slower, More Accurate)</option>
                  <option value="medium">Medium (Slowest, Most Accurate)</option>
                </select>
              </div>
            </div>
            
            <div className="form-group" style={{ marginTop: '1rem' }}>
              <label>Campaign Rules (LLM Instructions)</label>
              <textarea 
                placeholder="e.g. Add a promo overlay 'WHOP50' to the most exciting moments"
                value={campaignRules}
                onChange={e => setCampaignRules(e.target.value)}
                style={{ width: '100%', padding: '0.8rem', borderRadius: '8px', minHeight: '80px', backgroundColor: 'var(--bg-card)', color: 'white', border: '1px solid rgba(255,255,255,0.1)', fontFamily: 'inherit' }}
              />
            </div>
            
            <div className="form-group" style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input 
                type="checkbox" 
                id="addSubtitle" 
                checked={enableSubtitles}
                onChange={e => setEnableSubtitles(e.target.checked)}
                style={{ width: 'auto', cursor: 'pointer' }}
              />
              <label htmlFor="addSubtitle" style={{ cursor: 'pointer', margin: 0 }}>Add Subtitles (Captions)</label>
            </div>
            
            <button 
              onClick={handleStart} 
              style={{ marginTop: '2rem', width: '100%', fontSize: '1.1rem', padding: '1rem' }}
            >
              Generate AI Clips ✨
            </button>
          </div>
        ) : null}

        {(status === 'Running' || status === 'Completed' || status === 'Failed') && (
          <div className="glass-panel progress-container">
            <h2>
              {status === 'Completed' ? 'Processing Complete!' : 
               status === 'Failed' ? 'Processing Failed!' : 'Processing Video...'}
            </h2>
            {status === 'Running' && <p style={{ color: 'var(--primary)' }}>{stage} ({progress}%)</p>}
            {status === 'Failed' && <p style={{ color: 'red' }}>Error occurred during {stage}</p>}
            
            <div className="progress-bar-bg">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }}></div>
            </div>
            
            <div className="logs-container">
              {logs.map((log, i) => (
                <p key={i}>&gt; {log}</p>
              ))}
              <div ref={logsEndRef} />
            </div>
            
            {(status === 'Completed' || status === 'Failed') && (
              <button onClick={() => { setStatus('Idle'); setUrl(''); setFile(null); setTaskId(null); setClips([]); }} style={{ marginTop: '1rem' }}>
                {status === 'Failed' ? 'Try Again' : 'Create More Clips'}
              </button>
            )}
          </div>
        )}

        {clips.length > 0 && (
          <div style={{ marginTop: '3rem' }}>
            <h2>Generated Clips ({clips.length})</h2>
            <div className="clips-grid">
              {clips.map((clipPath, i) => {
                const filename = clipPath.split(/[\/\\]/).pop();
                const videoUrl = `${API_BASE}/clips/${filename}`;
                return (
                  <div key={i} className="clip-card glass-panel">
                    <div className="video-wrapper">
                      <video src={videoUrl} controls preload="metadata"></video>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontWeight: '500' }}>Clip #{i + 1}</span>
                      <a href={videoUrl} download={filename}>
                        <button style={{ padding: '0.4em 0.8em', fontSize: '0.9em' }}>Download</button>
                      </a>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
        )}
      </main>
    </div>
  )
}

export default App
