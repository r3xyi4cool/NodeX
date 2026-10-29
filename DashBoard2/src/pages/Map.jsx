// OpenStreetMap location tracker with historical route trajectory, detailed marker inspection, and laptop selector
import React, { useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  MapPin, RefreshCw, Navigation, Calendar, Clock, Compass,
  Layers, Shield, Laptop, Eye, Camera, Maximize2, AlertTriangle, Info
} from 'lucide-react';
import { Card } from '../components/Card';
import { Badge } from '../components/Badge';
import { getLocations, getLaptops, supabase } from '../lib/supabase';
import { useData } from '../context/DataContext';

// Fix Leaflet default icon paths in bundlers
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export function Map({ onOpenLightbox }) {
  const { refreshCount, lastRefreshed, refreshData, isRefreshing } = useData();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [locations, setLocations] = useState([]);
  const [laptops, setLaptops] = useState([]);
  const [selectedLaptopId, setSelectedLaptopId] = useState('ALL');
  const [selectedLocation, setSelectedLocation] = useState(null);
  const [showTrajectory, setShowTrajectory] = useState(true);

  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersLayerRef = useRef(null);
  const trajectoryLayerRef = useRef(null);
  const accuracyCircleRef = useRef(null);

  // 1. Fetch Laptops and Locations
  const loadData = async (isManualRefresh = false) => {
    try {
      if (isManualRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);

      const [laptopList, locData] = await Promise.all([
        getLaptops().catch(() => []),
        getLocations({ limit: 150, laptopId: selectedLaptopId }),
      ]);

      setLaptops(laptopList || []);
      setLocations(locData || []);

      if (locData && locData.length > 0 && !selectedLocation) {
        setSelectedLocation(locData[0]); // Default to latest
      }
    } catch (err) {
      console.error('Failed to load map location data:', err);
      setError(err.message || 'Failed to load geographical location records');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedLaptopId, refreshCount]);

  // Realtime subscription for incoming location inserts
  useEffect(() => {
    const channel = supabase
      .channel('locations-live-channel')
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'locations' },
        () => {
          loadData(true);
        }
      )
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'heartbeats' },
        (payload) => {
          if (payload.new && payload.new.location) {
            loadData(true);
          }
        }
      )
      .subscribe();

    const pollInterval = setInterval(() => {
      loadData(true);
    }, 20000);

    return () => {
      supabase.removeChannel(channel);
      clearInterval(pollInterval);
    };
  }, [selectedLaptopId]);

  // 2. Initialize Leaflet Map (Guaranteed single initialization)
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Default view: Center on Kochi / India reference coordinates or World
      const map = L.map(mapContainerRef.current, {
        center: [9.9787, 76.3062],
        zoom: 13,
        zoomControl: true,
      });

      // Standard OpenStreetMap (OSM) Tiles
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
        maxZoom: 19,
        subdomains: ['a', 'b', 'c'],
      }).addTo(map);

      // Feature layer groups
      markersLayerRef.current = L.layerGroup().addTo(map);
      trajectoryLayerRef.current = L.layerGroup().addTo(map);

      mapInstanceRef.current = map;
    }

    // Ensure map tiles calculate correct pixel sizes
    const resizeTimer = setTimeout(() => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.invalidateSize();
      }
    }, 250);

    return () => {
      clearTimeout(resizeTimer);
    };
  }, []);

  // 3. Render Markers & Trajectory on Map when locations update
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !markersLayerRef.current || !trajectoryLayerRef.current) return;

    markersLayerRef.current.clearLayers();
    trajectoryLayerRef.current.clearLayers();
    if (accuracyCircleRef.current) {
      map.removeLayer(accuracyCircleRef.current);
      accuracyCircleRef.current = null;
    }

    if (!locations || locations.length === 0) {
      // Reset view to default reference if no points exist
      map.setView([9.9787, 76.3062], 12);
      map.invalidateSize();
      return;
    }

    // Detect overlapping coordinates to add subtle spiderfy offset
    const coordCounts = {};
    const processedLocations = locations.map((loc, idx) => {
      const coordKey = `${loc.latitude.toFixed(5)},${loc.longitude.toFixed(5)}`;
      const seenIndex = coordCounts[coordKey] || 0;
      coordCounts[coordKey] = seenIndex + 1;

      let renderLat = loc.latitude;
      let renderLon = loc.longitude;

      if (seenIndex > 0) {
        // Displace overlapping points in a small circle around the center (~20 meters)
        const angle = (seenIndex * (2 * Math.PI)) / 6;
        const radius = 0.00018 * Math.ceil(seenIndex / 6);
        renderLat += radius * Math.cos(angle);
        renderLon += radius * Math.sin(angle);
      }

      return {
        ...loc,
        renderLat,
        renderLon,
        isLatest: idx === 0,
        indexNumber: locations.length - idx,
      };
    });

    const bounds = L.latLngBounds([]);
    const trajectoryPoints = [];

    // Chronological order for trajectory line: oldest to newest
    const chronological = [...processedLocations].reverse();
    chronological.forEach((loc) => {
      trajectoryPoints.push([loc.renderLat, loc.renderLon]);
    });

    // Draw Trajectory Polyline
    if (showTrajectory && trajectoryPoints.length > 1) {
      L.polyline(trajectoryPoints, {
        color: '#06b6d4',
        weight: 3,
        opacity: 0.8,
        dashArray: '6, 8',
      }).addTo(trajectoryLayerRef.current);
    }

    // Add Custom Markers
    processedLocations.forEach((loc) => {
      bounds.extend([loc.renderLat, loc.renderLon]);

      const isLatest = loc.isLatest;
      const isSelected = selectedLocation && selectedLocation.id === loc.id;

      const customIcon = L.divIcon({
        className: 'custom-map-pin',
        html: `
          <div style="position:relative;width:32px;height:32px;display:flex;align-items:center;justify-content:center;cursor:pointer;">
            ${
              isLatest
                ? `
                  <div style="position:absolute;inset:-4px;border-radius:50%;background:rgba(34,211,238,0.35);animation:pulse 1.8s infinite;"></div>
                  <div style="position:absolute;width:28px;height:28px;border-radius:50%;background:#06b6d4;border:2px solid #ffffff;box-shadow:0 0 14px rgba(6,182,212,0.85);display:flex;align-items:center;justify-content:center;color:#ffffff;font-size:12px;font-weight:700;">
                    📍
                  </div>
                  <span style="position:absolute;bottom:-18px;left:50%;transform:translateX(-50%);background:#0f172a;color:#22d3ee;border:1px solid #06b6d4;font-family:monospace;font-size:9px;font-weight:700;padding:1px 5px;border-radius:9999px;white-space:nowrap;">LATEST</span>
                `
                : isSelected
                ? `
                  <div style="position:absolute;inset:-2px;border-radius:50%;background:rgba(168,85,247,0.4);"></div>
                  <div style="position:absolute;width:24px;height:24px;border-radius:50%;background:#a855f7;border:2px solid #ffffff;box-shadow:0 0 10px rgba(168,85,247,0.85);display:flex;align-items:center;justify-content:center;color:#ffffff;font-family:monospace;font-size:10px;font-weight:700;">
                    ${loc.indexNumber}
                  </div>
                `
                : `
                  <div style="width:20px;height:20px;border-radius:50%;background:#1e293b;border:2px solid #38bdf8;box-shadow:0 2px 6px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;color:#38bdf8;font-family:monospace;font-size:9px;font-weight:700;">
                    ${loc.indexNumber}
                  </div>
                `
            }
          </div>
        `,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -16],
      });

      const marker = L.marker([loc.renderLat, loc.renderLon], { icon: customIcon });

      const dateStr = new Date(loc.created_at).toLocaleString();
      const accuracyStr = loc.accuracy ? `±${Math.round(loc.accuracy)} m` : 'High / GPS';
      const sourceStr = loc.source === 'winrt' ? 'Windows OS (WinRT)' : loc.source?.toUpperCase();
      const popupHtml = `
        <div style="font-family:system-ui,-apple-system,sans-serif;min-width:210px;color:#0f172a;padding:2px 0;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;gap:8px;">
            <strong style="font-size:13px;color:#0369a1;">#${loc.indexNumber} • ${loc.city || 'Recorded Point'}</strong>
            ${isLatest ? '<span style="background:#06b6d4;color:#fff;font-size:9px;font-weight:700;padding:2px 6px;border-radius:4px;">LATEST</span>' : ''}
          </div>
          <div style="font-size:11px;color:#475569;margin-bottom:4px;">
            📍 <b>${loc.latitude.toFixed(5)}, ${loc.longitude.toFixed(5)}</b>
          </div>
          <div style="font-size:11px;color:#64748b;margin-bottom:2px;">
            🕒 ${dateStr}
          </div>
          <div style="font-size:11px;color:#64748b;margin-bottom:2px;">
            🎯 Accuracy: <b>${accuracyStr}</b>
          </div>
          <div style="font-size:11px;color:#64748b;margin-bottom:6px;">
            📡 Source: <b>${sourceStr}</b>
          </div>
          ${
            loc.image_url
              ? `<div style="margin-top:6px;border-radius:4px;overflow:hidden;border:1px solid #cbd5e1;">
                  <img src="${loc.image_url}" style="width:100%;height:80px;object-fit:cover;display:block;" />
                 </div>`
              : ''
          }
        </div>
      `;

      marker.bindPopup(popupHtml);

      marker.on('click', () => {
        setSelectedLocation(loc);
        highlightAccuracyCircle(loc);
      });

      markersLayerRef.current.addLayer(marker);
    });

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
    map.invalidateSize();
  }, [locations, showTrajectory]);

  // Highlight Accuracy Circle on Selection
  const highlightAccuracyCircle = (loc) => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (accuracyCircleRef.current) {
      map.removeLayer(accuracyCircleRef.current);
      accuracyCircleRef.current = null;
    }

    if (loc && loc.accuracy && loc.accuracy > 0) {
      accuracyCircleRef.current = L.circle([loc.latitude, loc.longitude], {
        radius: Math.min(loc.accuracy, 2000),
        color: '#06b6d4',
        weight: 1.5,
        fillColor: '#06b6d4',
        fillOpacity: 0.12,
        dashArray: '4, 4',
      }).addTo(map);
    }
  };

  // Center on Selected Location
  const handleSelectLocation = (loc) => {
    setSelectedLocation(loc);
    highlightAccuracyCircle(loc);
    const map = mapInstanceRef.current;
    if (map) {
      map.flyTo([loc.latitude, loc.longitude], 16, { duration: 0.8 });
    }
  };

  const handleResetBounds = () => {
    const map = mapInstanceRef.current;
    if (!map) return;
    if (locations.length === 0) {
      map.setView([9.9787, 76.3062], 13);
      return;
    }
    const bounds = L.latLngBounds(locations.map((l) => [l.latitude, l.longitude]));
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
  };

  const latestLoc = locations[0];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <MapPin className="w-5 h-5 text-cyan-500" />
              <span>Geographical Location History</span>
            </h2>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-600 dark:text-nodex-cyan border border-cyan-500/20">
              OpenStreetMap (OSM)
            </span>
          </div>
          <p className="text-xs text-slate-500 dark:text-nodex-secondary mt-0.5">
            Real-time physical laptop location tracking recorded every 30s alongside image surveillance
          </p>
        </div>

        {/* Top Controls: Laptop Filter, Route Toggle, Fit All, Refresh */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {laptops.length > 1 && (
            <select
              value={selectedLaptopId}
              onChange={(e) => setSelectedLaptopId(e.target.value)}
              className="text-xs rounded-lg px-2.5 py-1.5 bg-white dark:bg-nodex-card2 border border-slate-200 dark:border-nodex-border text-slate-700 dark:text-nodex-primary focus:outline-none focus:border-cyan-500"
            >
              <option value="ALL">All Laptops ({laptops.length})</option>
              {laptops.map((lap) => (
                <option key={lap.id} value={lap.id}>
                  {lap.name || lap.fingerprint?.slice(0, 10)}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={() => setShowTrajectory(!showTrajectory)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              showTrajectory
                ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border-cyan-500/30'
                : 'bg-white dark:bg-nodex-card2 text-slate-600 dark:text-nodex-secondary border-slate-200 dark:border-nodex-border'
            }`}
          >
            <Navigation className="w-3.5 h-3.5" />
            <span>Route</span>
          </button>

          <button
            onClick={handleResetBounds}
            title="Fit all markers in view"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-white dark:bg-nodex-card2 border border-slate-200 dark:border-nodex-border text-slate-600 dark:text-nodex-secondary hover:text-slate-900 dark:hover:text-white"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            <span>Fit All</span>
          </button>

          <button
            onClick={() => loadData(true)}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-cyan-500/10 text-cyan-600 dark:text-nodex-cyan border border-cyan-500/20 hover:bg-cyan-500/20 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>{refreshing ? 'Refreshing…' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Map Canvas + Sidebar Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Map Card (Span 2 cols on lg) */}
        <div className="lg:col-span-2 space-y-4">
          <Card hover={false} className="p-0 overflow-hidden relative">
            {/* Loading Indicator Overlay */}
            {loading && (
              <div className="absolute top-3 right-3 z-[1000] bg-slate-900/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-cyan-500/30 flex items-center gap-2 text-cyan-400 text-xs font-mono shadow-lg">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Syncing OSM data…</span>
              </div>
            )}

            {/* Floating Map Stats Banner */}
            <div className="absolute top-3 left-3 z-[1000] bg-white/90 dark:bg-slate-900/90 backdrop-blur-md px-3.5 py-2 rounded-xl border border-slate-200 dark:border-nodex-border shadow-md flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <span className={`w-2.5 h-2.5 rounded-full ${locations.length > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'}`} />
                <span className="text-xs font-bold text-slate-800 dark:text-white font-mono">
                  {locations.length} {locations.length === 1 ? 'Point' : 'Points'}
                </span>
              </div>
              {latestLoc && (
                <div className="hidden sm:flex items-center gap-1.5 pl-3 border-l border-slate-200 dark:border-slate-700 text-xs text-slate-600 dark:text-slate-300">
                  <span className="text-slate-400 dark:text-slate-500">Latest:</span>
                  <span className="font-semibold text-cyan-600 dark:text-cyan-400 truncate max-w-[150px]">
                    {latestLoc.city || `${latestLoc.latitude.toFixed(3)}, ${latestLoc.longitude.toFixed(3)}`}
                  </span>
                </div>
              )}
            </div>

            {/* Empty State Banner overlay when 0 locations */}
            {!loading && locations.length === 0 && (
              <div className="absolute top-14 left-3 right-3 sm:right-auto sm:max-w-md z-[1000] bg-slate-900/90 backdrop-blur-md p-3.5 rounded-xl border border-cyan-500/30 shadow-xl text-xs">
                <div className="flex items-start gap-2.5">
                  <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="font-semibold text-white">No Location Points Recorded Yet</p>
                    <p className="text-slate-400 text-[11px] mt-0.5 leading-relaxed">
                      Dashboard 1 transmits coordinates every 30s alongside image surveillance. You can also click <b>"📍 Send Location"</b> on Dashboard 1 to send coordinates right now.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Map Canvas (ALWAYS rendered in DOM so Leaflet attaches immediately) */}
            <div
              ref={mapContainerRef}
              className="w-full h-[520px] rounded-xl z-0"
              style={{ minHeight: '520px', background: '#0a0f1e' }}
            />
          </Card>

          {/* Selected Location Details Card */}
          {selectedLocation ? (
            <Card hover={false} className="border-l-4 border-l-cyan-500 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-100 dark:border-nodex-border/60">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-600 dark:text-cyan-400">
                    <Compass className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-bold text-slate-900 dark:text-white">
                      {selectedLocation.city || 'Recorded Location'}
                      {selectedLocation.region ? `, ${selectedLocation.region}` : ''}
                      {selectedLocation.country ? `, ${selectedLocation.country}` : ''}
                    </h4>
                    <p className="text-[11px] font-mono text-cyan-600 dark:text-cyan-400">
                      {selectedLocation.latitude.toFixed(6)}, {selectedLocation.longitude.toFixed(6)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {selectedLocation.id === latestLoc?.id && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                      LATEST POSITION
                    </span>
                  )}
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 dark:bg-nodex-card2 text-slate-600 dark:text-nodex-secondary border border-slate-200 dark:border-nodex-border">
                    {selectedLocation.sync_event || 'SYNC'}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-100 dark:border-nodex-border/50">
                  <span className="text-[10px] uppercase font-mono text-slate-400 dark:text-nodex-dim block mb-1">
                    Recorded At
                  </span>
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {new Date(selectedLocation.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                  <span className="text-[10px] text-slate-400 dark:text-nodex-dim block">
                    {new Date(selectedLocation.created_at).toLocaleDateString()}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-100 dark:border-nodex-border/50">
                  <span className="text-[10px] uppercase font-mono text-slate-400 dark:text-nodex-dim block mb-1">
                    Accuracy
                  </span>
                  <span className="font-medium text-slate-800 dark:text-slate-200">
                    {selectedLocation.accuracy ? `±${Math.round(selectedLocation.accuracy)} meters` : 'High / GPS'}
                  </span>
                  <span className="text-[10px] text-slate-400 dark:text-nodex-dim block">
                    {selectedLocation.altitude ? `Alt: ${selectedLocation.altitude.toFixed(1)}m` : 'Ground'}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-100 dark:border-nodex-border/50">
                  <span className="text-[10px] uppercase font-mono text-slate-400 dark:text-nodex-dim block mb-1">
                    Provider Source
                  </span>
                  <span className="font-medium text-slate-800 dark:text-slate-200 truncate block">
                    {selectedLocation.source === 'winrt' ? 'Windows OS (WinRT)' : selectedLocation.source || 'Network IP'}
                  </span>
                  <span className="text-[10px] text-slate-400 dark:text-nodex-dim block">
                    {selectedLocation.ip || 'OS Geolocation'}
                  </span>
                </div>

                <div className="p-2.5 rounded-lg bg-slate-50 dark:bg-nodex-card2 border border-slate-100 dark:border-nodex-border/50">
                  <span className="text-[10px] uppercase font-mono text-slate-400 dark:text-nodex-dim block mb-1">
                    Laptop Station
                  </span>
                  <span className="font-medium text-slate-800 dark:text-slate-200 truncate block">
                    {selectedLocation.laptops?.name || 'Local Machine'}
                  </span>
                  <span className="text-[10px] text-slate-400 dark:text-nodex-dim block truncate">
                    {selectedLocation.laptops?.os || 'Windows 11'}
                  </span>
                </div>
              </div>

              {/* Associated Capture Photo if present */}
              {selectedLocation.image_url && (
                <div className="mt-3 pt-3 border-t border-slate-100 dark:border-nodex-border/60 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Camera className="w-4 h-4 text-cyan-500" />
                    <span className="text-xs text-slate-600 dark:text-nodex-secondary">
                      Surveillance photo taken during this synchronization:
                    </span>
                  </div>
                  <button
                    onClick={() => onOpenLightbox && onOpenLightbox([selectedLocation.image_url], 0)}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-600 dark:text-nodex-cyan text-xs font-semibold hover:bg-cyan-500/20 transition-colors"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View Snapshot</span>
                  </button>
                </div>
              )}
            </Card>
          ) : (
            <Card hover={false} className="p-4 text-center text-xs text-slate-400">
              Select any marker on the OpenStreetMap to inspect its recorded details.
            </Card>
          )}
        </div>

        {/* Right Sidebar: Chronological History Timeline */}
        <div className="space-y-4">
          <Card
            title="Location Timeline"
            subtitle={`${locations.length} updates recorded in Supabase`}
            className="max-h-[660px] flex flex-col"
          >
            {locations.length === 0 ? (
              <div className="py-12 px-4 text-center space-y-3">
                <MapPin className="w-8 h-8 text-slate-400 dark:text-nodex-dim mx-auto" />
                <p className="text-xs text-slate-500 dark:text-nodex-secondary">
                  No location records received yet.
                </p>
                <button
                  onClick={() => loadData(true)}
                  className="px-3 py-1.5 bg-cyan-500/10 text-cyan-500 border border-cyan-500/30 rounded-lg text-xs font-medium hover:bg-cyan-500/20"
                >
                  Check Now
                </button>
              </div>
            ) : (
              <div className="overflow-y-auto space-y-2.5 pr-1 max-h-[560px]">
                {locations.map((loc, idx) => {
                  const isLatest = idx === 0;
                  const isSelected = selectedLocation && selectedLocation.id === loc.id;
                  const itemNumber = locations.length - idx;

                  return (
                    <div
                      key={loc.id || idx}
                      onClick={() => handleSelectLocation(loc)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-cyan-500/10 border-cyan-500 dark:border-cyan-500/60 shadow-sm'
                          : 'bg-slate-50 dark:bg-nodex-card2 border-slate-100 dark:border-nodex-border/50 hover:border-slate-300 dark:hover:border-slate-700'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`w-5 h-5 rounded-full flex items-center justify-center font-mono text-[10px] font-bold ${
                              isLatest
                                ? 'bg-emerald-500 text-white'
                                : isSelected
                                ? 'bg-cyan-500 text-white'
                                : 'bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-300'
                            }`}
                          >
                            {itemNumber}
                          </span>
                          <div>
                            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 block truncate max-w-[130px]">
                              {loc.city || 'Recorded Point'}
                            </span>
                            <span className="text-[10px] font-mono text-slate-400 dark:text-nodex-dim">
                              {loc.latitude.toFixed(4)}, {loc.longitude.toFixed(4)}
                            </span>
                          </div>
                        </div>

                        {isLatest ? (
                          <span className="text-[9px] font-bold font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                            LATEST
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono text-slate-400 dark:text-nodex-dim">
                            {new Date(loc.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </div>

                      <div className="mt-2 pt-2 border-t border-slate-200/50 dark:border-slate-800 flex items-center justify-between text-[10px] text-slate-500 dark:text-nodex-dim font-mono">
                        <span>{loc.source === 'winrt' ? 'GPS/WinRT' : loc.source || 'IP'}</span>
                        <span>{loc.accuracy ? `±${Math.round(loc.accuracy)}m` : 'Accurate'}</span>
                        {loc.image_url && <span className="text-cyan-500">📷 Photo</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
