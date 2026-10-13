/**
 * useAnalytics - React Hook for fetching analytics data
 * Handles data fetching, caching, error states, and auto-refresh
 */

import { useState, useCallback, useEffect } from 'react';

const CACHE_TIMEOUT = 60000; // 1 minute cache
const REFRESH_INTERVAL = 60000; // Auto-refresh every minute

export const useAnalytics = (clinicId, options = {}) => {
  const {
    endpoint = 'dashboard',
    refetchInterval = REFRESH_INTERVAL,
    cacheTimeout = CACHE_TIMEOUT,
    enabled = true,
  } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetchTime, setLastFetchTime] = useState(null);
  const [cache, setCache] = useState({});

  /**
   * Fetch analytics data from API
   */
  const fetch = useCallback(async () => {
    if (!clinicId || !enabled) return;

    try {
      setError(null);

      // Check cache first
      const cacheKey = `${endpoint}:${clinicId}`;
      const cachedData = cache[cacheKey];
      const now = Date.now();

      if (
        cachedData &&
        cachedData.timestamp &&
        now - cachedData.timestamp < cacheTimeout
      ) {
        setData(cachedData.data);
        setLoading(false);
        return;
      }

      setLoading(true);

      const response = await fetch(
        `/api/v1/analytics/${endpoint}/?clinic_id=${clinicId}`
      );

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const result = await response.json();

      if (result.success) {
        // For dashboard endpoint, data is in result.dashboard
        const analyticsData = result.dashboard || result.data;
        
        setData(analyticsData);
        setLastFetchTime(now);

        // Update cache
        setCache((prev) => ({
          ...prev,
          [cacheKey]: {
            data: analyticsData,
            timestamp: now,
          },
        }));

        setError(null);
      } else {
        throw new Error(result.error || 'Failed to fetch analytics data');
      }
    } catch (err) {
      setError(err.message || 'Unknown error occurred');
      setLoading(false);
    } finally {
      setLoading(false);
    }
  }, [clinicId, endpoint, enabled, cache, cacheTimeout]);

  /**
   * Manual refetch
   */
  const refetch = useCallback(() => {
    setCache((prev) => {
      const newCache = { ...prev };
      const cacheKey = `${endpoint}:${clinicId}`;
      delete newCache[cacheKey];
      return newCache;
    });
    fetch();
  }, [fetch, endpoint, clinicId]);

  /**
   * Clear cache
   */
  const clearCache = useCallback(() => {
    setCache({});
  }, []);

  /**
   * Auto-fetch on mount and when dependencies change
   */
  useEffect(() => {
    fetch();
  }, [clinicId, endpoint, enabled, fetch]);

  /**
   * Auto-refresh interval
   */
  useEffect(() => {
    if (!enabled || !clinicId) return;

    const interval = setInterval(() => {
      fetch();
    }, refetchInterval);

    return () => clearInterval(interval);
  }, [enabled, clinicId, refetchInterval, fetch]);

  return {
    data,
    loading,
    error,
    refetch,
    clearCache,
    lastFetchTime,
    isCached: !!lastFetchTime && Date.now() - lastFetchTime < cacheTimeout,
  };
};

/**
 * useFirebaseAnalytics - For future Firebase integration
 * Placeholder for cloud analytics
 */
export const useFirebaseAnalytics = (clinicId) => {
  // TODO: Implement Firebase analytics tracking
  return {
    trackEvent: (eventName, params) => {
      console.log(`[Analytics] ${eventName}`, params);
    },
    trackScreenView: (screenName) => {
      console.log(`[Analytics] Screen: ${screenName}`);
    },
  };
};

/**
 * useAnalyticsCache - Utility hook for cache management
 */
export const useAnalyticsCache = () => {
  const [cacheStats, setCacheStats] = useState({
    hits: 0,
    misses: 0,
    size: 0,
  });

  const recordHit = useCallback(() => {
    setCacheStats((prev) => ({
      ...prev,
      hits: prev.hits + 1,
    }));
  }, []);

  const recordMiss = useCallback(() => {
    setCacheStats((prev) => ({
      ...prev,
      misses: prev.misses + 1,
    }));
  }, []);

  const getHitRate = useCallback(() => {
    const total = cacheStats.hits + cacheStats.misses;
    return total === 0 ? 0 : Math.round((cacheStats.hits / total) * 100);
  }, [cacheStats]);

  return {
    cacheStats,
    recordHit,
    recordMiss,
    getHitRate,
  };
};

export default useAnalytics;
