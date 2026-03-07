/**
 * ChartsPanel - Display analytics charts
 * Desktop-focused with mobile fallback
 */

import React from 'react';
import styles from './ChartsPanel.module.css';

function ChartsPanel({ dashboardData = {} }) {
  const trends = dashboardData.trends || {};
  const revenue = dashboardData.revenue || {};

  // Simple bar chart renderer
  const renderSimpleChart = (data, maxValue) => {
    return (
      <div className={styles.chartBars}>
        {data.map((item, idx) => (
          <div key={idx} className={styles.chartBar}>
            <div
              className={styles.bar}
              style={{ height: `${(item.value / maxValue) * 100}%` }}
            ></div>
            <span className={styles.label}>{item.label}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className={styles.chartsGrid}>
      {/* Appointment Trends Chart */}
      {trends.trend_data && trends.trend_data.length > 0 && (
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>📅 Qabul Tendensiyalari</h3>
          <div className={styles.chartContainer}>
            {renderSimpleChart(
              trends.trend_data.map((d) => ({
                label: new Date(d.date_only).toLocaleDateString('uz-UZ', {
                  month: 'short',
                  day: 'numeric',
                }),
                value: d.count,
              })),
              Math.max(...trends.trend_data.map((d) => d.count), 1)
            )}
          </div>
          <div className={styles.chartStats}>
            <span>O'rtacha: {trends.average_daily_appointments?.toFixed(1)}</span>
            <span>Jami: {trends.total_trend_appointments}</span>
          </div>
        </div>
      )}

      {/* Revenue Distribution Chart */}
      {revenue.revenue_by_doctor && revenue.revenue_by_doctor.length > 0 && (
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>💰 Shifokorlar bo'yicha Daromad</h3>
          <div className={styles.chartContainer}>
            {revenue.revenue_by_doctor.map((item, idx) => (
              <div key={idx} className={styles.revenueRow}>
                <span className={styles.doctorName}>{item.doctor}</span>
                <div className={styles.revenueBar}>
                  <div
                    className={styles.revenueFill}
                    style={{
                      width: `${(item.revenue / Math.max(...revenue.revenue_by_doctor.map((r) => r.revenue), 1)) * 100}%`,
                    }}
                  ></div>
                </div>
                <span className={styles.revenueAmount}>${item.revenue}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Payment Methods Pie Chart */}
      {revenue.payment_methods && (
        <div className={styles.chartCard}>
          <h3 className={styles.chartTitle}>💳 To'lov Usullari</h3>
          <div className={styles.pieChart}>
            <div className={styles.pieContainer}>
              <svg viewBox="0 0 100 100" className={styles.pieSvg}>
                {Object.entries(revenue.payment_methods).map((entry, idx) => {
                  const [method, percentage] = entry;
                  const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A'];
                  return null; // Simplified - just show list
                })}
              </svg>
            </div>
            <div className={styles.pieLegend}>
              {Object.entries(revenue.payment_methods).map(([method, percentage]) => (
                <div key={method} className={styles.legendItem}>
                  <span className={styles.legendDot}></span>
                  <span>{method}</span>
                  <span className={styles.percentage}>{percentage}%</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className={styles.chartCard}>
        <h3 className={styles.chartTitle}>⚡ Tezkor Info</h3>
        <div className={styles.statsGrid}>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Bugungi Daromad</span>
            <span className={styles.statValue}>${(revenue.total_revenue || 0).toLocaleString()}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Muvaffaqiyatli</span>
            <span className={styles.statValue}>{revenue.successful_payments || 0}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Ortalama</span>
            <span className={styles.statValue}>${(revenue.average_transaction || 0).toLocaleString()}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Kutilmoqda</span>
            <span className={styles.statValue}>{revenue.pending_payments || 0}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ChartsPanel;
