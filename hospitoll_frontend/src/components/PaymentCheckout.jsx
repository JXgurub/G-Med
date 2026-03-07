/**
 * PaymentCheckout Component
 * Handles payment initiation and status display
 */

import React, { useState, useEffect } from 'react';
import PaymentService from '@/services/PaymentService';
import { usePayment } from '@/hooks/usePayment';
import styles from './PaymentCheckout.module.css';

function PaymentCheckout({ invoiceId, amount, invoiceNumber, onSuccess, onCancel }) {
  const {
    loading,
    error,
    paymentStatus,
    checkoutUrl,
    initiatePayment,
    cancelPayment,
    redirectToPayment,
    clearPayment
  } = usePayment({ autoPolling: true, pollingInterval: 2000 });

  const [showDetails, setShowDetails] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('click');

  /**
   * Handle payment initiation
   */
  const handlePaymentClick = async () => {
    try {
      const result = await initiatePayment(invoiceId);
      if (result.success) {
        setTimeout(() => {
          redirectToPayment();
        }, 1500);
      }
    } catch (err) {
      console.error('Payment error:', err);
    }
  };

  /**
   * Handle payment cancellation
   */
  const handleCancelClick = async () => {
    try {
      await cancelPayment(invoiceId);
      if (onCancel) onCancel();
    } catch (err) {
      console.error('Cancellation error:', err);
    }
  };

  /**
   * Handle successful payment
   */
  useEffect(() => {
    if (PaymentService.isPaymentCompleted(paymentStatus)) {
      if (onSuccess) onSuccess(paymentStatus);
    }
  }, [paymentStatus, onSuccess]);

  /**
   * Check if payment is pending
   */
  const isPending = PaymentService.isPaymentInProgress(paymentStatus);
  const isCompleted = PaymentService.isPaymentCompleted(paymentStatus);

  return (
    <div className={styles.checkoutContainer}>
      {/* Header */}
      <div className={styles.header}>
        <h2>To'lovni Bajarish</h2>
        <p className={styles.subtitle}>Invoice #{invoiceNumber}</p>
      </div>

      {/* Amount Display */}
      <div className={styles.amountSection}>
        <div className={styles.amountLabel}>To'lov miqdori:</div>
        <div className={styles.amount}>
          {PaymentService.formatAmount(amount)}
        </div>
      </div>

      {/* Status Messages */}
      {error && (
        <div className={`${styles.alert} ${styles.alertError}`}>
          <span className={styles.alertIcon}>⚠️</span>
          <div>
            <div className={styles.alertTitle}>Xato</div>
            <div className={styles.alertMessage}>{error}</div>
          </div>
        </div>
      )}

      {isPending && (
        <div className={`${styles.alert} ${styles.alertInfo}`}>
          <span className={styles.alertIcon}>ℹ️</span>
          <div>
            <div className={styles.alertTitle}>To'lov jarayoni</div>
            <div className={styles.alertMessage}>
              Click orqali to'lovni bajaryotgan bo'lishingiz mumkin...
            </div>
          </div>
        </div>
      )}

      {isCompleted && (
        <div className={`${styles.alert} ${styles.alertSuccess}`}>
          <span className={styles.alertIcon}>✓</span>
          <div>
            <div className={styles.alertTitle}>To'lov muvaffaqiyatli</div>
            <div className={styles.alertMessage}>
              To'lov {paymentStatus.payment_confirmed_at} vaqtida qabul qilindi
            </div>
          </div>
        </div>
      )}

      {/* Payment Method Selection */}
      {!isPending && !isCompleted && (
        <div className={styles.methodSection}>
          <label className={styles.methodLabel}>To'lov usuli:</label>
          <div className={styles.methodOptions}>
            <label className={styles.radioLabel}>
              <input
                type="radio"
                value="click"
                checked={paymentMethod === 'click'}
                onChange={(e) => setPaymentMethod(e.target.value)}
                disabled={loading}
              />
              <span className={styles.radioText}>Click (Uzbekistan)</span>
            </label>

            <label className={styles.radioLabel}>
              <input
                type="radio"
                value="stripe"
                checked={paymentMethod === 'stripe'}
                onChange={(e) => setPaymentMethod(e.target.value)}
                disabled={loading}
              />
              <span className={styles.radioText}>Stripe (International)</span>
            </label>

            <label className={styles.radioLabel}>
              <input
                type="radio"
                value="bank"
                checked={paymentMethod === 'bank'}
                onChange={(e) => setPaymentMethod(e.target.value)}
                disabled={loading}
              />
              <span className={styles.radioText}>Bank o'tkazmasi</span>
            </label>
          </div>
        </div>
      )}

      {/* Invoice Details */}
      {showDetails && (
        <div className={styles.detailsSection}>
          <h4>Faktura tafsilotlari</h4>
          <div className={styles.detailRow}>
            <span>Faktura raqami:</span>
            <span>{invoiceNumber}</span>
          </div>
          <div className={styles.detailRow}>
            <span>Summa:</span>
            <span>{PaymentService.formatAmount(amount)}</span>
          </div>
          {paymentStatus && (
            <>
              <div className={styles.detailRow}>
                <span>To'lov statusu:</span>
                <span className={styles.statusBadge}>{paymentStatus.payment_status}</span>
              </div>
              {paymentStatus.payment_initiated_at && (
                <div className={styles.detailRow}>
                  <span>Boshlangan vaqti:</span>
                  <span>{new Date(paymentStatus.payment_initiated_at).toLocaleString('uz-UZ')}</span>
                </div>
              )}
              {paymentStatus.payment_confirmed_at && (
                <div className={styles.detailRow}>
                  <span>Tasdiqlangan vaqti:</span>
                  <span>{new Date(paymentStatus.payment_confirmed_at).toLocaleString('uz-UZ')}</span>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Toggle Details */}
      <button
        className={styles.detailsToggle}
        onClick={() => setShowDetails(!showDetails)}
      >
        {showDetails ? 'Tafsilotlarni yashirish' : 'Tafsilotlarni ko\'rish'}
      </button>

      {/* Actions */}
      <div className={styles.actions}>
        {!isPending && !isCompleted && (
          <>
            <button
              className={`${styles.button} ${styles.buttonPrimary}`}
              onClick={handlePaymentClick}
              disabled={loading}
            >
              {loading ? (
                <>
                  <span className={styles.spinner}></span>
                  Yuklanmoqda...
                </>
              ) : (
                <>
                  <span>💳 To\'lovni bajaring</span>
                  <span className={styles.amount}>{PaymentService.formatAmount(amount)}</span>
                </>
              )}
            </button>

            <button
              className={`${styles.button} ${styles.buttonSecondary}`}
              onClick={handleCancelClick}
              disabled={loading}
            >
              Bekor qilish
            </button>
          </>
        )}

        {isCompleted && (
          <button
            className={`${styles.button} ${styles.buttonSuccess}`}
            onClick={() => {
              clearPayment();
              if (onSuccess) onSuccess(paymentStatus);
            }}
          >
            ✓ Davom etish
          </button>
        )}
      </div>

      {/* Security Notice */}
      <div className={styles.security}>
        <span className={styles.securityIcon}>🔒</span>
        <span className={styles.securityText}>
          Sizning to'lovingiz xavfli Click xizmatida qayta kuruladi
        </span>
      </div>

      {/* Help Text */}
      <div className={styles.helpText}>
        <p>
          <strong>Nimani bilish kerak:</strong>
        </p>
        <ul>
          <li>To'lovingiz Click orqali xavfli tarzda qayta kuruladi</li>
          <li>Karta ma'lumotlari G-MED serverida saqlanmaydi</li>
          <li>To'lovning tasdiqlanishi 2-3 minut vaqt olishi mumkin</li>
          <li>Agar muammo bo'lsa, iltimos biz bilan bog'laning: support@hospitoll.uz</li>
        </ul>
      </div>
    </div>
  );
}

export default PaymentCheckout;
