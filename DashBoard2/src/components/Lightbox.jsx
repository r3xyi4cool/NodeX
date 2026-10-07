// Full-screen keyboard-accessible photo viewer with zoom, navigation and download
import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Download, AlertTriangle } from 'lucide-react';

export function Lightbox({ photos = [], currentIndex = 0, isOpen, onClose, onNavigate }) {
  const [zoomed, setZoomed] = useState(false);
  const current = photos[currentIndex];

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && currentIndex > 0) onNavigate(currentIndex - 1);
      if (e.key === 'ArrowRight' && currentIndex < photos.length - 1) onNavigate(currentIndex + 1);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentIndex, photos.length, onClose, onNavigate]);

  if (!isOpen || !current) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex flex-col justify-between bg-black/95 p-4 sm:p-6 backdrop-blur-md"
        role="dialog"
        aria-modal="true"
        aria-label="Image lightbox"
      >
        <div className="flex items-center justify-between z-10">
          <div className="text-white text-xs font-mono">
            Slot {current.slot} &bull; {new Date(current.captured_at).toLocaleString()}
            <span className="hidden sm:inline-block ml-3 text-amber-400/90 text-[11px]">
              (20-slot ring buffer: older periodic photos are overwritten)
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setZoomed(!zoomed)}
              aria-label={zoomed ? 'Zoom out' : 'Zoom in'}
              className="p-2 text-white/80 hover:text-white rounded-lg bg-white/10 hover:bg-white/20"
            >
              {zoomed ? <ZoomOut className="w-4 h-4" /> : <ZoomIn className="w-4 h-4" />}
            </button>
            {current.url && (
              <a
                href={current.url}
                download={current.filename || `photo_${current.slot}.jpg`}
                target="_blank"
                rel="noreferrer"
                aria-label="Download photo"
                className="p-2 text-white/80 hover:text-white rounded-lg bg-white/10 hover:bg-white/20"
              >
                <Download className="w-4 h-4" />
              </a>
            )}
            <button
              onClick={onClose}
              aria-label="Close lightbox"
              className="p-2 text-white/80 hover:text-white rounded-lg bg-white/10 hover:bg-white/20"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="relative flex-1 flex items-center justify-center overflow-hidden my-4">
          {currentIndex > 0 && (
            <button
              onClick={() => onNavigate(currentIndex - 1)}
              aria-label="Previous photo"
              className="absolute left-2 z-10 p-3 rounded-full bg-black/50 hover:bg-black/80 text-white"
            >
              <ChevronLeft className="w-6 h-6" />
            </button>
          )}

          <motion.img
            key={current.url || current.slot}
            src={current.url}
            alt={`Capture slot ${current.slot}`}
            animate={{ scale: zoomed ? 1.75 : 1 }}
            transition={{ type: 'spring', stiffness: 260, damping: 25 }}
            onClick={() => setZoomed(!zoomed)}
            className={`max-h-[80vh] max-w-full object-contain rounded-lg cursor-${zoomed ? 'zoom-out' : 'zoom-in'}`}
          />

          {currentIndex < photos.length - 1 && (
            <button
              onClick={() => onNavigate(currentIndex + 1)}
              aria-label="Next photo"
              className="absolute right-2 z-10 p-3 rounded-full bg-black/50 hover:bg-black/80 text-white"
            >
              <ChevronRight className="w-6 h-6" />
            </button>
          )}
        </div>

        <div className="text-center text-xs font-mono text-slate-400">
          {currentIndex + 1} of {photos.length}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
