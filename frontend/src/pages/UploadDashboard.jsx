import React from 'react';
import { UploadCloud, Link as LinkIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const UploadDashboard = () => {
  const navigate = useNavigate();

  return (
    <div className="container mx-auto py-10">
      <h1 className="text-3xl font-bold tracking-tight mb-8">Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
        {/* Upload Zone */}
        <div className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-12 flex flex-col items-center justify-center bg-muted/10 hover:bg-muted/20 transition-colors cursor-pointer">
          <div className="rounded-full bg-primary/10 p-4 mb-4">
            <UploadCloud className="w-8 h-8 text-primary" />
          </div>
          <h3 className="text-xl font-semibold mb-2">Upload Video</h3>
          <p className="text-sm text-muted-foreground text-center mb-6">Drag and drop your video file here, or click to browse.</p>
        </div>

        {/* YouTube Import Zone */}
        <div className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-12 flex flex-col items-center justify-center bg-muted/10 hover:bg-muted/20 transition-colors">
          <div className="rounded-full bg-primary/10 p-4 mb-4">
            <LinkIcon className="w-8 h-8 text-primary" />
          </div>
          <h3 className="text-xl font-semibold mb-2">Import from YouTube</h3>
          <p className="text-sm text-muted-foreground text-center mb-6">Paste a YouTube URL to automatically download and analyze.</p>
          <div className="w-full max-w-sm flex space-x-2">
            <input type="text" placeholder="https://youtube.com/watch?v=..." className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <button className="inline-flex items-center justify-center rounded-md text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2">Import</button>
          </div>
        </div>
      </div>

      <h2 className="text-2xl font-bold tracking-tight mb-6">Recent Videos</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        <div className="border rounded-lg overflow-hidden bg-card text-card-foreground shadow-sm cursor-pointer hover:shadow-md transition-all" onClick={() => navigate('/analyze/mock-id-1')}>
          <div className="aspect-video bg-muted relative">
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">Mock Thumbnail</div>
          </div>
          <div className="p-4">
            <h4 className="font-semibold truncate">Sample_Gaming_Clip.mp4</h4>
            <p className="text-xs text-muted-foreground mt-1">Processed 2 hours ago</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadDashboard;
