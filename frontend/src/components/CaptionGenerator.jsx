import React, { useState } from 'react';
import { Type, Check } from 'lucide-react';

const CaptionGenerator = () => {
  const [captionsEnabled, setCaptionsEnabled] = useState(true);
  const [activeStyle, setActiveStyle] = useState('neon');

  const styles = [
    { id: 'bold', name: 'Bold Center' },
    { id: 'neon', name: 'Neon Pop' },
    { id: 'minimalist', name: 'Minimalist' }
  ];

  return (
    <div className="border rounded-lg bg-card text-card-foreground shadow-sm">
      <div className="p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold flex items-center">
            <Type className="w-5 h-5 mr-2 text-primary" />
            Captions
          </h3>
          <button 
            onClick={() => setCaptionsEnabled(!captionsEnabled)}
            className={`w-11 h-6 rounded-full transition-colors relative flex items-center ${captionsEnabled ? 'bg-primary' : 'bg-input'}`}
          >
            <span className={`w-5 h-5 bg-background rounded-full absolute transition-transform ${captionsEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
          </button>
        </div>

        <div className={`space-y-4 transition-opacity ${captionsEnabled ? 'opacity-100' : 'opacity-50 pointer-events-none'}`}>
          <div className="space-y-2">
            <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Style Preset</label>
            <div className="grid grid-cols-1 gap-2">
              {styles.map(style => (
                <button
                  key={style.id}
                  onClick={() => setActiveStyle(style.id)}
                  className={`flex items-center justify-between px-4 py-2 border rounded-md text-sm transition-colors ${activeStyle === style.id ? 'border-primary bg-primary/5 text-foreground' : 'text-muted-foreground hover:bg-muted/50'}`}
                >
                  {style.name}
                  {activeStyle === style.id && <Check className="w-4 h-4 text-primary" />}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CaptionGenerator;
