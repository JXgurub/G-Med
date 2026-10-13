/**
 * Payment Processing Service
 * Handles payment API interactions with Click/Stripe
 */

import axios from 'axios';
import { API_BASE_URL } from './api';

const API_ENDPOINT = `${API_BASE_URL}/payments`;

class PaymentService {
  /**
   * Initiate payment for an invoice
   * @param {number} invoiceId - Invoice ID
   * @returns {Promise<Object>} - Payment data with checkout URL
   */
  static async initiatePayment(invoiceId) {
    try {
      const response = await axios.post(
        `${API_ENDPOINT}/invoice-payments/${invoiceId}/initiate-payment/`
      );
      return response.data;
    } catch (error) {
      console.error('Error initiating payment:', error);
      throw error;
    }
  }

  /**
   * Get payment status for invoice
   * @param {number} invoiceId - Invoice ID
   * @returns {Promise<Object>} - Payment status
   */
  static async getPaymentStatus(invoiceId) {
    try {
      const response = await axios.get(
        `${API_ENDPOINT}/invoice-payments/${invoiceId}/payment-status/`
      );
      return response.data;
    } catch (error) {
      console.error('Error getting payment status:', error);
      throw error;
    }
  }

  /**
   * Cancel pending payment
   * @param {number} invoiceId - Invoice ID
   * @returns {Promise<Object>} - Cancellation result
   */
  static async cancelPayment(invoiceId) {
    try {
      const response = await axios.post(
        `${API_ENDPOINT}/invoice-payments/${invoiceId}/cancel-payment/`
      );
      return response.data;
    } catch (error) {
      console.error('Error cancelling payment:', error);
      throw error;
    }
  }

  /**
   * Renew subscription with payment
   * @param {number} subscriptionId - Subscription ID
   * @returns {Promise<Object>} - Payment data
   */
  static async renewSubscription(subscriptionId) {
    try {
      const response = await axios.post(
        `${API_ENDPOINT}/renew-subscription/`,
        { subscription_id: subscriptionId }
      );
      return response.data;
    } catch (error) {
      console.error('Error renewing subscription:', error);
      throw error;
    }
  }

  /**
   * Redirect to Click payment
   * @param {string} checkoutUrl - Click checkout URL
   */
  static redirectToClick(checkoutUrl) {
    if (checkoutUrl) {
      window.location.href = checkoutUrl;
    }
  }

  /**
   * Handle payment callback
   * @param {Object} params - URL parameters
   * @returns {Promise<Object>} - Callback result
   */
  static async handlePaymentCallback(params) {
    try {
      const response = await axios.get(
        `${API_ENDPOINT}/callback/`,
        { params }
      );
      return response.data;
    } catch (error) {
      console.error('Error handling payment callback:', error);
      throw error;
    }
  }

  /**
   * Initialize Click payment widget
   * @param {Object} options - Widget options
   * @returns {Object} - Click widget instance
   */
  static initializeClickWidget(options) {
    if (typeof window.Click !== 'undefined') {
      return new window.Click(options);
    }
    console.warn('Click widget not loaded');
    return null;
  }

  /**
   * Format amount for display (UZS)
   * @param {number} amount - Amount in som
   * @returns {string} - Formatted amount
   */
  static formatAmount(amount) {
    return new Intl.NumberFormat('uz-UZ', {
      style: 'currency',
      currency: 'UZS'
    }).format(amount);
  }

  /**
   * Check if payment is in progress
   * @param {Object} paymentData - Payment data object
   * @returns {boolean}
   */
  static isPaymentInProgress(paymentData) {
    return paymentData?.payment_status === 'pending_payment' ||
           paymentData?.payment_status === 'initiated';
  }

  /**
   * Check if payment is completed
   * @param {Object} paymentData - Payment data object
   * @returns {boolean}
   */
  static isPaymentCompleted(paymentData) {
    return paymentData?.payment_status === 'completed' ||
           paymentData?.payment_status === 'paid';
  }

  /**
   * Poll payment status
   * @param {number} invoiceId - Invoice ID
   * @param {number} maxAttempts - Maximum polling attempts (default: 60)
   * @param {number} interval - Polling interval in ms (default: 2000)
   * @returns {Promise<Object>} - Final payment status
   */
  static async pollPaymentStatus(invoiceId, maxAttempts = 60, interval = 2000) {
    let attempts = 0;

    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const status = await this.getPaymentStatus(invoiceId);

          if (this.isPaymentCompleted(status)) {
            resolve(status);
          } else if (attempts >= maxAttempts) {
            reject(new Error('Payment status check timeout'));
          } else {
            attempts++;
            setTimeout(poll, interval);
          }
        } catch (error) {
          console.error('Error polling payment status:', error);
          if (attempts >= maxAttempts) {
            reject(error);
          } else {
            attempts++;
            setTimeout(poll, interval);
          }
        }
      };

      poll();
    });
  }
}

export default PaymentService;
