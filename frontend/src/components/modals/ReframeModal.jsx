import React, { useState } from 'react';
import { Crop, Maximize, Move } from 'lucide-react';

const ReframeModal = () => {
  const [cropMode, setCropMode] = useState('static'); // 'static', 'dynamic', 'split'

  return (
    <div className="border rounded-lg bg-card text-card-foreground shadow-sm">
      <div className="p-6">
        <h3 className="text-lg font-semibold flex items-center mb-4">
          <Crop className="w-5 h-5 mr-2 text-primary" />
          Reframe & Crop
        </h3>
        
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-2">
             <button 
                onClick={() => setCropMode('static')}
                className={`flex flex-col items-center justify-center p-3 border rounded-md transition-colors ${cropMode === 'static' ? 'bg-primary/10 border-primary text-primary' : 'hover:bg-muted'}`}
             >
                <Maximize className="w-5 h-5 mb-1" />
                <span className="text-xs font-medium">Static Center</span>
             </button>
             <button 
                onClick={() => setCropMode('dynamic')}
                className={`flex flex-col items-center justify-center p-3 border rounded-md transition-colors ${cropMode === 'dynamic' ? 'bg-primary/10 border-primary text-primary' : 'hover:bg-muted'}`}
             >
                <Move className="w-5 h-5 mb-1" />
                <span className="text-xs font-medium">AI Tracking</span>
             </button>
             <button 
                onClick={() => setCropMode('split')}
                className={`flex flex-col items-center justify-center p-3 border rounded-md transition-colors ${cropMode === 'split' ? 'bg-primary/10 border-primary text-primary' : 'hover:bg-muted'}`}
             >
                <div className="w-5 h-5 border-2 rounded-sm mb-1 flex flex-col"><div className="flex-1 border-b"></div><div className="flex-1"></div></div>
                <span className="text-xs font-medium">Split Screen</span>
             </button>
          </div>

          <div className="bg-muted/30 p-4 rounded-md border text-sm text-muted-foreground">
             {cropMode === 'static' && "A standard 9:16 vertical crop locked to the center of the video."}
             {cropMode === 'dynamic' && "AI will use MediaPipe/YOLO to track the active subject and pan the camera dynamically."}
             {cropMode === 'split' && "Select two distinct regions (e.g., facecam and gameplay) to stack vertically."}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReframeModal;
