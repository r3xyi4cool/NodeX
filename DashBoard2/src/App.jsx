// Main application layout, routing, realtime subscriptions, and authentication session router
import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu } from 'lucide-react';
import { supabase, isConfigured } from './lib/supabase';
import { Sidebar } from './components/Sidebar';
import { Lightbox } from './components/Lightbox';
import { Login } from './pages/Login';
import { Overview } from './pages/Overview';
import { Laptop } from './pages/Laptop';
import { Token } from './pages/Token';
import { Events } from './pages/Events';
import { Captures } from './pages/Captures';
import { Alerts } from './pages/Alerts';
import { Stats } from './pages/Stats';

function PerspectiveGridBackground() {
  const W = 1000, H = 700, vx = 575, vy = 330;
  const bw = { l: 410, r: 740, t: 240, b: 430 };
  const lines = [];

  for (let i = 0; i <= 12; i++) {
    const t = i / 12;
    const yTop = t * bw.t;
    const yBot = H - t * (H - bw.b);
    lines.push(<line key={`c1-${i}`} x1={0} y1={i * 6} x2={bw.l} y2={yTop} />);
    lines.push(<line key={`c2-${i}`} x1={W} y1={i * 6} x2={bw.r} y2={yTop} />);
    lines.push(<line key={`f1-${i}`} x1={0} y1={H - i * 6} x2={bw.l} y2={yBot} />);
    lines.push(<line key={`f2-${i}`} x1={W} y1={H - i * 6} x2={bw.r} y2={yBot} />);
  }

  for (let j = 0; j <= 8; j++) {
    const f = j / 8, e = Math.pow(f, 1.6);
    const xl = e * bw.l, xr = W - e * (W - bw.r);
    const tl = e * bw.t, bl = H - e * (H - bw.b);
    const isStrong = j % 4 === 0;
    lines.push(<line key={`w1-${j}`} x1={xl} y1={tl} x2={xl} y2={bl} className={isStrong ? 'strong' : ''} />);
    lines.push(<line key={`w2-${j}`} x1={xr} y1={tl} x2={xr} y2={bl} className={isStrong ? 'strong' : ''} />);
  }

  lines.push(<line key="bw-t" x1={bw.l} y1={bw.t} x2={bw.r} y2={bw.t} className="strong" />);
  lines.push(<line key="bw-b" x1={bw.l} y1={bw.b} x2={bw.r} y2={bw.b} className="strong" />);
  lines.push(<line key="bw-l" x1={bw.l} y1={bw.t} x2={bw.l} y2={bw.b} className="strong" />);
  lines.push(<line key="bw-r" x1={bw.r} y1={bw.t} x2={bw.r} y2={bw.b} className="strong" />);
  lines.push(<line key="v-cen" x1={vx} y1={0} x2={vx} y2={H} className="strong" />);

  for (let k = 1; k < 8; k++) {
    lines.push(<line key={`fan-l-${k}`} x1={0} y1={(H / 8) * k} x2={vx} y2={vy} />);
    lines.push(<line key={`fan-r-${k}`} x1={W} y1={(H / 8) * k} x2={vx} y2={vy} />);
  }

  return (
    <>
      <div className="grid-bg" aria-hidden="true">
        <svg preserveAspectRatio="none" viewBox="0 0 1000 700">
          {lines}
        </svg>
      </div>
      <div className="grid-glow" aria-hidden="true" />
    </>
  );
}

export default function App() {
  const [session, setSession] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [lightboxState, setLightboxState] = useState({ isOpen: false, photos: [], index: 0 });
  const location = useLocation();

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      setAuthLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  const openLightbox = (photos, index = 0) => {
    setLightboxState({ isOpen: true, photos, index });
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#000308] relative">
        <PerspectiveGridBackground />
        <div className="relative z-10 w-10 h-10 border-2 border-[#006eff] border-t-transparent rounded-full animate-spin shadow-[0_0_24px_rgba(0,110,255,0.5)]" />
      </div>
    );
  }

  if (!session) {
    return <Login onLoginSuccess={(s) => setSession(s)} />;
  }

  return (
    <div className="min-h-screen bg-[#000308] text-white flex relative overflow-x-hidden font-sans">
      <PerspectiveGridBackground />

      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onLogout={handleLogout}
        userEmail={session?.user?.email}
      />

      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen relative z-10">
        <header className="lg:hidden p-4 border-b border-white/10 bg-[#00040d]/80 backdrop-blur-xl flex items-center justify-between">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
            className="p-2 rounded-xl text-[#c9d1de] hover:text-white hover:bg-white/5 transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-medium italic text-base tracking-tight text-white font-sans">
            Node<b className="text-[#006eff] not-italic font-bold">X</b>{' '}
            <span className="ml-1 text-[10px] not-italic font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border border-white/20 bg-white/5 text-[#c9d1de]">
              Cloud
            </span>
          </span>
          <div className="w-5" />
        </header>

        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18 }}
            >
              <Routes>
                <Route path="/" element={<Overview onOpenLightbox={openLightbox} />} />
                <Route path="/laptop" element={<Laptop />} />
                <Route path="/token" element={<Token />} />
                <Route path="/events" element={<Events />} />
                <Route path="/captures" element={<Captures onOpenLightbox={openLightbox} />} />
                <Route path="/alerts" element={<Alerts />} />
                <Route path="/stats" element={<Stats />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      <Lightbox
        isOpen={lightboxState.isOpen}
        photos={lightboxState.photos}
        currentIndex={lightboxState.index}
        onClose={() => setLightboxState((prev) => ({ ...prev, isOpen: false }))}
        onNavigate={(idx) => setLightboxState((prev) => ({ ...prev, index: idx }))}
      />
    </div>
  );
}
