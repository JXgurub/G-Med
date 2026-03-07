/**
 * SearchBar Component
 * Universal search bar with suggestions and autocomplete
 */

import React, { useState, useEffect, useRef } from 'react';
import { useSearch } from '@/hooks/useSearch';
import styles from './SearchBar.module.css';

function SearchBar({ 
  placeholder = "Izlash...", 
  onResultsChange = null,
  onSearch = null,
  modelFilter = null,
  showSuggestions = true,
  showFilters = false
}) {
  const {
    query,
    results,
    suggestions,
    loading,
    error,
    handleQueryChange,
    clearSearch
  } = useSearch({ minQueryLength: 2 });

  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef(null);
  const dropdownRef = useRef(null);

  // Notify parent of results change
  useEffect(() => {
    if (onResultsChange) {
      onResultsChange(results);
    }
  }, [results, onResultsChange]);

  /**
   * Handle input focus
   */
  const handleFocus = () => {
    setShowDropdown(true);
  };

  /**
   * Handle input blur
   */
  const handleBlur = () => {
    // Delay to allow click on suggestion
    setTimeout(() => {
      setShowDropdown(false);
      setActiveIndex(-1);
    }, 100);
  };

  /**
   * Handle suggestion click
   */
  const handleSuggestionClick = (suggestion) => {
    handleQueryChange(suggestion);
    setShowDropdown(false);
    if (onSearch) {
      onSearch(suggestion);
    }
  };

  /**
   * Handle keyboard navigation
   */
  const handleKeyDown = (e) => {
    if (!showDropdown) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex(prev => 
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex(prev => prev > 0 ? prev - 1 : -1);
        break;
      case 'Enter':
        e.preventDefault();
        if (activeIndex >= 0 && suggestions[activeIndex]) {
          handleSuggestionClick(suggestions[activeIndex]);
        } else if (query) {
          if (onSearch) onSearch(query);
          setShowDropdown(false);
        }
        break;
      case 'Escape':
        setShowDropdown(false);
        break;
      default:
        break;
    }
  };

  /**
   * Handle clear button
   */
  const handleClear = () => {
    clearSearch();
    inputRef.current?.focus();
  };

  return (
    <div className={styles.searchBarContainer}>
      {/* Main search input */}
      <div className={styles.inputWrapper}>
        <span className={styles.searchIcon}>🔍</span>
        
        <input
          ref={inputRef}
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={handleKeyDown}
          className={styles.input}
          autoComplete="off"
        />

        {/* Clear button */}
        {query && (
          <button
            onClick={handleClear}
            className={styles.clearButton}
            title="Qayta boshlash"
          >
            ✕
          </button>
        )}

        {/* Loading indicator */}
        {loading && (
          <span className={styles.loadingIcon}>⌛</span>
        )}
      </div>

      {/* Error message */}
      {error && (
        <div className={styles.errorMessage}>
          {error}
        </div>
      )}

      {/* Suggestions dropdown */}
      {showDropdown && showSuggestions && (
        <div ref={dropdownRef} className={styles.dropdown}>
          {suggestions.length > 0 ? (
            <ul className={styles.suggestionsList}>
              {suggestions.map((suggestion, index) => (
                <li
                  key={index}
                  className={`${styles.suggestionItem} ${
                    index === activeIndex ? styles.active : ''
                  }`}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => handleSuggestionClick(suggestion)}
                >
                  <span className={styles.suggestionIcon}>✓</span>
                  {suggestion}
                </li>
              ))}
            </ul>
          ) : query && query.length >= 2 ? (
            <div className={styles.noSuggestions}>
              Natijalar topilmadi
            </div>
          ) : null}
        </div>
      )}

      {/* Results summary */}
      {query && results && (
        <div className={styles.resultsSummary}>
          {Object.entries(results).map(([modelName, data]) => (
            data.items && data.items.length > 0 && (
              <div key={modelName} className={styles.resultCategory}>
                <strong>{modelName}:</strong> {data.items.length} natija
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}

export default SearchBar;
