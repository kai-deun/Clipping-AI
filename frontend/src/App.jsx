import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/layout/Layout';
import UploadDashboard from './pages/UploadDashboard';
import VideoAnalysis from './pages/VideoAnalysis';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/upload" element={<UploadDashboard />} />
          <Route path="/analyze/:id" element={<VideoAnalysis />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
