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
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-nodex-base">
        <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!session) {
    return <Login onLoginSuccess={(s) => setSession(s)} />;
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-nodex-base text-slate-800 dark:text-nodex-primary flex">
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onLogout={handleLogout}
        userEmail={session?.user?.email}
      />

      <div className="flex-1 lg:pl-64 flex flex-col min-h-screen">
        <header className="lg:hidden p-4 border-b border-slate-200 dark:border-nodex-border bg-white dark:bg-nodex-card flex items-center justify-between">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open sidebar"
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-white"
          >
            <Menu className="w-5 h-5" />
          </button>
          <span className="font-bold text-sm">Node<span className="text-cyan-500">X</span> Cloud</span>
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
