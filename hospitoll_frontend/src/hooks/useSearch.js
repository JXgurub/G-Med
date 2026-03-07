/**
 * useSearch Hook
 * React hook for search functionality with debouncing and caching
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import SearchService from '../services/SearchService';

/**
 * Hook for search functionality
 * @param {Object} options - Hook options
 * @returns {Object} - Search state and methods
 */
export function useSearch(options = {}) {
  const {
    debounceDelay = 300,
    minQueryLength = 3,
    maxResults = 100,
    autoFocus = false
  } = options;

  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const debounceTimer = useRef(null);
  const cachedResults = useRef({});

  /**
   * Perform search
   */
  const performSearch = useCallback(async (searchQuery, models = null) => {
    if (!searchQuery || searchQuery.length < minQueryLength) {
      setResults(null);
      setSearched(false);
      return;
    }

    // Check cache
    const cacheKey = `${searchQuery}:${models ? models.join(',') : 'all'}`;
    if (cachedResults.current[cacheKey]) {
      setResults(cachedResults.current[cacheKey]);
      setSearched(true);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const searchResults = await SearchService.search(
        searchQuery,
        models,
        maxResults
      );

      // Cache results
      cachedResults.current[cacheKey] = searchResults;

      setResults(searchResults);
      setSearched(true);
    } catch (err) {
      setError(err.message);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, [minQueryLength, maxResults]);

  /**
   * Get search suggestions
   */
  const getSearchSuggestions = useCallback(async (searchQuery, model = null) => {
    if (!searchQuery || searchQuery.length < 2) {
      setSuggestions([]);
      return;
    }

    try {
      const sug = await SearchService.getSuggestions(searchQuery, model);
      setSuggestions(sug);
    } catch (err) {
      console.error('Error getting suggestions:', err);
      setSuggestions([]);
    }
  }, []);

  /**
   * Search doctors
   */
  const searchDoctors = useCallback(async (searchQuery, clinicId, specialtyId) => {
    try {
      setLoading(true);
      setError(null);

      const doctorResults = await SearchService.searchDoctors(
        searchQuery,
        clinicId,
        specialtyId
      );

      setResults({ doctors: doctorResults });
      setSearched(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Handle query input change with debouncing
   */
  const handleQueryChange = useCallback((newQuery) => {
    setQuery(newQuery);

    // Clear previous timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Get suggestions while typing
    getSearchSuggestions(newQuery);

    // Debounce search
    debounceTimer.current = setTimeout(() => {
      performSearch(newQuery);
    }, debounceDelay);
  }, [performSearch, getSearchSuggestions, debounceDelay]);

  /**
   * Clear search results
   */
  const clearSearch = useCallback(() => {
    setQuery('');
    setResults(null);
    setSuggestions([]);
    setSearched(false);
    setError(null);
  }, []);

  /**
   * Clear cache
   */
  const clearCache = useCallback(() => {
    cachedResults.current = {};
  }, []);

  /**
   * Get specialties
   */
  const getSpecialties = useCallback(async () => {
    try {
      return await SearchService.getSpecialties();
    } catch (err) {
      console.error('Error getting specialties:', err);
      return [];
    }
  }, []);

  /**
   * Get doctor availability
   */
  const getDoctorAvailability = useCallback(async (doctorId, date = null) => {
    try {
      return await SearchService.getDoctorAvailability(doctorId, date);
    } catch (err) {
      console.error('Error getting availability:', err);
      return null;
    }
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (debounceTimer.current) {
        clearTimeout(debounceTimer.current);
      }
    };
  }, []);

  return {
    // State
    query,
    results,
    suggestions,
    loading,
    error,
    searched,

    // Methods
    handleQueryChange,
    performSearch,
    getSearchSuggestions,
    searchDoctors,
    clearSearch,
    clearCache,
    getSpecialties,
    getDoctorAvailability,

    // Helpers
    hasResults: results !== null && Object.values(results).some(r => r.items?.length > 0),
    totalResults: results ? Object.values(results).reduce((sum, r) => sum + (r.items?.length || 0), 0) : 0
  };
}

/**
 * Hook for autocomplete search with filtering
 */
export function useAutocompleteSearch(modelFilter = null) {
  const {
    query,
    suggestions,
    handleQueryChange,
    clearSearch
  } = useSearch({ minQueryLength: 1, debounceDelay: 200 });

  return {
    query,
    suggestions,
    handleQueryChange,
    clearSearch,
    modelFilter
  };
}

/**
 * Hook for doctor search with filters
 */
export function useDoctorSearch() {
  const {
    query,
    results,
    loading,
    error,
    handleQueryChange,
    searchDoctors,
    getDoctorAvailability,
    getSpecialties,
    clearSearch
  } = useSearch();

  const [selectedSpecialty, setSelectedSpecialty] = useState(null);
  const [selectedClinic, setSelectedClinic] = useState(null);
  const [availableDates, setAvailableDates] = useState([]);

  /**
   * Handle specialty change
   */
  const handleSpecialtyChange = useCallback((specialtyId) => {
    setSelectedSpecialty(specialtyId);
    // Re-search with new filters
    searchDoctors(query, selectedClinic, specialtyId);
  }, [query, selectedClinic, searchDoctors]);

  /**
   * Handle clinic change
   */
  const handleClinicChange = useCallback((clinicId) => {
    setSelectedClinic(clinicId);
    // Re-search with new filters
    searchDoctors(query, clinicId, selectedSpecialty);
  }, [query, selectedSpecialty, searchDoctors]);

  /**
   * Load doctor availability
   */
  const loadAvailability = useCallback(async (doctorId) => {
    try {
      const availability = await getDoctorAvailability(doctorId);
      return availability;
    } catch (err) {
      console.error('Error loading availability:', err);
      return null;
    }
  }, [getDoctorAvailability]);

  return {
    // Search state
    query,
    results: results?.doctors?.results || [],
    loading,
    error,

    // Filters
    selectedSpecialty,
    selectedClinic,

    // Methods
    handleQueryChange,
    handleSpecialtyChange,
    handleClinicChange,
    searchDoctors: (q) => searchDoctors(q, selectedClinic, selectedSpecialty),
    loadAvailability,
    getSpecialties,
    clearSearch
  };
}

/**
 * Hook for multi-model search
 */
export function useMultiModelSearch(models = ['doctors', 'clinics', 'patients']) {
  const [selectedModels, setSelectedModels] = useState(models);
  const {
    query,
    results,
    loading,
    error,
    handleQueryChange,
    performSearch,
    clearSearch
  } = useSearch();

  /**
   * Handle model selection change
   */
  const handleModelChange = useCallback((model, selected) => {
    if (selected) {
      setSelectedModels(prev => [...prev, model]);
    } else {
      setSelectedModels(prev => prev.filter(m => m !== model));
    }
  }, []);

  /**
   * Perform search with selected models
   */
  const searchWithModels = useCallback((searchQuery) => {
    performSearch(searchQuery, selectedModels);
  }, [performSearch, selectedModels]);

  return {
    // State
    query,
    results,
    loading,
    error,
    selectedModels,

    // Methods
    handleQueryChange,
    handleModelChange,
    searchWithModels,
    clearSearch,

    // Helpers
    flattenResults: () => SearchService.flattenResults(results || {}),
    indexResults: () => SearchService.indexResults(results || {})
  };
}
