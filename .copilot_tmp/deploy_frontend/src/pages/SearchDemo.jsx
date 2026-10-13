/**
 * SearchDemo Page
 * Demonstrates search functionality and usage of search hooks/components
 */

import React, { useState } from 'react';
import SearchBar from '@/components/SearchBar';
import SearchResults from '@/components/SearchResults';
import { useSearch } from '@/hooks/useSearch';
import { useDoctorSearch } from '@/hooks/useSearch';
import { useMultiModelSearch } from '@/hooks/useSearch';
import styles from './SearchDemo.module.css';

function SearchDemo() {
  const [demoMode, setDemoMode] = useState('basic'); // basic, doctors, multi
  const [selectedResult, setSelectedResult] = useState(null);

  // Mode 1: Basic search
  const basicSearch = useSearch();

  // Mode 2: Doctor search with filters
  const doctorSearch = useDoctorSearch();

  // Mode 3: Multi-model search
  const multiModelSearch = useMultiModelSearch(['doctors', 'clinics', 'appointments']);

  const handleResultClick = (item) => {
    setSelectedResult(item);
    console.log('Selected item:', item);
  };

  const renderModeContent = () => {
    switch (demoMode) {
      case 'basic':
        return (
          <div className={styles.demoSection}>
            <h3>Umumiy Qidiruv</h3>
            <p>Barcha model turlarida qidiruv</p>
            <SearchBar
              placeholder="Shifokor, klinika, bemor qidiring..."
              onResultsChange={(results) => console.log('Results:', results)}
              onSearch={(query) => console.log('Search:', query)}
              showSuggestions={true}
            />
            <SearchResults
              results={basicSearch.results}
              loading={basicSearch.loading}
              error={basicSearch.error}
              query={basicSearch.query}
              onResultClick={handleResultClick}
            />
          </div>
        );

      case 'doctors':
        return (
          <div className={styles.demoSection}>
            <h3>Shifokor Qidiruvini Filtrlagish</h3>
            <p>Ixtisoslik va klinikasi bo'yicha shifokor qidiruvini filtrlagish</p>

            <div className={styles.filterGroup}>
              <div className={styles.filterItem}>
                <label>Shifokor nomi:</label>
                <input
                  type="text"
                  value={doctorSearch.query}
                  onChange={(e) => doctorSearch.handleQueryChange(e.target.value)}
                  placeholder="Shifokor nomini kiriting..."
                  className={styles.input}
                />
              </div>

              <div className={styles.filterItem}>
                <label>Ixtisoslik:</label>
                <select
                  onChange={(e) => doctorSearch.handleSpecialtyChange(e.target.value)}
                  className={styles.select}
                >
                  <option value="">Hammasini tanlang</option>
                  <option value="1">Kardiologiya</option>
                  <option value="2">Nevrologiya</option>
                  <option value="3">Ortopediya</option>
                </select>
              </div>

              <div className={styles.filterItem}>
                <label>Klinika:</label>
                <select
                  onChange={(e) => doctorSearch.handleClinicChange(e.target.value)}
                  className={styles.select}
                >
                  <option value="">Hammasini tanlang</option>
                  <option value="1">Oltin Shifa</option>
                  <option value="2">Med Center</option>
                </select>
              </div>
            </div>

            {doctorSearch.hasResults && (
              <div className={styles.resultsList}>
                <h4>Shifokorlar ({doctorSearch.results?.doctors?.count || 0})</h4>
                {doctorSearch.results?.doctors?.items?.map((doctor) => (
                  <div key={doctor.id} className={styles.resultCard} onClick={() => handleResultClick(doctor)}>
                    <div className={styles.resultHeader}>
                      <h5>{doctor.name}</h5>
                      <span className={styles.specialty}>{doctor.specialty}</span>
                    </div>
                    <p>Klinika: {doctor.clinic}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      case 'multi':
        return (
          <div className={styles.demoSection}>
            <h3>Ko'p Modelni Qidiruv</h3>
            <p>Bir nechta model turlarida bir vaqtning o'zida qidiruv</p>

            <SearchBar
              placeholder="Qidiruv..."
              onResultsChange={multiModelSearch.searchWithModels}
              modelFilter={null}
              showSuggestions={true}
              showFilters={false}
            />

            <div className={styles.modelSelection}>
              <label>Qidiruv turi:</label>
              <div className={styles.checkboxGroup}>
                {['doctors', 'clinics', 'appointments'].map((model) => (
                  <label key={model} className={styles.checkbox}>
                    <input
                      type="checkbox"
                      checked={multiModelSearch.selectedModels.includes(model)}
                      onChange={() => multiModelSearch.handleModelChange(model)}
                    />
                    {model}
                  </label>
                ))}
              </div>
            </div>

            <SearchResults
              results={multiModelSearch.results}
              loading={multiModelSearch.loading}
              error={multiModelSearch.error}
              query={multiModelSearch.query}
              onResultClick={handleResultClick}
            />
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>🔍 Qidiruv Demo</h1>
        <p>Qidiruv funktsiyasini test qilish</p>
      </div>

      <div className={styles.modeSelector}>
        <button
          className={`${styles.modeButton} ${demoMode === 'basic' ? styles.active : ''}`}
          onClick={() => setDemoMode('basic')}
        >
          Umumiy Qidiruv
        </button>
        <button
          className={`${styles.modeButton} ${demoMode === 'doctors' ? styles.active : ''}`}
          onClick={() => setDemoMode('doctors')}
        >
          Shifokor Qidiruvini Filtrlagish
        </button>
        <button
          className={`${styles.modeButton} ${demoMode === 'multi' ? styles.active : ''}`}
          onClick={() => setDemoMode('multi')}
        >
          Ko'p Modelni Qidiruv
        </button>
      </div>

      <div className={styles.content}>
        {renderModeContent()}
      </div>

      {selectedResult && (
        <div className={styles.sidebar}>
          <h3>Tanlangan Natija</h3>
          <div className={styles.selectedItem}>
            <button
              className={styles.closeButton}
              onClick={() => setSelectedResult(null)}
            >
              ✕
            </button>
            <pre>{JSON.stringify(selectedResult, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

export default SearchDemo;
