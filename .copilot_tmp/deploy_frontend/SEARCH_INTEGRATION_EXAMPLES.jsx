/**
 * Search System Integration Guide for React
 * Complete examples and patterns for using search in your components
 */

// ============================================================================
// 1. BASIC SEARCH INTEGRATION
// ============================================================================

import React from 'react';
import { useSearch } from '@/hooks/useSearch';
import SearchBar from '@/components/SearchBar';
import SearchResults from '@/components/SearchResults';

/**
 * Simple search page with autocomplete and results
 */
function BasicSearchExample() {
  const {
    query,
    results,
    suggestions,
    loading,
    error,
    handleQueryChange,
  } = useSearch();

  return (
    <div className="search-container">
      <h1>Qidiruv</h1>
      
      <SearchBar
        placeholder="Shifokor, klinika, bemor qidiring..."
        onResultsChange={(results) => {
          // Triggered when results update
          console.log('Results changed:', results);
        }}
        onSearch={(query) => {
          // Triggered when user searches
          console.log('User searched for:', query);
        }}
      />

      <SearchResults
        results={results}
        loading={loading}
        error={error}
        query={query}
        onResultClick={(item) => {
          console.log('User clicked:', item);
          // Navigate or handle result
        }}
      />
    </div>
  );
}

export default BasicSearchExample;

// ============================================================================
// 2. DOCTOR SEARCH WITH FILTERS
// ============================================================================

import { useDoctorSearch } from '@/hooks/useSearch';

/**
 * Doctor search with specialty and clinic filtering
 */
function DoctorSearchExample() {
  const {
    query,
    results,
    specialty,
    clinic,
    hasResults,
    handleQueryChange,
    handleSpecialtyChange,
    handleClinicChange,
  } = useDoctorSearch();

  return (
    <div className="doctor-search">
      <h2>Shifokor Izlash</h2>

      <form>
        <div className="search-group">
          <label>Nomi:</label>
          <input
            type="text"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="Shifokor nomini kiriting..."
          />
        </div>

        <div className="filter-group">
          <label>Ixtisoslik:</label>
          <select
            value={specialty}
            onChange={(e) => handleSpecialtyChange(e.target.value)}
          >
            <option value="">Hammasini tanlang</option>
            <option value="1">Kardiologiya</option>
            <option value="2">Nevrologiya</option>
            <option value="3">Ortopediya</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Klinika:</label>
          <select
            value={clinic}
            onChange={(e) => handleClinicChange(e.target.value)}
          >
            <option value="">Hammasini tanlang</option>
            <option value="1">Oltin Shifa</option>
            <option value="2">Med Center</option>
          </select>
        </div>
      </form>

      {hasResults && (
        <div className="results">
          {results?.doctors?.items?.map((doctor) => (
            <div key={doctor.id} className="doctor-card">
              <h3>{doctor.name}</h3>
              <p className="specialty">{doctor.specialty}</p>
              <p className="clinic">{doctor.clinic}</p>
              <p className="phone">{doctor.phone}</p>
              <button onClick={() => handleDoctorSelect(doctor)}>
                Qabul qabul qilish
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function handleDoctorSelect(doctor) {
  console.log('Selected doctor:', doctor);
  // Navigate to booking page or handle selection
}

// ============================================================================
// 3. MULTI-MODEL SEARCH
// ============================================================================

import { useMultiModelSearch } from '@/hooks/useSearch';

/**
 * Search across multiple models with model selection
 */
function MultiModelSearchExample() {
  const {
    query,
    results,
    selectedModels,
    loading,
    error,
    handleQueryChange,
    handleModelChange,
  } = useMultiModelSearch(['doctors', 'clinics', 'appointments']);

  const models = [
    { key: 'doctors', label: '👨‍⚕️ Shifokorlar' },
    { key: 'clinics', label: '🏥 Klinikalar' },
    { key: 'appointments', label: '📅 Qabullar' },
  ];

  return (
    <div className="multi-search">
      <h2>Barcha Bo'ylab Qidiruv</h2>

      <div className="search-input">
        <input
          type="text"
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Qidiruv..."
        />
      </div>

      <div className="model-filters">
        <label>Qidiruv turi:</label>
        {models.map((model) => (
          <label key={model.key} className="checkbox">
            <input
              type="checkbox"
              checked={selectedModels.includes(model.key)}
              onChange={() => handleModelChange(model.key)}
            />
            {model.label}
          </label>
        ))}
      </div>

      {loading && <p>Izlanmoqda...</p>}
      {error && <p className="error">{error}</p>}

      {results && (
        <div className="multi-results">
          <h3>Natijalar ({Object.keys(results).length} kategor.)</h3>
          {Object.entries(results).map(([model, data]) => (
            <div key={model}>
              <h4>{model} ({data?.items?.length || 0})</h4>
              {data?.items?.map((item) => (
                <div key={item.id} className="result-item">
                  {renderResultItem(model, item)}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function renderResultItem(model, item) {
  switch (model) {
    case 'doctors':
      return (
        <>
          <h5>{item.name}</h5>
          <p>{item.specialty}</p>
        </>
      );
    case 'clinics':
      return (
        <>
          <h5>{item.name}</h5>
          <p>{item.location}</p>
        </>
      );
    case 'appointments':
      return (
        <>
          <h5>{item.doctor} → {item.patient}</h5>
          <p>{new Date(item.date).toLocaleString()}</p>
        </>
      );
    default:
      return <p>{JSON.stringify(item)}</p>;
  }
}

// ============================================================================
// 4. AUTOCOMPLETE SEARCH (FOR INPUT FIELDS)
// ============================================================================

import { useAutocompleteSearch } from '@/hooks/useSearch';

/**
 * Simple autocomplete for input fields (doctors only)
 */
function DoctorAutocompleteExample() {
  const {
    query,
    suggestions,
    handleQueryChange,
    performSearch,
  } = useAutocompleteSearch('doctors');

  const [selectedDoctor, setSelectedDoctor] = React.useState(null);

  return (
    <div className="autocomplete">
      <label>Shifokorni tanlang:</label>
      
      <div className="input-wrapper">
        <input
          type="text"
          value={query}
          onChange={(e) => handleQueryChange(e.target.value)}
          placeholder="Shifokor nomini yozing..."
          autoComplete="off"
        />
        
        {suggestions.length > 0 && (
          <ul className="suggestions-list">
            {suggestions.map((suggestion, idx) => (
              <li
                key={idx}
                onClick={() => {
                  handleQueryChange(suggestion);
                  setSelectedDoctor(suggestion);
                }}
              >
                {suggestion}
              </li>
            ))}
          </ul>
        )}
      </div>

      {selectedDoctor && (
        <div className="selected">
          <p>Tanlangan: {selectedDoctor}</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 5. SEARCH IN MODAL/DIALOG
// ============================================================================

/**
 * Search inside a modal dialog for selecting items
 */
function ModalSearchExample() {
  const [isOpen, setIsOpen] = React.useState(false);
  const { results, handleQueryChange } = useSearch();

  return (
    <>
      <button onClick={() => setIsOpen(true)}>Shifokor Tanlash</button>

      {isOpen && (
        <div className="modal-overlay" onClick={() => setIsOpen(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Shifokor Tanlash</h2>
              <button className="close" onClick={() => setIsOpen(false)}>
                ✕
              </button>
            </div>

            <div className="modal-body">
              <input
                type="text"
                onChange={(e) => handleQueryChange(e.target.value)}
                placeholder="Shifokor izlash..."
              />

              <div className="modal-results">
                {results?.doctors?.items?.map((doctor) => (
                  <div
                    key={doctor.id}
                    className="modal-result-item"
                    onClick={() => {
                      onDoctorSelect(doctor);
                      setIsOpen(false);
                    }}
                  >
                    <div className="result-name">{doctor.name}</div>
                    <div className="result-meta">
                      {doctor.specialty} • {doctor.clinic}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function onDoctorSelect(doctor) {
  console.log('Selected:', doctor);
  // Handle doctor selection
}

// ============================================================================
// 6. SEARCH WITH ADVANCED FILTERS
// ============================================================================

/**
 * Search with advanced filtering options
 */
function AdvancedSearchExample() {
  const [filters, setFilters] = React.useState({
    query: '',
    models: ['doctors', 'clinics'],
    rating: 4,
    availability: true,
    clinic_id: null,
  });

  const [results, setResults] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/v1/search/?q=${filters.query}&models=${filters.models.join(',')}`
      );
      const data = await response.json();
      
      // Apply additional filters
      const filtered = {
        ...data.results,
        doctors: {
          ...data.results.doctors,
          items: (data.results.doctors?.items || []).filter((d) => {
            const matchesRating = !filters.rating || d.rating >= filters.rating;
            const matchesClinic = !filters.clinic_id || d.clinic_id === filters.clinic_id;
            return matchesRating && matchesClinic;
          }),
        },
      };
      setResults(filtered);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="advanced-search">
      <h2>Qo'shimcha Filtrlar Bilan Qidiruv</h2>

      <div className="filters-panel">
        <div className="filter">
          <label>Qidiruv so'zi:</label>
          <input
            type="text"
            value={filters.query}
            onChange={(e) => setFilters({ ...filters, query: e.target.value })}
          />
        </div>

        <div className="filter">
          <label>Minimum Reyting:</label>
          <select
            value={filters.rating}
            onChange={(e) => setFilters({ ...filters, rating: Number(e.target.value) })}
          >
            <option value={0}>Hammasi</option>
            <option value={3}>3+ ⭐</option>
            <option value={4}>4+ ⭐</option>
            <option value={5}>5 ⭐</option>
          </select>
        </div>

        <div className="filter">
          <label>Mavjud shans:</label>
          <input
            type="checkbox"
            checked={filters.availability}
            onChange={(e) => setFilters({ ...filters, availability: e.target.checked })}
          />
        </div>

        <button onClick={handleSearch} disabled={loading}>
          {loading ? 'Izlanmoqda...' : 'Qidiruv'}
        </button>
      </div>

      {results && (
        <div className="results">
          {/* Display results */}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 7. SEARCH RESULTS AS TABLE
// ============================================================================

/**
 * Display search results in a table format
 */
function TableSearchExample() {
  const { results, handleQueryChange } = useSearch();

  return (
    <div className="table-search">
      <input
        type="text"
        onChange={(e) => handleQueryChange(e.target.value)}
        placeholder="Qidiruv..."
      />

      {results?.doctors?.items && (
        <table className="results-table">
          <thead>
            <tr>
              <th>Nomi</th>
              <th>Ixtisoslik</th>
              <th>Klinika</th>
              <th>Telefon</th>
              <th>Reyting</th>
            </tr>
          </thead>
          <tbody>
            {results.doctors.items.map((doctor) => (
              <tr key={doctor.id}>
                <td>{doctor.name}</td>
                <td>{doctor.specialty}</td>
                <td>{doctor.clinic}</td>
                <td>{doctor.phone}</td>
                <td>{'⭐'.repeat(Math.round(doctor.rating || 0))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ============================================================================
// 8. SEARCH WITH CACHING AWARENESS
// ============================================================================

/**
 * Search with cache hit indication
 */
function CachedSearchExample() {
  const [lastResult, setLastResult] = React.useState(null);
  const { results: searchResults } = useSearch();

  React.useEffect(() => {
    if (searchResults) {
      setLastResult({
        ...searchResults,
        cached: true,  // In real impl, would come from API
        timestamp: new Date(),
      });
    }
  }, [searchResults]);

  return (
    <div className="cached-search">
      {lastResult?.cached && (
        <div className="cache-indicator">
          ⚡ Keshlangan natija ({lastResult.timestamp.toLocaleTimeString()})
        </div>
      )}
      {/* Show results */}
    </div>
  );
}

// ============================================================================
// 9. SEARCH WITH RECENT SEARCHES
// ============================================================================

/**
 * Show recent searches in a sidebar
 */
function RecentSearchesExample() {
  const [recentSearches, setRecentSearches] = React.useState([]);
  const { query, handleQueryChange } = useSearch();

  const handleSearch = (searchQuery) => {
    handleQueryChange(searchQuery);
    
    // Add to recent searches
    setRecentSearches((prev) => [
      searchQuery,
      ...prev.filter((s) => s !== searchQuery),
    ].slice(0, 10));
  };

  React.useEffect(() => {
    // Load from localStorage
    const saved = JSON.parse(localStorage.getItem('recentSearches') || '[]');
    setRecentSearches(saved);
  }, []);

  React.useEffect(() => {
    // Save to localStorage
    localStorage.setItem('recentSearches', JSON.stringify(recentSearches));
  }, [recentSearches]);

  return (
    <div className="recent-searches">
      <h3>So'nggi Qidiruvlar</h3>
      <ul>
        {recentSearches.map((search) => (
          <li key={search} onClick={() => handleSearch(search)}>
            {search}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================================
// 10. SEARCH IN PAGE HEADER/NAVBAR
// ============================================================================

/**
 * Integrated search in page header
 */
function HeaderSearchExample() {
  const [isExpanded, setIsExpanded] = React.useState(false);

  return (
    <header className="navbar">
      <div className="navbar-content">
        <div className="logo">Hospitoll</div>

        <div className={`search-container ${isExpanded ? 'expanded' : ''}`}>
          <SearchBar
            placeholder="Qidiruv..."
            onResultsChange={() => setIsExpanded(true)}
            showSuggestions={true}
          />
          {isExpanded && (
            <SearchResults
              results={null}
              loading={false}
              error={null}
              query=""
              onResultClick={() => setIsExpanded(false)}
            />
          )}
        </div>

        <div className="navbar-actions">
          {/* Other navbar items */}
        </div>
      </div>
    </header>
  );
}

// ============================================================================
// EXPORT ALL EXAMPLES
// ============================================================================

export {
  BasicSearchExample,
  DoctorSearchExample,
  MultiModelSearchExample,
  DoctorAutocompleteExample,
  ModalSearchExample,
  AdvancedSearchExample,
  TableSearchExample,
  CachedSearchExample,
  RecentSearchesExample,
  HeaderSearchExample,
};
