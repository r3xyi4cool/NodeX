import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { supabase, checkSupabaseConnectivity } from '../lib/supabase';

const DataContext = createContext(null);

export function DataProvider({ children }) {
  const [lastRefreshed, setLastRefreshed] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState(null);
  const [refreshCount, setRefreshCount] = useState(0);

  const [connectivity, setConnectivity] = useState({
    status: 'CHECKING',
    category: 'CHECKING',
    title: 'Checking Connection...',
    message: 'Testing Supabase availability...',
  });

  const isRefreshingRef = useRef(false);

  // Check Supabase connectivity
  const runConnectivityCheck = useCallback(async () => {
    setConnectivity((prev) => ({
      ...prev,
      status: 'CHECKING',
      title: 'Checking Connection...',
    }));
    try {
      const res = await checkSupabaseConnectivity();
      setConnectivity(res);
      return res;
    } catch (err) {
      const failState = {
        ok: false,
        status: 'FAILED',
        category: 'NETWORK_ERROR',
        title: 'Connection Failed',
        message: err.message || 'Failed to connect to Supabase servers',
      };
      setConnectivity(failState);
      return failState;
    }
  }, []);

  // Manual or automatic refresh with concurrency locking
  const refreshData = useCallback(async () => {
    if (isRefreshingRef.current) return;
    isRefreshingRef.current = true;
    setIsRefreshing(true);
    setRefreshError(null);

    try {
      // 1. Check connectivity
      const conn = await runConnectivityCheck();
      if (!conn.ok) {
        throw new Error(conn.message || 'Supabase unreachable');
      }

      // 2. Increment refresh count to trigger queries across views
      setLastRefreshed(new Date());
      setRefreshCount((c) => c + 1);
    } catch (err) {
      console.warn('Refresh error:', err);
      setRefreshError(err.message || 'Failed to refresh data from Supabase');
    } finally {
      setIsRefreshing(false);
      isRefreshingRef.current = false;
    }
  }, [runConnectivityCheck]);

  const clearRefreshError = useCallback(() => {
    setRefreshError(null);
  }, []);

  // Initial connectivity check & Supabase realtime subscription
  useEffect(() => {
    runConnectivityCheck();

    // Subscribe to realtime updates for live synchronization
    const channel = supabase
      .channel('nodex-cloud-live-sync')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'laptops' }, () => {
        setLastRefreshed(new Date());
        setRefreshCount((c) => c + 1);
      })
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'events' }, () => {
        setLastRefreshed(new Date());
        setRefreshCount((c) => c + 1);
      })
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'captures' }, () => {
        setLastRefreshed(new Date());
        setRefreshCount((c) => c + 1);
      })
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'locations' }, () => {
        setLastRefreshed(new Date());
        setRefreshCount((c) => c + 1);
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [runConnectivityCheck]);

  return (
    <DataContext.Provider
      value={{
        lastRefreshed,
        isRefreshing,
        refreshError,
        refreshCount,
        refreshData,
        connectivity,
        runConnectivityCheck,
        clearRefreshError,
      }}
    >
      {children}
    </DataContext.Provider>
  );
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) {
    throw new Error('useData must be used within a DataProvider');
  }
  return ctx;
}

