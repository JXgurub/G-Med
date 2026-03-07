/**
 * AnalyticsDashboard - Main dashboard component
 * Real-time analytics and statistics for clinics
 * Fully responsive for mobile, tablet, and desktop
 */

import React, { useState } from 'react';
import styles from './AnalyticsDashboard.module.css';
import DashboardCard from './DashboardCard';
import MetricsGrid from './MetricsGrid';
import ChartsPanel from './ChartsPanel';
import TrendChart from './TrendChart';
import useAnalytics from '../hooks/useAnalytics';

function AnalyticsDashboard({ clinicId, title = 'Klinika Analitikasi' }) {
  const [dateRange, setDateRange] = useState('month');
  const [activeTab, setActiveTab] = useState('overview');

  // Use analytics hook for data fetching and caching
  const { data: dashboardData, loading, error, refetch } = useAnalytics(
    clinicId,
    {
      endpoint: 'dashboard',
      refetchInterval: 60000, // 1 minute
      cacheTimeout: 60000, // 1 minute cache
      enabled: !!clinicId,
    }
  );

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingState}>
          <div className={styles.spinner}></div>
          <p>Toplamalar yuklanmoqda...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.errorState}>
          <span>⚠️</span>
          <p>Xato: {error}</p>
          <button onClick={refetch} className={styles.retryButton}>
            Qayta urinish
          </button>
        </div>
      </div>
    );
  }

  if (!dashboardData) {
    return null;
  }

  const overview = dashboardData.overview || {};
  const metrics = dashboardData.metrics || {};
  const patients = dashboardData.patients || {};
  const revenue = dashboardData.revenue || {};
  const health = dashboardData.health || {};

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h1 className={styles.title}>{title}</h1>
          <p className={styles.subtitle}>{overview.clinic_name}</p>
        </div>

        <div className={styles.controls}>
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className={styles.dateRangeSelect}
          >
            <option value="week">Bu hafta</option>
            <option value="month">Bu oy</option>
            <option value="quarter">Chorak</option>
            <option value="year">Yil</option>
          </select>

          <button
            onClick={refetch}
            className={styles.refreshButton}
            title="Qayta yuklash"
          >
            🔄
          </button>
        </div>
      </div>

      {/* Tab Navigation (Mobile) */}
      <div className={styles.tabNavigation}>
        {[
          { id: 'overview', label: 'Ko\'rikma', icon: '📊' },
          { id: 'metrics', label: 'Ko\'rsatkichlar', icon: '📈' },
          { id: 'revenue', label: 'Daromad', icon: '💰' },
          { id: 'health', label: 'Tizim', icon: '⚙️' },
        ].map((tab) => (
          <button
            key={tab.id}
            className={`${styles.tabButton} ${activeTab === tab.id ? styles.activeTab : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className={styles.tabIcon}>{tab.icon}</span>
            <span className={styles.tabLabel}>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className={styles.content}>
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>📊 Umumiy Ko'rikma</div>

            <div className={styles.cardsGrid}>
              <DashboardCard
                title="Jami Shifokorlar"
                value={overview.total_doctors || 0}
                icon="👨‍⚕️"
                color="blue"
              />
              <DashboardCard
                title="Jami Bemorlar"
                value={overview.total_patients || 0}
                icon="👥"
                color="green"
              />
              <DashboardCard
                title="Bugungi Qabullar"
                value={overview.total_appointments || 0}
                icon="📅"
                color="orange"
              />
              <DashboardCard
                title="Daromad"
                value={`$${(overview.total_revenue || 0).toLocaleString()}`}
                icon="💰"
                color="purple"
              />
            </div>

            {/* Key Indicators */}
            <div className={styles.indicatorsSection}>
              <div className={styles.indicator}>
                <span className={styles.indicatorLabel}>Rating:</span>
                <span className={styles.indicatorValue}>
                  {'⭐'.repeat(Math.round(overview.avg_rating || 0))}
                  {` (${overview.avg_rating || 0})`}
                </span>
              </div>
              <div className={styles.indicator}>
                <span className={styles.indicatorLabel}>Tugatish Darajasi:</span>
                <span className={styles.indicatorValue}>
                  {(overview.completion_rate || 0).toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Metrics Tab */}
        {activeTab === 'metrics' && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>📈 Ko'rsatkichlar</div>
            <MetricsGrid metrics={metrics} />
          </div>
        )}

        {/* Revenue Tab */}
        {activeTab === 'revenue' && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>💰 Daromad Tahlili</div>
            <div className={styles.revenueSection}>
              <div className={styles.revenueSummary}>
                <div className={styles.revenueCard}>
                  <span>Jami Daromad</span>
                  <strong>${(revenue.total_revenue || 0).toLocaleString()}</strong>
                </div>
                <div className={styles.revenueCard}>
                  <span>Tranzaksiyalar</span>
                  <strong>{revenue.total_transactions || 0}</strong>
                </div>
                <div className={styles.revenueCard}>
                  <span>Ortalama</span>
                  <strong>${(revenue.average_transaction || 0).toLocaleString()}</strong>
                </div>
              </div>

              <div className={styles.paymentStatus}>
                <h4>To'lov Holati</h4>
                <div className={styles.statusItem}>
                  <span>✓ Tugatilgan: {revenue.successful_payments || 0}</span>
                </div>
                <div className={styles.statusItem}>
                  <span>⏳ Kutilmoqda: {revenue.pending_payments || 0}</span>
                </div>
                <div className={styles.statusItem}>
                  <span>✗ Muvaffaqiyatsiz: {revenue.failed_payments || 0}</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Health Tab */}
        {activeTab === 'health' && (
          <div className={styles.section}>
            <div className={styles.sectionTitle}>⚙️ Tizim Sog'ligi</div>
            <div className={styles.healthSection}>
              <div className={styles.healthItem}>
                <span>Faol Shifokorlar:</span>
                <strong>{health.active_doctors || 0}</strong>
              </div>
              <div className={styles.healthItem}>
                <span>Bu hafta qabullar:</span>
                <strong>{health.appointments_this_week || 0}</strong>
              </div>
              <div className={styles.healthItem}>
                <span>To'lov Tizimi:</span>
                <strong className={styles[`status_${health.payment_status || 'OK'}`]}>
                  {health.payment_status || 'OK'}
                </strong>
              </div>
              <div className={styles.healthItem}>
                <span>API Javob Vaqti:</span>
                <strong>{health.api_response_time || '< 100ms'}</strong>
              </div>
              <div className={styles.healthItem}>
                <span>Cache Hit Rate:</span>
                <strong>{health.cache_hit_rate || 0}%</strong>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Charts Section (Desktop Only) */}
      {activeTab === 'overview' && (
        <div className={styles.chartsSection}>
          <ChartsPanel dashboardData={dashboardData} />
        </div>
      )}
    </div>
  );
}

export default AnalyticsDashboard;
