import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Camera, Shield, Activity, AlertTriangle, Download, Eye, EyeOff } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';
const WS_URL = 'ws://localhost:8000/api/logs';

interface Detection {
  id: string;
  name: string;
  timestamp: string;
  confidence: number;
  risk_level: string;
  face_crop: string;
  match?: boolean;
  notes?: string;
}

interface Stats {
  total_detections: number;
  high_risk_count: number;
  medium_risk_count: number;
  watchlist_size: number;
  fps: number;
}

export default function AegisVisionDashboard() {
  const [detections, setDetections] = useState<Detection[]>([]);
  const [stats, setStats] = useState<Stats>({ total_detections: 0, high_risk_count: 0, medium_risk_count: 0, watchlist_size: 0, fps: 0 });
  const [enhancementEnabled, setEnhancementEnabled] = useState(true);
  const [alertActive, setAlertActive] = useState(false);
  const [scanLine, setScanLine] = useState(0);
  const [showWatchlistModal, setShowWatchlistModal] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const wsRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
        
        // Trigger alert for high-risk detections
        const hasHighRisk = message.data.some((d: Detection) => d.risk_level === 'HIGH');
        if (hasHighRisk) {
          setAlertActive(true);
          setTimeout(() => setAlertActive(false), 2000);
        }
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
      {/* Alert Flash Overlay */}
      <AnimatePresence>
        {alertActive && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.3, 0, 0.3, 0] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1 }}
            className="fixed inset-0 bg-red-600 pointer-events-none z-50"
          />
        )}
      </AnimatePresence>

      {/* Header */}
      <header className="border-b border-blue-500/30 bg-slate-900/50 backdrop-blur-sm">
        <div className="w-full px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-2xl font-bold tracking-wider">AEGIS-VISION</h1>
              <p className="text-xs text-blue-400">Advanced Surveillance & Recognition</p>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-green-400">
              <Activity className="w-5 h-5 animate-pulse" />
              <span className="text-sm">SYSTEM ACTIVE</span>
            </div>
            <div className="text-sm text-gray-400">
              {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      </header>

      {/* Stats Bar */}
      <div className="border-b border-blue-500/20 bg-slate-900/30">
        <div className="w-full px-6 py-3 grid grid-cols-4 gap-4">
          <StatCard label="Total Detections" value={stats.total_detections} icon={<Camera />} />
          <StatCard label="High Risk" value={stats.high_risk_count} icon={<AlertTriangle />} color="text-red-500" />
          <StatCard label="Watchlist Size" value={stats.watchlist_size} icon={<Shield />} color="text-blue-500" />
          <StatCard label="FPS" value={stats.fps?.toFixed(1) || '0.0'} icon={<Activity />} color={enhancementEnabled ? 'text-green-500' : 'text-gray-500'} />
        </div>
      </div>

      {/* Main Content */}
      <div className="w-full px-6 py-6">
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
                    className="absolute left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-blue-500 to-transparent opacity-50"
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
              >
                {enhancementEnabled ? <Eye className="w-5 h-5 text-blue-400" /> : <EyeOff className="w-5 h-5 text-gray-400" />}
                <span className="text-sm">Enhancement</span>
              </button>
              
              <button
                onClick={exportLog}
                className="bg-slate-800 hover:bg-slate-700 border border-blue-500/30 rounded-lg px-4 py-3 flex items-center justify-center gap-2 transition-all hover:border-blue-500 text-white"
              >
                <Download className="w-5 h-5 text-green-400" />
                <span className="text-sm">Export Log</span>
              </button>
              
              <button 
                onClick={() => setShowWatchlistModal(true)}
                className="bg-slate-800 hover:bg-slate-700 border border-blue-500/30 rounded-lg px-4 py-3 flex items-center justify-center gap-2 transition-all hover:border-blue-500 text-white"
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
                          
                          {det.match && (
                            <div className="mt-2 text-xs px-2 py-1 rounded bg-current/20 border border-current">
                              {det.risk_level}
                            </div>
                          )}
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
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="flex-1 bg-blue-600 hover:bg-blue-700 rounded px-4 py-2 text-sm transition-all"
                  >
                    Add Person
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number | string;
  icon: React.ReactNode;
  color?: string;
}

function StatCard({ label, value, icon, color = 'text-blue-500' }: StatCardProps) {
  return (
    <div className="bg-slate-900 rounded-lg border border-blue-500/20 p-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-gray-400 mb-1">{label}</div>
          <div className={`text-2xl font-bold ${color}`}>{value}</div>
        </div>
        <div className={color}>
          {icon}
        </div>
      </div>
    </div>
  );
}