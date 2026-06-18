import React from 'react';
import { useParams } from 'react-router-dom';
import { Play, Sparkles } from 'lucide-react';
import ReframeModal from '../components/modals/ReframeModal';
import CaptionGenerator from '../components/CaptionGenerator';

const VideoAnalysis = () => {
  const { id } = useParams();

  return (
    <div className="container mx-auto py-6 h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Analysis: {id}</h1>
        <div className="flex space-x-2">
          <button className="inline-flex items-center justify-center rounded-md text-sm font-medium border border-input bg-background hover:bg-accent hover:text-accent-foreground h-9 px-4 py-2">
            Settings
          </button>
          <button className="inline-flex items-center justify-center rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 h-9 px-4 py-2">
            <Sparkles className="w-4 h-4 mr-2" />
            Analyze for Clips
          </button>
        </div>
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0">
        {/* Left Panel: Video Player & Controls */}
        <div className="lg:col-span-2 flex flex-col space-y-6 overflow-y-auto pr-2">
          <div className="aspect-video bg-black rounded-lg border flex items-center justify-center relative overflow-hidden">
             <div className="text-muted-foreground flex flex-col items-center">
                <Play className="w-12 h-12 mb-2 opacity-50" />
                <span>Video Player Placeholder</span>
             </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <ReframeModal />
            <CaptionGenerator />
          </div>
        </div>

        {/* Right Panel: Interactive Transcript */}
        <div className="border rounded-lg bg-card flex flex-col overflow-hidden">
          <div className="border-b p-4 bg-muted/50 font-semibold flex justify-between items-center">
            <span>Transcript</span>
            <span className="text-xs font-normal text-muted-foreground px-2 py-1 bg-background rounded-full border">WhisperX</span>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
             <p className="text-muted-foreground text-sm italic text-center mt-10">Transcript generation pending...</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoAnalysis;
