/**
 * Search Service
 * API client for search operations
 */

import axios from 'axios';
import { API_BASE_URL } from './api';

const SEARCH_API = `${API_BASE_URL}/search`;
const CACHE_API = `${API_BASE_URL}/cache`;

class SearchService {
  /**
   * Perform full-text search
   * @param {string} query - Search query
   * @param {string[]} models - Models to search (optional)
   * @param {number} limit - Max results per model
   * @returns {Promise<Object>} - Search results
   */
  static async search(query, models = null, limit = 20) {
    try {
      const params = new URLSearchParams();
      params.append('q', query);
      if (models && models.length) {
        params.append('models', models.join(','));
      }
      params.append('limit', limit);

      const response = await axios.get(
        `${SEARCH_API}/list_all/?${params.toString()}`
      );
      return response.data;
    } catch (error) {
      console.error('Search error:', error);
      throw error;
    }
  }

  /**
   * Get search suggestions
   * @param {string} query - Partial query
   * @param {string} model - Model filter (optional)
   * @returns {Promise<string[]>} - Suggestions
   */
  static async getSuggestions(query, model = null) {
    try {
      const params = new URLSearchParams();
      params.append('q', query);
      if (model) {
        params.append('model', model);
      }

      const response = await axios.get(
        `${SEARCH_API}/suggestions/?${params.toString()}`
      );
      return response.data.suggestions || [];
    } catch (error) {
      console.error('Suggestions error:', error);
      return [];
    }
  }

  /**
   * Search doctors
   * @param {string} query - Search query (optional)
   * @param {number} clinicId - Clinic ID filter (optional)
   * @param {number} specialtyId - Specialty ID filter (optional)
   * @returns {Promise<Object>} - Doctor search results
   */
  static async searchDoctors(query = null, clinicId = null, specialtyId = null) {
    try {
      const params = new URLSearchParams();
      if (query) params.append('q', query);
      if (clinicId) params.append('clinic_id', clinicId);
      if (specialtyId) params.append('specialty_id', specialtyId);

      const response = await axios.get(
        `${SEARCH_API}/doctors/?${params.toString()}`
      );
      return response.data;
    } catch (error) {
      console.error('Doctor search error:', error);
      throw error;
    }
  }

  /**
   * Get doctor availability
   * @param {number} doctorId - Doctor ID
   * @param {string} date - Date (YYYY-MM-DD format, optional)
   * @returns {Promise<Object>} - Availability info
   */
  static async getDoctorAvailability(doctorId, date = null) {
    try {
      const params = new URLSearchParams();
      if (date) params.append('date', date);

      const response = await axios.get(
        `${SEARCH_API}/${doctorId}/availability/?${params.toString()}`
      );
      return response.data;
    } catch (error) {
      console.error('Availability error:', error);
      throw error;
    }
  }

  /**
   * Get all specialties
   * @returns {Promise<Object[]>} - Specialties list
   */
  static async getSpecialties() {
    try {
      const response = await axios.get(`${SEARCH_API}/specialties/`);
      return response.data.specialties || [];
    } catch (error) {
      console.error('Specialties error:', error);
      return [];
    }
  }

  /**
   * Invalidate cache (admin only)
   * @param {string[]} patterns - Cache patterns to invalidate
   * @returns {Promise<Object>} - Result
   */
  static async invalidateCache(patterns) {
    try {
      const response = await axios.post(
        `${CACHE_API}/invalidate/`,
        { patterns }
      );
      return response.data;
    } catch (error) {
      console.error('Cache invalidation error:', error);
      throw error;
    }
  }

  /**
   * Clear all cache (admin only)
   * @returns {Promise<Object>} - Result
   */
  static async clearCache() {
    try {
      const response = await axios.post(`${CACHE_API}/clear/`);
      return response.data;
    } catch (error) {
      console.error('Cache clear error:', error);
      throw error;
    }
  }

  /**
   * Get cache statistics (admin only)
   * @returns {Promise<Object>} - Cache stats
   */
  static async getCacheStats() {
    try {
      const response = await axios.get(`${CACHE_API}/stats/`);
      return response.data;
    } catch (error) {
      console.error('Cache stats error:', error);
      throw error;
    }
  }

  /**
   * Index results by type for easier UI rendering
   * @param {Object} results - Search results from API
   * @returns {Object} - Re-indexed results
   */
  static indexResults(results) {
    const indexed = {};
    for (const [key, value] of Object.entries(results)) {
      if (value.items) {
        indexed[key] = value.items.reduce((acc, item) => {
          if (!acc[item.type]) {
            acc[item.type] = [];
          }
          acc[item.type].push(item);
          return acc;
        }, {});
      }
    }
    return indexed;
  }

  /**
   * Flatten search results for display
   * @param {Object} results - Search results
   * @returns {Object[]} - Flattened results (all items with type)
   */
  static flattenResults(results) {
    const flattened = [];
    for (const [modelName, data] of Object.entries(results)) {
      if (data.items && Array.isArray(data.items)) {
        flattened.push(...data.items);
      }
    }
    return flattened;
  }

  /**
   * Highlight search query in text
   * @param {string} text - Text to highlight
   * @param {string} query - Query to highlight
   * @returns {string} - HTML with highlights
   */
  static highlightQuery(text, query) {
    if (!text || !query) return text;
    
    const regex = new RegExp(`(${query})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
  }
}

export default SearchService;
