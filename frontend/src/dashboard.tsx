import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Camera, Shield, Activity, AlertTriangle, Download, Eye, EyeOff,
  Video, Upload, Radio, X, CheckCircle, Loader2, FileVideo, Bell, BellOff, 
  BarChart3, Play, RefreshCw
} from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/api/logs';

interface Detection {
  id: string;
  name: string;
  timestamp: string;
  confidence: number;
  risk_level: string;
  face_crop: string;
  person_id?: string;
  notes?: string;
}

interface Stats {
  total_detections: number;
  high_risk: number;
  medium_risk: number;
  low_risk: number;
  watchlist_count: number;
}

interface VideoProgress {
  source_type: string;
  current_frame: number;
  total_frames: number;
  progress_percentage: number;
  processing_complete: boolean;
}

interface SessionStats {
  total_faces: number;
  unique_individuals: number;
  high_risk_count: number;
  medium_risk_count: number;
  low_risk_count: number;
  unknown_count: number;
  start_time: string;
  end_time?: string;
}

interface Alert {
  id: string;
  severity: 'high' | 'medium' | 'low';
  detection: Detection;
  timestamp: string;
}

// StatCard Component (used inside Dashboard)
interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color?: string;
}

function StatCard({ label, value, icon, color = 'text-blue-500' }: StatCardProps) {
  return (
    <motion.div 
      whileHover={{ scale: 1.02, y: -2 }}
      className="bg-slate-900/80 backdrop-blur-sm rounded-lg border border-blue-500/20 hover:border-blue-500/50 p-4 transition-all"
    >
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-gray-400 mb-1">{label}</div>
          <div className={`text-2xl font-bold ${color}`}>{value}</div>
        </div>
        <div className={color}>
          {icon}
        </div>
      </div>
    </motion.div>
  );
}

export default function AegisVisionDashboard() {
  const [detections, setDetections] = useState<Detection[]>([]);
  const [stats, setStats] = useState<Stats>({ 
    total_detections: 0, high_risk: 0, medium_risk: 0, low_risk: 0, watchlist_count: 0 
  });
  const [enhancementEnabled, setEnhancementEnabled] = useState(true);
  const [scanLine, setScanLine] = useState(0);
  const [showWatchlistModal, setShowWatchlistModal] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  
  // New state for multi-source video
  const [videoSource, setVideoSource] = useState<{ type: 'webcam' | 'file' | 'rtsp'; path?: string }>({ type: 'webcam' });
  const [videoProgress, setVideoProgress] = useState<VideoProgress | null>(null);
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null);
  const [showSessionStats, setShowSessionStats] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<string | null>(null);
  
  // Alert system
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [soundEnabled, setSoundEnabled] = useState(true);
  
  // Video source selector
  const [activeTab, setActiveTab] = useState<'webcam' | 'file' | 'rtsp'>('webcam');
  const [isUploading, setIsUploading] = useState(false);
  const [rtspUrl, setRtspUrl] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const progressIntervalRef = useRef<number | null>(null);

  // WebSocket connection for real-time detections
  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => console.log('🔷 WebSocket connected');
    
    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'initial') {
        setDetections(message.data.slice(-20).reverse());
      } else if (message.type === 'detection') {
        setDetections(prev => [...message.data.reverse(), ...prev].slice(0, 20));
      } else if (message.type === 'alert') {
        // Handle high-risk alerts
        handleNewAlert({
          id: Date.now().toString(),
          severity: message.severity,
          detection: message.data[0],
          timestamp: new Date().toISOString()
        });
      }
    };

    ws.onerror = (error) => console.error('WebSocket error:', error);
    ws.onclose = () => console.log('🔷 WebSocket disconnected');

    return () => ws.close();
  }, []);

  // Fetch stats periodically
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/stats`);
        const data = await res.json();
        setStats(data);
      } catch (err) {
        console.error('Stats fetch error:', err);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 3000);
    return () => clearInterval(interval);
  }, []);

  // Scanning animation
  useEffect(() => {
    const interval = setInterval(() => {
      setScanLine(prev => (prev + 2) % 100);
    }, 50);
    return () => clearInterval(interval);
  }, []);

  // Progress polling for video files
  useEffect(() => {
    if (videoSource.type === 'file' && !videoProgress?.processing_complete) {
      startProgressPolling();
    }
    
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, [videoSource.type, videoProgress?.processing_complete]);

  const startProgressPolling = () => {
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }
    
    progressIntervalRef.current = window.setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/video/progress`);
        const data = await res.json();
        setVideoProgress(data);
        
        if (data.processing_complete) {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
          }
          await fetchSessionStats();
          setShowSessionStats(true);
        }
      } catch (err) {
        console.error('Progress fetch error:', err);
      }
    }, 500);
  };

  const fetchSessionStats = async () => {
    try {
      const res = await fetch(`${API_BASE}/video/session-stats`);
      const data = await res.json();
      setSessionStats(data);
    } catch (err) {
      console.error('Session stats fetch error:', err);
    }
  };

  const handleNewAlert = (alert: Alert) => {
    setAlerts(prev => [alert, ...prev].slice(0, 10));
    
    if (soundEnabled) {
      const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBjV+zPDTjjwJE2q46+qeUAoMVqvl6bNcHAU2jdXvyHcoAw==');
      audio.play().catch(() => {});
    }
  };

  const handleVideoUpload = async (file: File) => {
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await fetch(`${API_BASE}/video/upload`, {
        method: 'POST',
        body: formData
      });
      
      const data = await res.json();
      if (data.success) {
        setUploadedFile(data.filename);
        await switchVideoSource('file', data.filename);
      } else {
        alert(`Upload failed: ${data.error}`);
      }
    } catch (err) {
      alert(`Upload error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  const switchVideoSource = async (sourceType: 'webcam' | 'file' | 'rtsp', sourcePath?: string) => {
    const formData = new FormData();
    formData.append('source_type', sourceType);
    if (sourcePath) formData.append('source_path', sourcePath);
    formData.append('camera_id', 'CAM-001');
    formData.append('location', 'Monitoring Station');
    
    try {
      const res = await fetch(`${API_BASE}/video/set-source`, {
        method: 'POST',
        body: formData
      });
      
      const data = await res.json();
      if (data.success) {
        setVideoSource({ type: sourceType, path: sourcePath });
        setDetections([]);
        setVideoProgress(null);
        setShowSessionStats(false);
      } else {
        alert(`Source switch failed: ${data.error}`);
      }
    } catch (err) {
      alert(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      handleVideoUpload(file);
    } else {
      alert('Please upload a video file');
    }
  };

  const exportSessionReport = async () => {
    if (!sessionStats) return;
    
    const report = {
      session_summary: sessionStats,
      video_source: videoSource,
      export_time: new Date().toISOString()
    };
    
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `session-report-${Date.now()}.json`;
    a.click();
  };

  const formatDuration = (startTime: string, endTime?: string) => {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const diff = end.getTime() - start.getTime();
    
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const toggleEnhancement = async () => {
    try {
      const res = await fetch(`${API_BASE}/toggle-enhancement`, { method: 'POST' });
      const data = await res.json();
      setEnhancementEnabled(data.enabled);
    } catch (err) {
      console.error('Toggle error:', err);
    }
  };

  const exportLog = async () => {
    try {
      const res = await fetch(`${API_BASE}/export-log`);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `aegis-log-${Date.now()}.json`;
      a.click();
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  const handleAddToWatchlist = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    
    try {
      setUploadStatus('Uploading...');
      const res = await fetch(`${API_BASE}/watchlist/add`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      
      if (data.success) {
        setUploadStatus(`✅ Added: ${data.name}`);
        setTimeout(() => {
          setShowWatchlistModal(false);
          setUploadStatus('');
        }, 2000);
      } else {
        setUploadStatus(`❌ Error: ${data.error}`);
      }
    } catch (err) {
      setUploadStatus(`❌ Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'HIGH': return 'text-red-500 bg-red-500/10 border-red-500';
      case 'MEDIUM': return 'text-orange-500 bg-orange-500/10 border-orange-500';
      case 'LOW': return 'text-green-500 bg-green-500/10 border-green-500';
      default: return 'text-gray-500 bg-gray-500/10 border-gray-500';
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white font-mono">
      {/* Alert System */}
      <div className="fixed top-20 right-6 z-50 space-y-2 max-w-md">
        <AnimatePresence>
          {alerts.map((alert) => (
            <motion.div
              key={alert.id}
              initial={{ x: 400, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 400, opacity: 0 }}
              className={`bg-slate-900 border-2 ${getRiskColor(alert.detection.risk_level)} rounded-lg p-4 shadow-2xl`}
            >
              <div className="flex items-start justify-between gap-3">
                <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
                <div className="flex-1">
                  <div className="font-bold text-sm">🚨 {alert.severity.toUpperCase()} RISK</div>
                  <div className="text-sm mt-1">{alert.detection.name}</div>
                  <div className="text-xs text-gray-400">
                    {(alert.detection.confidence * 100).toFixed(0)}% confident
                  </div>
                </div>
                <button
                  onClick={() => setAlerts(prev => prev.filter(a => a.id !== alert.id))}
                  className="text-gray-400 hover:text-white transition-colors"
                  title="Dismiss alert"
                  aria-label="Dismiss alert"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {/* Header */}
      <header className="border-b border-blue-500/30 bg-slate-900/50 backdrop-blur-sm sticky top-0 z-40">
        <div className="w-full px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-2xl font-bold tracking-wider">AEGIS-VISION</h1>
              <p className="text-xs text-blue-400">Pakistan AI Challenge 2026 - Safe City Surveillance</p>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
            <button
              onClick={() => setSoundEnabled(!soundEnabled)}
              className="text-gray-400 hover:text-white transition-colors"
              title={soundEnabled ? 'Mute alerts' : 'Enable sound'}
              aria-label={soundEnabled ? 'Mute alerts' : 'Enable sound'}
            >
              {soundEnabled ? <Bell className="w-5 h-5" /> : <BellOff className="w-5 h-5" />}
            </button>
            <div className="flex items-center gap-2 text-green-400">
              <Activity className="w-5 h-5 animate-pulse" />
              <span className="text-sm font-semibold">ACTIVE</span>
            </div>
            <div className="text-sm text-gray-400 font-mono">
              {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </header>

      {/* Stats Dashboard */}
      <div className="border-b border-blue-500/20 bg-slate-900/30">
        <div className="w-full px-6 py-4 grid grid-cols-4 gap-4">
          <StatCard label="Detections" value={stats.total_detections} icon={<Camera />} />
          <StatCard label="High Risk" value={stats.high_risk} icon={<AlertTriangle />} color="text-red-500" />
          <StatCard label="Watchlist" value={stats.watchlist_count} icon={<Shield />} color="text-blue-500" />
          <StatCard label="FPS" value="30" icon={<Activity />} color="text-green-500" />
        </div>
      </div>

      <div className="w-full px-6 py-6">
        {/* Video Source Selector */}
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 bg-slate-900 rounded-lg border border-blue-500/30 p-4"
        >
          <div className="flex items-center gap-2 mb-4">
            <Video className="w-5 h-5 text-blue-400" />
            <h3 className="text-sm font-semibold">VIDEO SOURCE</h3>
          </div>
          
          <div className="flex gap-2 mb-4">
            {(['webcam', 'file', 'rtsp'] as const).map((tab) => (
              <motion.button
                key={tab}
                onClick={() => setActiveTab(tab)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`flex items-center gap-2 px-4 py-2 rounded transition-all ${
                  activeTab === tab ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/50' : 'bg-slate-800 text-gray-400 hover:bg-slate-700'
                }`}
                title={`Switch to ${tab} source`}
                aria-label={`Switch to ${tab} source`}
              >
                {tab === 'webcam' && <Video className="w-4 h-4" />}
                {tab === 'file' && <Upload className="w-4 h-4" />}
                {tab === 'rtsp' && <Radio className="w-4 h-4" />}
                <span className="text-sm capitalize font-semibold">{tab}</span>
              </motion.button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="min-h-30"
            >
              {activeTab === 'webcam' && (
                <div className="flex flex-col items-center justify-center py-6">
                  <Camera className="w-12 h-12 text-blue-400 mb-3" />
                  <button
                    onClick={() => switchVideoSource('webcam')}
                    disabled={videoSource.type === 'webcam'}
                    className={`px-6 py-2 rounded font-semibold transition-all ${
                      videoSource.type === 'webcam'
                        ? 'bg-green-500/20 text-green-400 border-2 border-green-500'
                        : 'bg-blue-500 hover:bg-blue-600 text-white'
                    }`}
                  >
                    {videoSource.type === 'webcam' ? '✓ Webcam Active' : 'Start Webcam'}
                  </button>
                </div>
              )}

              {activeTab === 'file' && (
                <div>
                  <div
                    onDrop={handleFileDrop}
                    onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                    onDragLeave={() => setIsDragging(false)}
                    className={`border-2 border-dashed rounded-lg p-8 text-center transition-all ${
                      isDragging ? 'border-blue-500 bg-blue-500/10 scale-105' : 'border-slate-700 hover:border-blue-500/50'
                    }`}
                  >
                    <Upload className="w-12 h-12 text-blue-400 mx-auto mb-3" />
                    <p className="text-sm text-gray-300 mb-2 font-semibold">Drag video or click to browse</p>
                    <p className="text-xs text-gray-500 mb-4">MP4, AVI, MOV, MKV, FLV, WMV</p>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="video/*"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleVideoUpload(file);
                      }}
                      className="hidden"
                      aria-label="Upload video file"
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isUploading}
                      className="px-6 py-2 bg-blue-500 hover:bg-blue-600 rounded text-sm font-semibold disabled:opacity-50 transition-all"
                      title="Browse video files"
                      aria-label="Browse video files"
                    >
                      {isUploading ? (
                        <span className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Uploading...
                        </span>
                      ) : 'Browse Files'}
                    </button>
                  </div>
                  {uploadedFile && (
                    <motion.div 
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="mt-3 text-sm text-green-400 flex items-center gap-2"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span className="font-semibold">{uploadedFile}</span>
                    </motion.div>
                  )}
                </div>
              )}

              {activeTab === 'rtsp' && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2 font-semibold">RTSP URL</label>
                    <input
                      type="text"
                      value={rtspUrl}
                      onChange={(e) => setRtspUrl(e.target.value)}
                      placeholder="rtsp://username:password@ip:port/path"
                      className="w-full bg-slate-800 border border-blue-500/30 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500 transition-colors"
                    />
                  </div>
                  <button
                    onClick={() => rtspUrl.trim() && switchVideoSource('rtsp', rtspUrl)}
                    disabled={!rtspUrl.trim()}
                    className="px-6 py-2 bg-blue-500 hover:bg-blue-600 rounded text-sm font-semibold disabled:opacity-50 transition-all"
                    title="Connect to RTSP stream"
                    aria-label="Connect to RTSP stream"
                  >
                    Connect Stream
                  </button>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </motion.div>

        {/* Video Progress Tracker */}
        {videoSource.type === 'file' && videoProgress && !videoProgress.processing_complete && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 bg-slate-900 rounded-lg border border-blue-500/30 p-4"
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <FileVideo className="w-5 h-5 text-blue-400" />
                <span className="text-sm font-semibold">{uploadedFile}</span>
              </div>
              <span className="text-sm text-gray-400 font-bold">{videoProgress.progress_percentage.toFixed(1)}%</span>
            </div>
            
            <div className="w-full bg-slate-800 rounded-full h-3 mb-3 overflow-hidden">
              <motion.div
                className="bg-linear-to-r from-blue-500 to-blue-400 h-3 rounded-full"
                initial={{ width: 0 }}
                animate={{ width: `${videoProgress.progress_percentage}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>
            
            <div className="flex justify-between text-xs text-gray-400">
              <span>Frame {videoProgress.current_frame.toLocaleString()} / {videoProgress.total_frames.toLocaleString()}</span>
              <span className="flex items-center gap-1">
                <Play className="w-3 h-3" />
                Processing...
              </span>
            </div>
          </motion.div>
        )}

        {/* Main Content */}
        <div className="grid grid-cols-3 gap-6 w-full max-w-full">
          {/* Video Feed - Takes 2 columns */}
          <div className="col-span-2 w-full">
            <div className="bg-slate-900 rounded-lg border border-blue-500/30 overflow-hidden">
              <div className="bg-slate-800/50 px-4 py-2 border-b border-blue-500/30 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  <span className="text-sm font-semibold">LIVE FEED</span>
                </div>
                <div className="text-xs text-gray-400">CAMERA-01 | 1280x720</div>
              </div>
              
              <div className="relative aspect-video bg-black">
                {/* Video Stream */}
                <img 
                  src={`${API_BASE}/stream`} 
                  alt="Live surveillance feed"
                  className="w-full h-full object-cover"
                />
                
                {/* Scanning Overlay */}
                <div className="absolute inset-0 pointer-events-none">
                  <motion.div
                    className="absolute left-0 right-0 h-0.5 bg-linear-to-r from-transparent via-blue-500 to-transparent opacity-50"
                    style={{ top: `${scanLine}%` }}
                  />
                  
                  {/* Corner Brackets */}
                  <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-blue-500" />
                  <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-blue-500" />
                  <div className="absolute bottom-4 left-4 w-8 h-8 border-b-2 border-l-2 border-blue-500" />
                  <div className="absolute bottom-4 right-4 w-8 h-8 border-b-2 border-r-2 border-blue-500" />
                </div>
              </div>
            </div>

            {/* Control Panel */}
            <div className="mt-4 grid grid-cols-3 gap-4">
              <button
                onClick={toggleEnhancement}
                className="bg-slate-800 hover:bg-slate-700 border border-blue-500/30 rounded-lg px-4 py-3 flex items-center justify-center gap-2 transition-all hover:border-blue-500 text-white"
                title={enhancementEnabled ? 'Disable enhancement' : 'Enable enhancement'}
                aria-label={enhancementEnabled ? 'Disable enhancement' : 'Enable enhancement'}
              >
                {enhancementEnabled ? <Eye className="w-5 h-5 text-blue-400" /> : <EyeOff className="w-5 h-5 text-gray-400" />}
                <span className="text-sm">Enhancement</span>
              </button>
              
              <button
                onClick={exportLog}
                className="bg-slate-800 hover:bg-slate-700 border border-blue-500/30 rounded-lg px-4 py-3 flex items-center justify-center gap-2 transition-all hover:border-blue-500 text-white"
                title="Export detection log"
                aria-label="Export detection log"
              >
                <Download className="w-5 h-5 text-green-400" />
                <span className="text-sm">Export Log</span>
              </button>
              
              <button 
                onClick={() => setShowWatchlistModal(true)}
                className="bg-slate-800 hover:bg-slate-700 border border-blue-500/30 rounded-lg px-4 py-3 flex items-center justify-center gap-2 transition-all hover:border-blue-500 text-white"
                title="Add person to watchlist"
                aria-label="Add person to watchlist"
              >
                <Shield className="w-5 h-5 text-orange-400" />
                <span className="text-sm">Add Watchlist</span>
              </button>
            </div>
          </div>

          {/* Detection Sidebar */}
          <div className="col-span-1">
            <div className="bg-slate-900 rounded-lg border border-blue-500/30 h-[calc(100vh-280px)]">
              <div className="bg-slate-800/50 px-4 py-2 border-b border-blue-500/30">
                <h3 className="text-sm font-semibold">DETECTED PERSONS</h3>
              </div>
              
              <div className="overflow-y-auto h-[calc(100%-40px)] p-4 space-y-3">
                <AnimatePresence>
                  {detections.map((det) => (
                    <motion.div
                      key={det.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      className={`bg-slate-800 rounded-lg border ${getRiskColor(det.risk_level)} p-3`}
                    >
                      <div className="flex gap-3">
                        <img
                          src={`data:image/jpeg;base64,${det.face_crop}`}
                          alt="Face"
                          className="w-16 h-16 rounded object-cover border-2 border-current"
                        />
                        
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-sm truncate">{det.name}</div>
                          <div className="text-xs text-gray-400 truncate">
                            {new Date(det.timestamp).toLocaleTimeString()}
                          </div>
                          
                          <div className="mt-2">
                            <div className="flex justify-between text-xs mb-1">
                              <span>Confidence</span>
                              <span>{(det.confidence * 100).toFixed(0)}%</span>
                            </div>
                            <div className="w-full bg-slate-700 rounded-full h-1.5">
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${det.confidence * 100}%` }}
                                className="bg-current h-full rounded-full"
                              />
                            </div>
                          </div>
                          
                          <div className="mt-2 text-xs px-2 py-1 rounded bg-current/20 border border-current">
                            {det.risk_level}
                          </div>
                        </div>
                      </div>
                      
                      {det.notes && (
                        <div className="mt-2 text-xs text-gray-400 border-t border-slate-700 pt-2">
                          {det.notes}
                        </div>
                      )}
                    </motion.div>
                  ))}
                </AnimatePresence>
                
                {detections.length === 0 && (
                  <div className="text-center text-gray-500 py-8">
                    <Camera className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p className="text-sm">No detections yet</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Watchlist Modal */}
      <AnimatePresence>
        {showWatchlistModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50"
            onClick={() => setShowWatchlistModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-slate-900 border border-blue-500/30 rounded-lg p-6 w-full max-w-md"
            >
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                <Shield className="w-6 h-6 text-blue-500" />
                Add to Watchlist
              </h2>
              
              <form onSubmit={handleAddToWatchlist} className="space-y-4">
                <div>
                  <label htmlFor="face-image-upload" className="block text-sm mb-2">Face Image</label>
                  <input
                    id="face-image-upload"
                    ref={fileInputRef}
                    type="file"
                    name="file"
                    accept="image/*"
                    required
                    title="Upload face image"
                    className="w-full bg-slate-800 border border-blue-500/30 rounded px-3 py-2 text-sm"
                  />
                </div>
                
                <div>
                  <label className="block text-sm mb-2">Name</label>
                  <input
                    type="text"
                    name="name"
                    required
                    placeholder="John Doe"
                    className="w-full bg-slate-800 border border-blue-500/30 rounded px-3 py-2 text-sm"
                  />
                </div>
                
                <div>
                  <label htmlFor="risk-level-select" className="block text-sm mb-2">Risk Level</label>
                  <select
                    id="risk-level-select"
                    name="risk_level"
                    className="w-full bg-slate-800 border border-blue-500/30 rounded px-3 py-2 text-sm"
                  >
                    <option value="LOW">Low</option>
                    <option value="MEDIUM">Medium</option>
                    <option value="HIGH">High</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm mb-2">Notes</label>
                  <textarea
                    name="notes"
                    placeholder="Additional information..."
                    rows={3}
                    className="w-full bg-slate-800 border border-blue-500/30 rounded px-3 py-2 text-sm"
                  />
                </div>
                
                {uploadStatus && (
                  <div className="text-sm text-center py-2 rounded bg-slate-800">
                    {uploadStatus}
                  </div>
                )}
                
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowWatchlistModal(false)}
                    className="flex-1 bg-slate-800 hover:bg-slate-700 border border-blue-500/30 rounded px-4 py-2 text-sm transition-all"
                    title="Cancel and close modal"
                    aria-label="Cancel and close modal"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 bg-blue-600 hover:bg-blue-700 rounded px-4 py-2 text-sm transition-all"
                    title="Add person to watchlist"
                    aria-label="Add person to watchlist"
                  >
                    Add Person
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Session Stats Modal */}
      <AnimatePresence>
        {showSessionStats && sessionStats && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="bg-slate-900 rounded-lg border-2 border-blue-500/50 p-6 max-w-lg w-full"
            >
              <div className="flex items-center gap-3 mb-6">
                <BarChart3 className="w-6 h-6 text-blue-400" />
                <h3 className="text-xl font-bold">📊 Session Summary</h3>
              </div>

              <div className="space-y-4 mb-6">
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-800 rounded-lg p-4">
                    <div className="text-2xl font-bold">{formatDuration(sessionStats.start_time, sessionStats.end_time)}</div>
                    <div className="text-xs text-gray-400">Duration</div>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-4">
                    <div className="text-2xl font-bold">{sessionStats.total_faces}</div>
                    <div className="text-xs text-gray-400">Total Faces</div>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-4">
                    <div className="text-2xl font-bold">{sessionStats.unique_individuals}</div>
                    <div className="text-xs text-gray-400">Unique People</div>
                  </div>
                  <div className="bg-slate-800 rounded-lg p-4">
                    <div className="text-2xl font-bold">
                      {sessionStats.high_risk_count + sessionStats.medium_risk_count + sessionStats.low_risk_count}
                    </div>
                    <div className="text-xs text-gray-400">Identified</div>
                  </div>
                </div>

                <div className="bg-slate-800 rounded-lg p-4">
                  <div className="text-sm font-semibold mb-3">Risk Breakdown</div>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-red-400">🔴 High Risk</span>
                      <span className="font-bold">{sessionStats.high_risk_count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-orange-400">🟠 Medium Risk</span>
                      <span className="font-bold">{sessionStats.medium_risk_count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-green-400">🟢 Low Risk</span>
                      <span className="font-bold">{sessionStats.low_risk_count}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-400">⚪ Unknown</span>
                      <span className="font-bold">{sessionStats.unknown_count}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                <button
                  onClick={exportSessionReport}
                  className="flex-1 bg-blue-500 hover:bg-blue-600 text-white font-semibold py-2 rounded flex items-center justify-center gap-2 transition-all"
                  title="Export session report"
                  aria-label="Export session report"
                >
                  <Download className="w-4 h-4" />
                  Export Report
                </button>
                <button
                  onClick={() => {
                    setShowSessionStats(false);
                    setVideoProgress(null);
                    switchVideoSource('webcam');
                  }}
                  className="flex-1 bg-slate-700 hover:bg-slate-600 text-white font-semibold py-2 rounded flex items-center justify-center gap-2 transition-all"
                  title="Start new session"
                  aria-label="Start new session"
                >
                  <RefreshCw className="w-4 h-4" />
                  New Session
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}