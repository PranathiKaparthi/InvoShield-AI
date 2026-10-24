/**
 * InvoShield AI - Centralized Currency Utility
 * 
 * Supports dynamic conversion and standard locale formatting:
 * - USD ($): en-US standard formatting (e.g., $1,500.00)
 * - INR (₹): en-IN standard formatting with Lakhs/Crores grouping (e.g., ₹1,24,500.00)
 */

export type CurrencyCode = 'USD' | 'INR';

export interface CurrencyConfig {
  code: CurrencyCode;
  name: string;
  symbol: string;
  locale: string;
  rateAgainstUSD: number; // 1 USD = rate
}

export const CURRENCY_CONFIGS: Record<CurrencyCode, CurrencyConfig> = {
  USD: {
    code: 'USD',
    name: 'US Dollar',
    symbol: '$',
    locale: 'en-US',
    rateAgainstUSD: 1.0,
  },
  INR: {
    code: 'INR',
    name: 'Indian Rupee',
    symbol: '₹',
    locale: 'en-IN',
    rateAgainstUSD: 83.0, // Standard configurable conversion baseline
  },
};

export const DEFAULT_CURRENCY: CurrencyCode = 'USD';

/**
 * Converts a base numeric amount (in USD) to the target currency.
 */
export function convertCurrency(
  amountInUSD: number | null | undefined,
  targetCurrency: CurrencyCode,
  customRate?: number
): number {
  if (amountInUSD === null || amountInUSD === undefined || isNaN(amountInUSD)) {
    return 0;
  }
  const rate = customRate ?? CURRENCY_CONFIGS[targetCurrency]?.rateAgainstUSD ?? 1.0;
  return amountInUSD * rate;
}

/**
 * Formats a base numeric amount (in USD) into a localized currency string.
 * Automatically applies conversion and proper locale grouping.
 */
export function formatCurrency(
  amountInUSD: number | null | undefined,
  currency: CurrencyCode = 'USD',
  fractionDigits: number = 2
): string {
  if (amountInUSD === null || amountInUSD === undefined || isNaN(amountInUSD)) {
    const symbol = CURRENCY_CONFIGS[currency]?.symbol || '$';
    return `${symbol}0.00`;
  }

  const convertedValue = convertCurrency(amountInUSD, currency);
  const config = CURRENCY_CONFIGS[currency] || CURRENCY_CONFIGS.USD;

  try {
    return new Intl.NumberFormat(config.locale, {
      style: 'currency',
      currency: config.code,
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(convertedValue);
  } catch (error) {
    const formattedNum = convertedValue.toLocaleString(config.locale, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    });
    return `${config.symbol}${formattedNum}`;
  }
}

/**
 * Helper to get the active currency symbol ($ or ₹)
 */
export function getCurrencySymbol(currency: CurrencyCode): string {
  return CURRENCY_CONFIGS[currency]?.symbol || '$';
}
