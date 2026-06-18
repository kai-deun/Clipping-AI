import { create } from 'zustand';

const useJobStore = create((set, get) => ({
  activeJobId: null,
  jobStatus: null, // 'pending', 'processing', 'completed', 'failed'
  progress: 0,
  error: null,
  pollIntervalId: null,

  setActiveJob: (jobId) => {
    set({ activeJobId: jobId, jobStatus: 'pending', progress: 0, error: null });
    get().startPolling();
  },

  startPolling: () => {
    const existingInterval = get().pollIntervalId;
    if (existingInterval) clearInterval(existingInterval);

    const intervalId = setInterval(async () => {
      const { activeJobId } = get();
      if (!activeJobId) {
        clearInterval(intervalId);
        return;
      }

      try {
        const response = await fetch(`http://localhost:8000/api/jobs/${activeJobId}`);
        if (!response.ok) throw new Error('Failed to fetch job status');
        
        const data = await response.json();
        set({ jobStatus: data.status, progress: data.progress });

        if (data.status === 'completed' || data.status === 'failed') {
          if (data.status === 'failed') set({ error: data.error || 'Job failed' });
          get().stopPolling();
        }
      } catch (err) {
        set({ error: err.message, jobStatus: 'failed' });
        get().stopPolling();
      }
    }, 2000);

    set({ pollIntervalId: intervalId });
  },

  stopPolling: () => {
    const { pollIntervalId } = get();
    if (pollIntervalId) {
      clearInterval(pollIntervalId);
      set({ pollIntervalId: null });
    }
  },
}));

export default useJobStore;
