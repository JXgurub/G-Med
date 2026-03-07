/**
 * DashboardCard - Reusable card component for dashboard metrics
 * Mobile responsive with animation
 */

import React from 'react';
import styles from './DashboardCard.module.css';

function DashboardCard({ title, value, subtitle, icon, color = 'blue', onClick }) {
  return (
    <div
      className={`${styles.card} ${styles[`color_${color}`]}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
    >
      <div className={styles.header}>
        <span className={styles.icon}>{icon}</span>
        <h3 className={styles.title}>{title}</h3>
      </div>

      <div className={styles.content}>
        <div className={styles.value}>{value}</div>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      </div>

      <div className={styles.footer}>
        <span className={styles.indicator}></span>
      </div>
    </div>
  );
}

export default DashboardCard;
