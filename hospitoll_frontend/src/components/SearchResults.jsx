/**
 * SearchResults Component
 * Displays search results in organized categories
 */

import React from 'react';
import styles from './SearchResults.module.css';

function SearchResults({ results, loading, error, query, onResultClick }) {
  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <div className={styles.spinner}></div>
          <p>Izlanmoqda...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <span>⚠️</span>
          <p>{error}</p>
        </div>
      </div>
    );
  }

  if (!results || !query) {
    return null;
  }

  const hasResults = Object.values(results).some(r => r.items?.length > 0);

  if (!hasResults) {
    return (
      <div className={styles.container}>
        <div className={styles.noResults}>
          <span>🔍</span>
          <p>"{query}" borasida natija topilmadi</p>
        </div>
      </div>
    );
  }

  const renderDoctorResult = (item) => (
    <div key={item.id} className={styles.resultItem} onClick={() => onResultClick?.(item)}>
      <div className={styles.icon}>👨‍⚕️</div>
      <div className={styles.content}>
        <div className={styles.title}>{item.name}</div>
        <div className={styles.subtitle}>{item.specialty}</div>
        <div className={styles.meta}>
          {item.clinic && <span>{item.clinic}</span>}
          {item.phone && <span className={styles.phone}>{item.phone}</span>}
        </div>
      </div>
    </div>
  );

  const renderClinicResult = (item) => (
    <div key={item.id} className={styles.resultItem} onClick={() => onResultClick?.(item)}>
      <div className={styles.icon}>🏥</div>
      <div className={styles.content}>
        <div className={styles.title}>{item.name}</div>
        <div className={styles.subtitle}>{item.location}</div>
        <div className={styles.meta}>
          {item.doctors_count && <span>Shifokorlar: {item.doctors_count}</span>}
          {item.phone && <span>{item.phone}</span>}
        </div>
      </div>
    </div>
  );

  const renderPatientResult = (item) => (
    <div key={item.id} className={styles.resultItem} onClick={() => onResultClick?.(item)}>
      <div className={styles.icon}>👤</div>
      <div className={styles.content}>
        <div className={styles.title}>{item.name}</div>
        <div className={styles.meta}>
          {item.phone && <span>{item.phone}</span>}
          {item.email && <span>{item.email}</span>}
        </div>
      </div>
    </div>
  );

  const renderAppointmentResult = (item) => (
    <div key={item.id} className={styles.resultItem} onClick={() => onResultClick?.(item)}>
      <div className={styles.icon}>📅</div>
      <div className={styles.content}>
        <div className={styles.title}>
          {item.doctor} → {item.patient}
        </div>
        <div className={styles.meta}>
          <span>{new Date(item.date).toLocaleString('uz-UZ')}</span>
          <span className={styles.status}>{item.status}</span>
        </div>
      </div>
    </div>
  );

  const renderMedicalRecordResult = (item) => (
    <div key={item.id} className={styles.resultItem} onClick={() => onResultClick?.(item)}>
      <div className={styles.icon}>📋</div>
      <div className={styles.content}>
        <div className={styles.title}>{item.diagnosis}</div>
        <div className={styles.subtitle}>{item.patient}</div>
        <div className={styles.meta}>
          <span>{item.symptoms}</span>
          <span>{new Date(item.date).toLocaleDateString('uz-UZ')}</span>
        </div>
      </div>
    </div>
  );

  const renderPharmacyResult = (item) => (
    <div key={item.id} className={styles.resultItem} onClick={() => onResultClick?.(item)}>
      <div className={styles.icon}>💊</div>
      <div className={styles.content}>
        <div className={styles.title}>{item.name}</div>
        <div className={styles.subtitle}>{item.location}</div>
        <div className={styles.meta}>
          {item.phone && <span>{item.phone}</span>}
        </div>
      </div>
    </div>
  );

  const renderResults = (modelName, items) => {
    if (!items || items.length === 0) return null;

    const renderFunctions = {
      doctors: renderDoctorResult,
      clinics: renderClinicResult,
      patients: renderPatientResult,
      appointments: renderAppointmentResult,
      medical_records: renderMedicalRecordResult,
      pharmacies: renderPharmacyResult,
    };

    const renderFunction = renderFunctions[modelName] || ((item) => (
      <div key={item.id} className={styles.resultItem}>
        <div className={styles.content}>
          <div className={styles.title}>{JSON.stringify(item)}</div>
        </div>
      </div>
    ));

    return (
      <div key={modelName} className={styles.category}>
        <h3 className={styles.categoryTitle}>
          {getCategoryLabel(modelName)} ({items.length})
        </h3>
        <div className={styles.categoryItems}>
          {items.map(item => renderFunction(item))}
        </div>
      </div>
    );
  };

  const getCategoryLabel = (modelName) => {
    const labels = {
      doctors: '👨‍⚕️ Shifokorlar',
      clinics: '🏥 Klinikalar',
      patients: '👤 Bemorlar',
      appointments: '📅 Qabullar',
      medical_records: '📋 Tibbiy yozuvlar',
      pharmacies: '💊 Dorihanalar',
    };
    return labels[modelName] || modelName;
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <span className={styles.title}>
          "{query}" borasida natijalar
        </span>
        <span className={styles.totalCount}>
          Jami: {Object.values(results).reduce((sum, r) => sum + (r.items?.length || 0), 0)} natija
        </span>
      </div>

      <div className={styles.resultsContainer}>
        {Object.entries(results).map(([modelName, data]) =>
          renderResults(modelName, data.items)
        )}
      </div>
    </div>
  );
}

export default SearchResults;
