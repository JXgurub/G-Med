/**
 * TrendChart - Display appointment and revenue trends over time
 * Simple line chart implementation for responsive display
 */

import React from 'react';
import styles from './TrendChart.module.css';

function TrendChart({ data = [], title = 'Tendensiya', type = 'line', color = '#4CAF50' }) {
  if (!data || data.length === 0) {
    return (
      <div className={styles.trendContainer}>
        <h3 className={styles.title}>{title}</h3>
        <div className={styles.emptyState}>
          <span>📊 Ma'lumot yo'q</span>
        </div>
      </div>
    );
  }

  // Calculate max value for scaling
  const maxValue = Math.max(...data.map((d) => d.value || 0), 1);
  const minValue = Math.min(...data.map((d) => d.value || 0), 0);
  const range = maxValue - minValue || 1;

  // Normalize data for SVG (0-100 scale)
  const normalizedData = data.map((d) => ({
    ...d,
    normalized: ((d.value - minValue) / range) * 100,
  }));

  // Generate SVG path for line chart
  const generatePath = () => {
    const width = 100;
    const height = 80;
    const pointSpacing = width / (data.length - 1 || 1);

    let pathData = normalizedData
      .map((d, i) => {
        const x = i * pointSpacing;
        const y = height - (d.normalized * (height - 10)) / 100;
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');

    return pathData;
  };

  return (
    <div className={styles.trendContainer}>
      <h3 className={styles.title}>{title}</h3>

      <svg className={styles.chartSvg} viewBox="0 0 100 100" preserveAspectRatio="none">
        {/* Grid lines */}
        <line x1="0" y1="20" x2="100" y2="20" className={styles.gridLine} />
        <line x1="0" y1="40" x2="100" y2="40" className={styles.gridLine} />
        <line x1="0" y1="60" x2="100" y2="60" className={styles.gridLine} />

        {/* Area under curve (fill) */}
        {type === 'area' && (
          <defs>
            <linearGradient id={`gradient-${color}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0.05" />
            </linearGradient>
          </defs>
        )}

        {type === 'area' && (
          <path
            d={`${generatePath()} L 100 100 L 0 100 Z`}
            fill={`url(#gradient-${color})`}
            className={styles.areaFill}
          />
        )}

        {/* Line */}
        <path
          d={generatePath()}
          stroke={color}
          strokeWidth="1.5"
          fill="none"
          className={styles.trendLine}
        />

        {/* Data points */}
        {normalizedData.map((d, i) => {
          const pointSpacing = 100 / (data.length - 1 || 1);
          const x = i * pointSpacing;
          const y = 80 - (d.normalized * 70) / 100;

          return (
            <g key={i} className={styles.dataPoint}>
              <circle cx={x} cy={y} r="1.5" fill={color} />
            </g>
          );
        })}
      </svg>

      {/* Data Table / Legend */}
      <div className={styles.dataTable}>
        {normalizedData.map((d, i) => (
          <div key={i} className={styles.tableRow}>
            <span className={styles.label}>{d.label || `Point ${i + 1}`}</span>
            <span className={styles.value}>{d.value}</span>
            {i > 0 && (
              <span
                className={`${styles.change} ${d.value > normalizedData[i - 1].value ? styles.positive : styles.negative}`}
              >
                {d.value > normalizedData[i - 1].value ? '↑' : '↓'}
                {Math.abs(d.value - normalizedData[i - 1].value).toFixed(1)}
              </span>
            )}
          </div>
        ))}
      </div>

      {/* Summary Stats */}
      <div className={styles.stats}>
        <div className={styles.stat}>
          <span className={styles.statLabel}>O'rtacha</span>
          <span className={styles.statValue}>
            {(data.reduce((sum, d) => sum + (d.value || 0), 0) / data.length).toFixed(1)}
          </span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Max</span>
          <span className={styles.statValue}>{maxValue}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Min</span>
          <span className={styles.statValue}>{minValue}</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statLabel}>Jami</span>
          <span className={styles.statValue}>{data.reduce((sum, d) => sum + (d.value || 0), 0)}</span>
        </div>
      </div>
    </div>
  );
}

export default TrendChart;
