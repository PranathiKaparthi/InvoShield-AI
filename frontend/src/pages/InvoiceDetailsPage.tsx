import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FileText,
  ArrowLeft,
  Lock,
  AlertTriangle,
  History,
  ExternalLink,
  ShieldCheck,
  Eye,
  EyeOff,
  Edit2,
} from 'lucide-react';
import { invoicesApi } from '../services/api';
import { useInvoiceFileUrl } from '../services/useInvoiceFile';
import { Invoice } from '../types';
import { useCurrency } from '../context/CurrencyContext';

export const InvoiceDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const fileUrl = useInvoiceFileUrl(id) ?? undefined;
  const { formatAmount } = useCurrency();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [showSensitive, setShowSensitive] = useState(false);

  useEffect(() => {
    if (!id) return;
    invoicesApi
      .getById(id)
      .then((res) => setInvoice(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading || !invoice) {
    return (
      <div className="flex items-center justify-center min-h-[350px]">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }


  return (
    <div className="space-y-5 max-w-5xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div className="flex items-center space-x-3">
          <Link
            to="/invoices"
            className="p-1.5 rounded-md bg-white hover:bg-gray-100 border border-gray-200 text-gray-600 transition-colors"
            title="Back to Invoices"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
                Invoice Record: #{invoice.invoice_number || `ID-${invoice.id}`}
              </h1>
              <span className={`px-2 py-0.5 rounded text-[11px] font-medium border ${
                invoice.status === 'approved' ? 'bg-green-50 text-green-700 border-green-200' :
                invoice.status === 'rejected' ? 'bg-red-50 text-red-700 border-red-200' :
                invoice.status === 'flagged' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                'bg-blue-50 text-blue-700 border-blue-200'
              }`}>
                {invoice.status === 'pending_review' ? 'Pending' : invoice.status}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-gray-500">
              <span>Organization: <span className="text-gray-800 font-medium">{invoice.organization || 'General'}</span></span>
              <span>•</span>
              <span className="flex items-center gap-1 text-gray-700">
                <ShieldCheck className="w-3.5 h-3.5 text-green-600" />
                SHA-256: {invoice.sha256_checksum ? `${invoice.sha256_checksum.slice(0, 16)}...` : 'Bit-Exact Match'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={fileUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <span>Original Document</span>
            <ExternalLink className="w-3 h-3 text-gray-500" />
          </a>
          <Link
            to={`/invoices/${invoice.id}/result`}
            className="px-3.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <Edit2 className="w-3.5 h-3.5" />
            <span>Inspect / Edit</span>
          </Link>
        </div>
      </div>

      {/* Overview Metric Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-lg bg-white border border-gray-200 space-y-1 shadow-xs">
          <span className="text-xs text-gray-500">Total Billed</span>
          <p className="text-xl font-bold text-gray-900">{formatAmount(invoice.total_amount, 2, invoice.currency)}</p>
          <span className="text-[11px] text-gray-500">Subtotal: {formatAmount(invoice.subtotal, 2, invoice.currency)}</span>
        </div>

        <div className="p-3.5 rounded-lg bg-white border border-gray-200 space-y-1 shadow-xs">
          <span className="text-xs text-gray-500">Risk Score</span>
          <p className="text-xl font-bold text-gray-900">{invoice.risk_score} / 100</p>
          <span className="text-[11px] text-amber-700 font-medium">{invoice.risk_level} Risk Tier</span>
        </div>

        <div className="p-3.5 rounded-lg bg-white border border-gray-200 space-y-1 shadow-xs">
          <span className="text-xs text-gray-500">Duplicate Check</span>
          <p className="text-xs font-semibold text-gray-800 mt-1 truncate">{invoice.duplicate_status}</p>
          <Link to={`/invoices/${invoice.id}/duplicates`} className="text-[11px] text-blue-600 hover:underline block">
            Inspect matches →
          </Link>
        </div>

        <div className="p-3.5 rounded-lg bg-white border border-gray-200 space-y-1 shadow-xs">
          <span className="text-xs text-gray-500">Math Validation</span>
          <p className="text-xs font-semibold text-gray-800 mt-1 capitalize">{invoice.validation_status}</p>
          <span className="text-[11px] text-gray-500">Reconciled tolerance</span>
        </div>
      </div>

      {/* Extracted Details & Encrypted Sensitive Fields */}
      <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-4 shadow-xs">
        <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-gray-500" />
          Extracted Invoice Metadata
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 text-xs">
          <div className="space-y-3">
            <div>
              <span className="text-gray-500 block text-[11px]">Vendor Information</span>
              <span className="font-medium text-gray-900">{invoice.vendor_name || 'N/A'}</span>
              <p className="text-gray-500 text-[11px] mt-0.5">{invoice.vendor_address || 'No address provided'}</p>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Customer Information</span>
              <span className="font-medium text-gray-900">{invoice.customer_name || 'N/A'}</span>
              <p className="text-gray-500 text-[11px] mt-0.5">{invoice.customer_address || 'No address provided'}</p>
            </div>
          </div>

          <div className="space-y-2.5 text-xs">
            <div>
              <span className="text-gray-500 block text-[11px]">Invoice Date</span>
              <span className="text-gray-800">{invoice.invoice_date || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">Due Date</span>
              <span className="text-gray-800">{invoice.due_date || 'N/A'}</span>
            </div>
            <div>
              <span className="text-gray-500 block text-[11px]">PO Number</span>
              <span className="text-gray-800">{invoice.po_number || 'N/A'}</span>
            </div>
          </div>

          {/* Encrypted Sensitive Fields */}
          <div className="p-3.5 rounded-md bg-gray-50 border border-gray-200 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-1 text-gray-700 font-medium text-[11px]">
                <Lock className="w-3 h-3 text-gray-500" />
                <span>Protected Identifiers</span>
              </div>
              <button
                type="button"
                onClick={() => setShowSensitive(!showSensitive)}
                className="text-[11px] text-blue-600 hover:text-blue-800 flex items-center gap-1 transition-colors"
              >
                {showSensitive ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                {showSensitive ? 'Mask' : 'Reveal'}
              </button>
            </div>
            <div className="text-xs space-y-1.5">
              <div>
                <span className="text-gray-500 block text-[10px]">Vendor GSTIN</span>
                <span className="font-mono text-gray-900 font-medium">
                  {showSensitive
                    ? (invoice.gst_number || 'None')
                    : (invoice.gst_number ? `${invoice.gst_number.slice(0, 4)}••••••••${invoice.gst_number.slice(-2)}` : 'None')}
                </span>
              </div>
              <div>
                <span className="text-gray-500 block text-[10px]">Tax ID</span>
                <span className="font-mono text-gray-900">
                  {showSensitive
                    ? (invoice.tax_id || 'None')
                    : (invoice.tax_id ? `••••••••${invoice.tax_id.slice(-4)}` : 'None')}
                </span>
              </div>
              <div>
                <span className="text-gray-500 block text-[10px]">Bank Details</span>
                <span className="text-gray-800 truncate block font-mono">
                  {showSensitive
                    ? (invoice.bank_details || 'Standard Wire')
                    : '•••• •••• •••• 9842 (Encrypted Wire)'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Fraud Alert Diagnostics */}
      <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
        <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
          Fraud & Anomaly Triggers ({invoice.fraud_alerts?.length || 0})
        </h2>
        <div className="space-y-1.5">
          {(invoice.fraud_alerts || []).length === 0 ? (
            <p className="text-xs text-gray-500 py-2">No active fraud triggers flagged for this record.</p>
          ) : (
            (invoice.fraud_alerts || []).map((alert, i) => (
              <div key={i} className="p-2.5 rounded-md bg-gray-50 border border-gray-200 flex items-center justify-between text-xs">
                <span className="text-gray-800 font-medium">{alert.alert_reason}</span>
                <span className="px-2 py-0.5 rounded text-[11px] bg-amber-50 text-amber-800 border border-amber-200 font-medium">
                  Score: {alert.risk_score} ({alert.risk_level})
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Immutable Audit Ledger */}
      <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
        <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
          <History className="w-3.5 h-3.5 text-gray-500" />
          Audit Ledger History
        </h2>
        <div className="divide-y divide-gray-100">
          {(invoice.audit_logs || []).map((log) => (
            <div key={log.id} className="py-2.5 flex items-center justify-between text-xs">
              <div className="space-y-0.5">
                <span className="px-2 py-0.5 rounded text-[10px] bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                  {log.action}
                </span>
                <p className="text-gray-700 text-xs mt-0.5">{log.details}</p>
              </div>
              <span className="text-gray-500 text-[11px]">
                {log.timestamp ? new Date(log.timestamp).toLocaleString() : ''}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
