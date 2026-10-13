/**
 * MetricsGrid - Display metrics in a responsive grid
 */

import React from 'react';
import styles from './MetricsGrid.module.css';

function MetricsGrid({ metrics = {} }) {
  const metricsList = [
    { label: 'Jami Qabullar', value: metrics.total_appointments || 0, icon: '📅' },
    { label: 'Tugatilgan', value: metrics.completed_appointments || 0, icon: '✅' },
    { label: 'Bekor qilingan', value: metrics.cancelled_appointments || 0, icon: '❌' },
    { label: 'Ko\'rsatilmagan', value: metrics.no_show_appointments || 0, icon: '👻' },
    {
      label: 'Kunlik O\'rtacha',
      value: (metrics.average_appointments_per_day || 0).toFixed(1),
      icon: '📊',
    },
    {
      label: 'Pik Soat',
      value: metrics.peak_appointment_hour ? `${metrics.peak_appointment_hour}:00` : 'N/A',
      icon: '⏰',
    },
    {
      label: 'Shifokor Foydalanish',
      value: (metrics.doctor_utilization || 0).toFixed(1),
      icon: '👨‍⚕️',
    },
    {
      label: 'Bemor Saqlanish',
      value: `${(metrics.patient_retention_rate || 0).toFixed(1)}%`,
      icon: '📈',
    },
  ];

  return (
    <div className={styles.grid}>
      {metricsList.map((metric, index) => (
        <div key={index} className={styles.metricItem}>
          <div className={styles.icon}>{metric.icon}</div>
          <div className={styles.content}>
            <div className={styles.label}>{metric.label}</div>
            <div className={styles.value}>{metric.value}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export default MetricsGrid;
