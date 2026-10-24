import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import {
  CopyCheck,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { invoicesApi } from '../services/api';
import { Invoice } from '../types';
import { useCurrency } from '../context/CurrencyContext';

export const DuplicateDetectionPage: React.FC = () => {
  const { formatAmount } = useCurrency();
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const targetId = id || searchParams.get('id');

  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string>(targetId || '');
  const [dupData, setDupData] = useState<any | null>(null);
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
      .getDuplicates(selectedInvoiceId)
      .then((res) => {
        setDupData(res.data);
      })
      .catch((err) => {
        console.error('Error fetching duplicate data', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedInvoiceId]);

  const getVerdictStyle = (verdict: string) => {
    if (verdict?.includes('Highly')) {
      return {
        bg: 'bg-red-50 border-red-200',
        text: 'text-red-700',
        badge: 'bg-red-100 text-red-800 border-red-200',
        label: 'Highly Likely Duplicate (90–100%)',
      };
    }
    if (verdict?.includes('Possible')) {
      return {
        bg: 'bg-amber-50 border-amber-200',
        text: 'text-amber-800',
        badge: 'bg-amber-100 text-amber-800 border-amber-200',
        label: 'Possible Duplicate (75–89%)',
      };
    }
    return {
      bg: 'bg-green-50 border-green-200',
      text: 'text-green-700',
      badge: 'bg-green-100 text-green-800 border-green-200',
      label: 'Unique Record (<75%)',
    };
  };

  const currentInv = dupData?.current_invoice;
  const matchedInv = dupData?.matched_invoice;
  const fieldScores = dupData?.breakdown?.field_scores || {};
  const verdictInfo = getVerdictStyle(dupData?.duplicate_status);

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
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Duplicate Detection</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Cross-evaluates vendor names, invoice numbers, dates, and amounts against historical archives
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
                #{inv.invoice_number || `ID ${inv.id}`} · {inv.vendor_name} ({formatAmount(inv.total_amount)})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center min-h-[300px]">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : !dupData ? (
        <div className="p-8 rounded-lg bg-white border border-gray-200 text-center text-gray-500 text-xs">
          Select an invoice above to evaluate duplicate matching.
        </div>
      ) : (
        <div className="space-y-5">
          {/* Verdict Score Card */}
          <div className={`p-4 rounded-lg border ${verdictInfo.bg} flex flex-col sm:flex-row items-center justify-between gap-4 shadow-xs`}>
            <div className="space-y-1 text-center sm:text-left">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Verdict</span>
              <h2 className={`text-lg font-bold ${verdictInfo.text}`}>{dupData.duplicate_status}</h2>
              <p className="text-xs text-gray-600">
                {dupData.similarity_score >= 75
                  ? `Match detected against Invoice #${matchedInv?.invoice_number || 'prior record'}. Review before approval.`
                  : 'No duplicate conflicts discovered in historical records.'}
              </p>
            </div>

            <div className="text-center sm:text-right shrink-0">
              <div className="text-3xl font-bold text-gray-900">
                {dupData.similarity_score}%
              </div>
              <span className="text-xs text-gray-500">Similarity Score</span>
            </div>
          </div>

          {/* Side-by-Side Comparison */}
          {matchedInv ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Current Ingested Invoice Card */}
              <div className="p-4 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
                <div className="flex items-center justify-between border-b border-gray-200 pb-2">
                  <span className="text-xs font-semibold text-blue-700">Current Ingested Invoice</span>
                  <Link
                    to={`/invoices/${currentInv?.id}/result`}
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                  >
                    View Details <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Invoice Number:</span>
                    <span className="text-gray-900 font-medium">{currentInv?.invoice_number || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Vendor:</span>
                    <span className="text-gray-800">{currentInv?.vendor_name}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Total Amount:</span>
                    <span className="text-gray-900 font-semibold">{formatAmount(currentInv?.total_amount)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Invoice Date:</span>
                    <span className="text-gray-700">{currentInv?.invoice_date}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">GST / Tax ID:</span>
                    <span className="text-gray-700">{currentInv?.gst_number || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-gray-500">PO Number:</span>
                    <span className="text-gray-700">{currentInv?.po_number || 'N/A'}</span>
                  </div>
                </div>
              </div>

              {/* Matched Historical Candidate Card */}
              <div className="p-4 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
                <div className="flex items-center justify-between border-b border-gray-200 pb-2">
                  <span className="text-xs font-semibold text-amber-700">Matched Prior Invoice</span>
                  <Link
                    to={`/invoices/${matchedInv?.id}/result`}
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                  >
                    View Prior <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Invoice Number:</span>
                    <span className="text-gray-900 font-medium">{matchedInv?.invoice_number || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Vendor:</span>
                    <span className="text-gray-800">{matchedInv?.vendor_name}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Total Amount:</span>
                    <span className="text-gray-900 font-semibold">{formatAmount(matchedInv?.total_amount)}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">Invoice Date:</span>
                    <span className="text-gray-700">{matchedInv?.invoice_date}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-gray-100">
                    <span className="text-gray-500">GST / Tax ID:</span>
                    <span className="text-gray-700">{matchedInv?.gst_number || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-gray-500">PO Number:</span>
                    <span className="text-gray-700">{matchedInv?.po_number || 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-6 rounded-lg bg-white border border-gray-200 text-center space-y-1.5 shadow-xs">
              <CheckCircle2 className="w-6 h-6 text-green-600 mx-auto" />
              <h3 className="text-sm font-semibold text-gray-900">Unique Invoice Document</h3>
              <p className="text-xs text-gray-500">No matching historical records exceeded the similarity threshold.</p>
            </div>
          )}

          {/* Per-Field Match Breakdown Grid */}
          {matchedInv && Object.keys(fieldScores).length > 0 && (
            <div className="p-4 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
              <h3 className="text-sm font-semibold text-gray-900">
                Field Match Analysis
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(fieldScores).map(([field, score]: [string, any]) => (
                  <div key={field} className="p-3 rounded-md bg-gray-50 border border-gray-200 space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-600 capitalize">{field.replace('_', ' ')}</span>
                      <span className={`font-semibold ${score >= 90 ? 'text-red-600' : score >= 75 ? 'text-amber-600' : 'text-gray-700'}`}>
                        {score}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 h-1.5 rounded overflow-hidden">
                      <div
                        className={`h-full rounded transition-all ${
                          score >= 90 ? 'bg-red-500' : score >= 75 ? 'bg-amber-500' : 'bg-green-500'
                        }`}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
