/**
 * usePayment Hook
 * React hook for handling payment operations
 */

import { useState, useEffect, useCallback } from 'react';
import PaymentService from '../services/PaymentService';

/**
 * Hook for handling payment operations
 * @param {Object} options - Hook options
 * @returns {Object} - Payment state and methods
 */
export function usePayment(options = {}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [paymentStatus, setPaymentStatus] = useState(null);
  const [checkoutUrl, setCheckoutUrl] = useState(null);

  const {
    autoPolling = false,
    pollingInterval = 2000,
    maxPollingAttempts = 60
  } = options;

  /**
   * Initiate payment for invoice
   */
  const initiatePayment = useCallback(async (invoiceId) => {
    try {
      setLoading(true);
      setError(null);

      const result = await PaymentService.initiatePayment(invoiceId);

      if (result.success) {
        setCheckoutUrl(result.checkout_url);
        setPaymentStatus('initiated');

        // Start auto-polling if enabled
        if (autoPolling) {
          pollPaymentStatus(invoiceId);
        }

        return result;
      } else {
        throw new Error(result.error || 'Failed to initiate payment');
      }
    } catch (err) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage);
      console.error('Payment initiation error:', errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [autoPolling]);

  /**
   * Check payment status
   */
  const checkPaymentStatus = useCallback(async (invoiceId) => {
    try {
      setLoading(true);
      const status = await PaymentService.getPaymentStatus(invoiceId);
      setPaymentStatus(status);
      return status;
    } catch (err) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage);
      console.error('Error checking payment status:', errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Poll payment status until completion
   */
  const pollPaymentStatus = useCallback(async (invoiceId) => {
    try {
      setLoading(true);
      const result = await PaymentService.pollPaymentStatus(
        invoiceId,
        maxPollingAttempts,
        pollingInterval
      );
      setPaymentStatus(result);
      return result;
    } catch (err) {
      const errorMessage = err.message;
      setError(errorMessage);
      console.error('Error polling payment:', errorMessage);
    } finally {
      setLoading(false);
    }
  }, [maxPollingAttempts, pollingInterval]);

  /**
   * Cancel payment
   */
  const cancelPayment = useCallback(async (invoiceId) => {
    try {
      setLoading(true);
      setError(null);

      const result = await PaymentService.cancelPayment(invoiceId);
      setPaymentStatus('cancelled');
      setCheckoutUrl(null);

      return result;
    } catch (err) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage);
      console.error('Payment cancellation error:', errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Renew subscription
   */
  const renewSubscription = useCallback(async (subscriptionId) => {
    try {
      setLoading(true);
      setError(null);

      const result = await PaymentService.renewSubscription(subscriptionId);

      if (result.success) {
        setCheckoutUrl(result.checkout_url);
        setPaymentStatus('initiated');
        return result;
      } else {
        throw new Error(result.error || 'Failed to renew subscription');
      }
    } catch (err) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage);
      console.error('Subscription renewal error:', errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Redirect to payment provider
   */
  const redirectToPayment = useCallback(() => {
    if (checkoutUrl) {
      PaymentService.redirectToClick(checkoutUrl);
    } else {
      setError('Checkout URL not available');
    }
  }, [checkoutUrl]);

  /**
   * Handle payment callback from URL parameters
   */
  const handleCallback = useCallback(async (params) => {
    try {
      setLoading(true);
      const result = await PaymentService.handlePaymentCallback(params);
      setPaymentStatus(result);
      return result;
    } catch (err) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage);
      console.error('Payment callback error:', errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Clear payment state
   */
  const clearPayment = useCallback(() => {
    setPaymentStatus(null);
    setCheckoutUrl(null);
    setError(null);
  }, []);

  return {
    // State
    loading,
    error,
    paymentStatus,
    checkoutUrl,

    // Methods
    initiatePayment,
    checkPaymentStatus,
    pollPaymentStatus,
    cancelPayment,
    renewSubscription,
    redirectToPayment,
    handleCallback,
    clearPayment,

    // Helpers
    isPaymentInProgress: () => PaymentService.isPaymentInProgress(paymentStatus),
    isPaymentCompleted: () => PaymentService.isPaymentCompleted(paymentStatus)
  };
}

/**
 * Hook for handling subscription renewal
 */
export function useSubscriptionRenewal() {
  const payment = usePayment({ autoPolling: true });

  const renewSubscription = useCallback(async (subscriptionId) => {
    try {
      return await payment.renewSubscription(subscriptionId);
    } catch (err) {
      console.error('Subscription renewal failed:', err);
      throw err;
    }
  }, [payment]);

  return {
    ...payment,
    renewSubscription
  };
}

/**
 * Hook for payment status polling
 */
export function usePaymentStatusPoller(invoiceId, options = {}) {
  const [status, setStatus] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState(null);

  const {
    interval = 2000,
    enabled = true,
    onComplete = null,
    onError = null
  } = options;

  useEffect(() => {
    if (!enabled || !invoiceId) {
      return;
    }

    setIsPolling(true);
    const startTime = Date.now();
    const timeout = 5 * 60 * 1000; // 5 minutes

    const poll = async () => {
      try {
        const paymentStatus = await PaymentService.getPaymentStatus(invoiceId);
        setStatus(paymentStatus);

        // Check if payment is completed
        if (PaymentService.isPaymentCompleted(paymentStatus)) {
          setIsPolling(false);
          onComplete?.(paymentStatus);
        } else if (Date.now() - startTime > timeout) {
          // Timeout after 5 minutes
          setIsPolling(false);
          setError('Payment status check timeout');
          onError?.('timeout');
        } else {
          // Continue polling
          setTimeout(poll, interval);
        }
      } catch (err) {
        setError(err.message);
        onError?.(err);
        console.error('Error polling payment status:', err);
      }
    };

    poll();
  }, [invoiceId, interval, enabled, onComplete, onError]);

  return {
    status,
    isPolling,
    error
  };
}
