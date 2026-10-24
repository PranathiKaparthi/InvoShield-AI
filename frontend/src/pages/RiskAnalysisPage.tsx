import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Clock,
  FileText,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Percent,
} from 'lucide-react';
import { invoicesApi } from '../services/api';
import { Invoice } from '../types';
import { useCurrency } from '../context/CurrencyContext';

export const RiskAnalysisPage: React.FC = () => {
  const { formatAmount } = useCurrency();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const targetId = id || searchParams.get('id');

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string>(targetId || '');
  const [riskData, setRiskData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    invoicesApi.getAll({ limit: 50 }).then((res) => {
      setInvoices(res.data.items);
      if (!selectedInvoiceId && res.data.items.length > 0) {
        setSelectedInvoiceId(String(res.data.items[0].id));
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedInvoiceId) return;
    setLoading(true);
    invoicesApi
      .getRiskAnalysis(selectedInvoiceId)
      .then((res) => {
        setRiskData(res.data);
      })
      .catch((err) => {
        console.error('Error fetching risk analysis', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedInvoiceId]);

  const score = riskData?.risk_score ?? 0;
  const level = riskData?.risk_level || 'Low';

  const getRiskTheme = (riskLevel: string) => {
    switch (riskLevel.toLowerCase()) {
      case 'high':
        return {
          bg: 'bg-red-50 border-red-200',
          text: 'text-red-700',
          badge: 'bg-red-100 text-red-800 border-red-200',
          meter: '#dc2626',
          icon: ShieldAlert,
        };
      case 'medium':
        return {
          bg: 'bg-amber-50 border-amber-200',
          text: 'text-amber-800',
          badge: 'bg-amber-100 text-amber-800 border-amber-200',
          meter: '#d97706',
          icon: AlertTriangle,
        };
      default:
        return {
          bg: 'bg-green-50 border-green-200',
          text: 'text-green-700',
          badge: 'bg-green-100 text-green-800 border-green-200',
          meter: '#16a34a',
          icon: ShieldCheck,
        };
    }
  };

  const theme = getRiskTheme(level);
  const Icon = theme.icon;

  return (
    <div className="space-y-5">
      {/* Top Header & Selector */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div className="flex items-center space-x-3">
          <Link
            to="/invoices"
            className="p-1.5 rounded-md bg-white hover:bg-gray-100 border border-gray-200 text-gray-600 transition-colors"
            title="Back to Invoices"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Fraud & Risk Engine</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Automated anomaly verification, vendor spend spike evaluation, and math reconciliation
            </p>
          </div>
        </div>

        {/* Invoice Selector */}
        <div className="flex items-center space-x-2 text-xs">
          <span className="text-gray-600 font-medium">Select Invoice:</span>
          <select
            value={selectedInvoiceId}
            onChange={(e) => setSelectedInvoiceId(e.target.value)}
            className="px-3 py-1.5 rounded-md bg-white border border-gray-300 text-gray-800 text-xs focus:border-blue-600 focus:outline-none"
          >
            {invoices.map((inv) => (
              <option key={inv.id} value={inv.id}>
                #{inv.invoice_number || `ID ${inv.id}`} · {inv.vendor_name || 'Vendor'} · {formatAmount(inv.total_amount)} · Risk: {inv.risk_level} ({inv.risk_score})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : !riskData ? (
        <div className="p-8 rounded-lg bg-white border border-gray-200 text-center text-gray-500 text-xs">
          Select an invoice above to evaluate risk breakdown.
        </div>
      ) : (
        <div className="space-y-5">
          {/* Risk Score Assessment Deck */}
          <div className={`p-5 rounded-lg border ${theme.bg} grid grid-cols-1 md:grid-cols-3 gap-6 items-center shadow-xs`}>
            {/* Score Dial Meter */}
            <div className="flex flex-col items-center justify-center text-center space-y-2">
              <div className="relative w-32 h-32 flex items-center justify-center">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-gray-200"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    strokeDasharray={`${score}, 100`}
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    stroke={theme.meter}
                    fill="none"
                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
                <div className="absolute flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold text-gray-900">{score}</span>
                  <span className="text-[10px] text-gray-500">/ 100</span>
                </div>
              </div>
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Threat Score</span>
            </div>

            {/* Level & Summary */}
            <div className="md:col-span-2 space-y-3">
              <div className="flex items-center gap-2.5">
                <div className={`p-2 rounded-md ${theme.badge}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-gray-900 tracking-tight">{level} Risk Tier</h2>
                    <span className={`px-2 py-0.2 rounded text-[10px] font-semibold uppercase border ${theme.badge}`}>
                      Score: {score}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Invoice #{riskData.invoice_number || 'N/A'} · Vendor: {riskData.vendor_name || 'Unspecified'}
                  </p>
                </div>
              </div>

              <div className="p-3 rounded-md bg-white border border-gray-200 space-y-1">
                <span className="text-xs font-medium text-gray-600">Primary Risk Factor:</span>
                <p className="text-xs text-gray-800 leading-relaxed">
                  {riskData.reasons?.[0] || 'Invoice matches expected historical profile.'}
                </p>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <Link
                  to={`/invoices/${selectedInvoiceId}/result`}
                  className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors border border-gray-300 shadow-xs"
                >
                  <FileText className="w-3.5 h-3.5 text-gray-500" />
                  <span>Inspect Record</span>
                </Link>
                <Link
                  to={`/invoices/${selectedInvoiceId}/duplicates`}
                  className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
                >
                  <span>Duplicate Check</span>
                  <ArrowRight className="w-3.5 h-3.5 text-gray-500" />
                </Link>
              </div>
            </div>
          </div>

          {/* Detailed Flagged Reasons */}
          <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
            <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-500" />
              Rule Diagnostics ({riskData.reasons?.length || 0} alerts evaluated)
            </h3>

            <div className="space-y-2">
              {(riskData.reasons || []).map((reason: string, idx: number) => (
                <div
                  key={idx}
                  className="p-3 rounded-md bg-gray-50 border border-gray-200 flex items-start space-x-2.5 text-xs"
                >
                  <div className="mt-0.5 shrink-0">
                    {reason.toLowerCase().includes('low risk') ? (
                      <CheckCircle2 className="w-4 h-4 text-green-600" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                    )}
                  </div>
                  <div className="space-y-0.5">
                    <p className="text-gray-800 leading-relaxed font-medium">{reason}</p>
                    <span className="text-[11px] text-gray-500">Evaluated against deterministic risk rules</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Rule Evaluation Architecture Matrix */}
          <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
            <h3 className="text-sm font-semibold text-gray-900">
              Verification Criteria
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-md bg-gray-50 border border-gray-200 space-y-1.5">
                <div className="flex items-center space-x-2 text-blue-700">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-xs font-semibold">Spend Spikes</span>
                </div>
                <p className="text-xs text-gray-600 leading-normal">
                  Flags invoices exceeding 300% of vendor 90-day moving average or historical standard deviation.
                </p>
              </div>

              <div className="p-3.5 rounded-md bg-gray-50 border border-gray-200 space-y-1.5">
                <div className="flex items-center space-x-2 text-green-700">
                  <Percent className="w-4 h-4" />
                  <span className="text-xs font-semibold">Math Integrity</span>
                </div>
                <p className="text-xs text-gray-600 leading-normal">
                  Enforces Subtotal + Tax - Discount = Total within strict {formatAmount(0.05)} rounding threshold.
                </p>
              </div>

              <div className="p-3.5 rounded-md bg-gray-50 border border-gray-200 space-y-1.5">
                <div className="flex items-center space-x-2 text-purple-700">
                  <Clock className="w-4 h-4" />
                  <span className="text-xs font-semibold">Chronology Check</span>
                </div>
                <p className="text-xs text-gray-600 leading-normal">
                  Flags post-dated invoices (&gt;7 days into future) or invoices where due date precedes invoice date.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
