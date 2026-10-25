import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  CurrencyCode,
  CURRENCY_CONFIGS,
  DEFAULT_CURRENCY,
  convertCurrency,
  toUSD,
  formatCurrency,
  getCurrencySymbol,
} from '../utils/currency';

interface CurrencyContextType {
  currency: CurrencyCode;
  setCurrency: (currency: CurrencyCode) => void;
  currencySymbol: string;
  exchangeRate: number;
  /** Format an amount for display. Pass the invoice's own currency so rupee invoices aren't read as dollars. */
  formatAmount: (amount: number | null | undefined, fractionDigits?: number, fromCurrency?: string) => string;
  convertAmount: (amountInUSD: number | null | undefined) => number;
}

const STORAGE_KEY = 'invoshield_currency';

const CurrencyContext = createContext<CurrencyContextType | undefined>(undefined);

export const CurrencyProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currency, setCurrencyState] = useState<CurrencyCode>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'USD' || saved === 'INR') {
        return saved;
      }
    } catch {
      // localStorage may not be available in some sandboxes
    }
    return DEFAULT_CURRENCY;
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, currency);
    } catch (e) {
      console.warn('Failed to save currency to localStorage:', e);
    }
  }, [currency]);

  const setCurrency = (newCurrency: CurrencyCode) => {
    setCurrencyState(newCurrency);
  };

  const formatAmount = (amount: number | null | undefined, fractionDigits: number = 2, fromCurrency: string = 'USD') => {
    return formatCurrency(toUSD(amount, fromCurrency || 'USD'), currency, fractionDigits);
  };

  const convertAmount = (amountInUSD: number | null | undefined) => {
    return convertCurrency(amountInUSD, currency);
  };

  const currencySymbol = getCurrencySymbol(currency);
  const exchangeRate = CURRENCY_CONFIGS[currency]?.rateAgainstUSD ?? 1.0;

  return (
    <CurrencyContext.Provider
      value={{
        currency,
        setCurrency,
        currencySymbol,
        exchangeRate,
        formatAmount,
        convertAmount,
      }}
    >
      {children}
    </CurrencyContext.Provider>
  );
};

export const useCurrency = (): CurrencyContextType => {
  const context = useContext(CurrencyContext);
  if (!context) {
    throw new Error('useCurrency must be used within a CurrencyProvider');
  }
  return context;
};
