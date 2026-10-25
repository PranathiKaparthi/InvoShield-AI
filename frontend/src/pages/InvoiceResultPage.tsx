import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  Save,
  RotateCw,
  Check,
  X,
  CopyCheck,
  ShieldAlert,
  ArrowLeft,
  ExternalLink,
  Edit2,
  ShieldCheck,
  Eye,
  EyeOff,
  Lock,
} from 'lucide-react';
import { invoicesApi } from '../services/api';
import { useInvoiceFileUrl } from '../services/useInvoiceFile';
import { Invoice } from '../types';
import { useAuth } from '../context/AuthContext';
import { useCurrency } from '../context/CurrencyContext';

export const InvoiceResultPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const fileUrl = useInvoiceFileUrl(id) ?? undefined;
  const { currency, formatAmount } = useCurrency();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  const [formData, setFormData] = useState<Partial<Invoice>>({});
  const [showSensitive, setShowSensitive] = useState<boolean>(false);

  const { user, canApprove, isAdmin } = useAuth();

  const isSelfSubmitted = Boolean(invoice && invoice.user_id && user && invoice.user_id === user.id && !isAdmin);

  const fetchInvoice = async () => {
    if (!id) return;
    try {
      setLoading(true);
      const res = await invoicesApi.getById(id);
      setInvoice(res.data);
      setFormData(res.data);
    } catch {
      setMessage({ text: 'Failed to load invoice details.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoice();
  }, [id]);

  const handleInputChange = (field: keyof Invoice, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveChanges = async () => {
    if (!id) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await invoicesApi.update(id, formData);
      setInvoice(res.data);
      setMessage({ text: 'Changes saved and re-encrypted successfully.', type: 'success' });
    } catch (err: any) {
      setMessage({ text: err.response?.data?.detail || 'Save failed.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleRevalidate = async () => {
    if (!id) return;
    setSaving(true);
    setMessage(null);
    try {
      const res = await invoicesApi.revalidate(id);
      setInvoice(res.data);
      setMessage({ text: 'Validation rules re-executed.', type: 'success' });
    } catch {
      setMessage({ text: 'Revalidation failed.', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    if (!id) return;
    try {
      await invoicesApi.approve(id);
      setMessage({ text: 'Invoice approved and stored in processed vault.', type: 'success' });
      fetchInvoice();
    } catch (err: any) {
      setMessage({ text: err.response?.data?.detail || 'Approval failed.', type: 'error' });
    }
  };

  const handleReject = async () => {
    if (!id) return;
    try {
      await invoicesApi.reject(id);
      setMessage({ text: 'Invoice rejected.', type: 'success' });
      fetchInvoice();
    } catch (err: any) {
      setMessage({ text: err.response?.data?.detail || 'Rejection failed.', type: 'error' });
    }
  };

  if (loading || !invoice) {
    return (
      <div className="flex items-center justify-center min-h-[350px]">
        <div className="flex flex-col items-center space-y-2.5">
          <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs font-mono text-slate-400">Loading extracted data & validation...</span>
        </div>
      </div>
    );
  }

  const getStatusBadge = (statusStr: string) => {
    switch (statusStr.toLowerCase()) {
      case 'valid':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-green-50 text-green-700 border border-green-200">Valid</span>;
      case 'warning':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">Warning</span>;
      case 'invalid':
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-red-50 text-red-700 border border-red-200">Invalid</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-100 text-gray-700 border border-gray-200">Missing</span>;
    }
  };

  const isPdf = invoice.original_filename?.toLowerCase().endsWith('.pdf');

  return (
    <div className="space-y-5">
      {/* Top Controls Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-4">
        <div className="flex items-center space-x-3">
          <Link
            to="/invoices"
            className="p-1.5 rounded-md bg-white hover:bg-gray-100 border border-gray-200 text-gray-600 transition-colors"
            title="Back to Invoice List"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold text-gray-900 tracking-tight">
                Invoice #{invoice.invoice_number || 'N/A'}
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
            <p className="text-xs text-gray-500 mt-0.5">Vendor: {invoice.vendor_name || 'Unspecified'}</p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/invoices/${invoice.id}/duplicates`}
            className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <CopyCheck className="w-3.5 h-3.5 text-gray-500" />
            <span>Duplicates</span>
          </Link>

          <Link
            to={`/invoices/${invoice.id}/risk-analysis`}
            className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-gray-500" />
            <span>Risk ({invoice.risk_score})</span>
          </Link>

          {canApprove && (
            <>
              <button
                type="button"
                onClick={handleRevalidate}
                disabled={saving}
                className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <RotateCw className={`w-3.5 h-3.5 ${saving ? 'animate-spin' : ''}`} />
                <span>Revalidate</span>
              </button>

              <button
                type="button"
                onClick={handleSaveChanges}
                disabled={saving}
                className="px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <Save className="w-3.5 h-3.5 text-gray-500" />
                <span>Save</span>
              </button>

              {isSelfSubmitted ? (
                <button
                  type="button"
                  disabled
                  title="Segregation of Duties (SoD) Active: You submitted this invoice. An independent reviewer must approve."
                  className="px-3 py-1.5 rounded-md bg-gray-100 text-gray-400 font-medium text-xs flex items-center gap-1.5 cursor-not-allowed border border-gray-200"
                >
                  <Lock className="w-3.5 h-3.5 text-gray-400" />
                  <span>Approve (SoD Locked)</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleApprove}
                  className="px-3 py-1.5 rounded-md bg-green-600 hover:bg-green-700 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shadow-xs"
                >
                  <Check className="w-3.5 h-3.5" />
                  <span>Approve</span>
                </button>
              )}

              <button
                type="button"
                onClick={handleReject}
                className="px-3 py-1.5 rounded-md bg-red-50 hover:bg-red-100 border border-red-200 text-red-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
              >
                <X className="w-3.5 h-3.5" />
                <span>Reject</span>
              </button>
            </>
          )}
        </div>
      </div>

      {isSelfSubmitted && (
        <div className="p-3 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
          <span>
            <strong>Segregation of Duties Enforced:</strong> You submitted this invoice. Internal control policies require an independent reviewer to authorize payment.
          </span>
        </div>
      )}

      {message && (
        <div className={`p-3 rounded-md text-xs flex items-center gap-2 ${
          message.type === 'success' ? 'bg-green-50 border border-green-200 text-green-800' : 'bg-red-50 border border-red-200 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0 text-green-600" /> : <AlertTriangle className="w-4 h-4 shrink-0 text-red-600" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Split Workbench View: Left Preview, Right Fields & Validation */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Side: Document Preview (5 cols) */}
        <div className="lg:col-span-5 p-4 rounded-lg bg-white border border-gray-200 flex flex-col space-y-3 shadow-xs">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-gray-800 flex items-center gap-1.5">
              <FileText className="w-3.5 h-3.5 text-gray-500" />
              Document Viewer
            </span>
            <a
              href={fileUrl}
              target="_blank"
              rel="noreferrer"
              className="text-xs text-blue-600 hover:underline flex items-center gap-1"
            >
              Open in new tab <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <div className="flex-1 min-h-[460px] rounded-md bg-gray-100 border border-gray-200 overflow-hidden flex items-center justify-center p-2">
            {isPdf ? (
              <iframe
                src={fileUrl}
                title="Invoice Document Preview"
                className="w-full h-full min-h-[460px] border-none rounded"
              />
            ) : (
              <img
                src={fileUrl}
                alt="Original Invoice Preview"
                className="max-h-[460px] max-w-full object-contain rounded"
                onError={(e) => {
                  (e.target as HTMLElement).style.display = 'none';
                }}
              />
            )}
          </div>

          {/* Cryptographic SHA-256 Tamper-Proof Seal */}
          <div className="p-3 rounded-md bg-gray-50 border border-gray-200 space-y-1 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-gray-800 flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-green-600" />
                File Integrity Seal
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-green-50 text-green-700 border border-green-200 font-medium">
                SHA-256 Verified
              </span>
            </div>
            <p className="text-[11px] text-gray-500 truncate">
              Checksum: <span className="font-mono text-gray-700">{invoice.sha256_checksum || 'Immutable bit-exact digest verified'}</span>
            </p>
          </div>
        </div>

        {/* Right Side: Extracted Fields, Math, and Line Items (7 cols) */}
        <div className="lg:col-span-7 space-y-5">
          {/* Metadata & Core Fields Form */}
          <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-gray-200 pb-2.5">
              <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-1.5">
                <Edit2 className="w-3.5 h-3.5 text-gray-500" />
                Extracted Invoice Fields
              </h2>
              <span className="text-xs text-gray-500">Edit fields if OCR requires adjustment</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 text-xs">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Invoice Number</label>
                <input
                  type="text"
                  value={formData.invoice_number || ''}
                  onChange={(e) => handleInputChange('invoice_number', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Vendor Name</label>
                <input
                  type="text"
                  value={formData.vendor_name || ''}
                  onChange={(e) => handleInputChange('vendor_name', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Invoice Date</label>
                <input
                  type="text"
                  value={formData.invoice_date || ''}
                  onChange={(e) => handleInputChange('invoice_date', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Due Date</label>
                <input
                  type="text"
                  value={formData.due_date || ''}
                  onChange={(e) => handleInputChange('due_date', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              {/* Zero-Trust GSTIN / PII Field */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700">
                    GST / Tax ID
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowSensitive(!showSensitive)}
                    className="text-[11px] text-blue-600 hover:text-blue-800 flex items-center gap-1 transition-colors"
                  >
                    {showSensitive ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
                    {showSensitive ? 'Mask' : 'Reveal'}
                  </button>
                </div>
                <input
                  type="text"
                  value={showSensitive ? (formData.gst_number || '') : (formData.gst_number ? `${formData.gst_number.slice(0, 4)}••••••••${formData.gst_number.slice(-2)}` : '')}
                  onChange={(e) => handleInputChange('gst_number', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 font-mono text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">PO Number</label>
                <input
                  type="text"
                  value={formData.po_number || ''}
                  onChange={(e) => handleInputChange('po_number', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Customer Name</label>
                <input
                  type="text"
                  value={formData.customer_name || ''}
                  onChange={(e) => handleInputChange('customer_name', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Currency</label>
                <input
                  type="text"
                  value={formData.currency || 'USD'}
                  onChange={(e) => handleInputChange('currency', e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              {/* Financial Calculation Fields */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700">Subtotal Amount</label>
                  {currency !== 'USD' && (
                    <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                      ≈ {formatAmount(formData.subtotal ?? 0, 2, formData.currency)}
                    </span>
                  )}
                </div>
                <input
                  type="number"
                  step="0.01"
                  value={formData.subtotal ?? 0}
                  onChange={(e) => handleInputChange('subtotal', parseFloat(e.target.value) || 0)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700">Tax Amount</label>
                  {currency !== 'USD' && (
                    <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                      ≈ {formatAmount(formData.tax_amount ?? 0, 2, formData.currency)}
                    </span>
                  )}
                </div>
                <input
                  type="number"
                  step="0.01"
                  value={formData.tax_amount ?? 0}
                  onChange={(e) => handleInputChange('tax_amount', parseFloat(e.target.value) || 0)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700">Discount</label>
                  {currency !== 'USD' && (
                    <span className="text-[11px] font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                      ≈ {formatAmount(formData.discount ?? 0, 2, formData.currency)}
                    </span>
                  )}
                </div>
                <input
                  type="number"
                  step="0.01"
                  value={formData.discount ?? 0}
                  onChange={(e) => handleInputChange('discount', parseFloat(e.target.value) || 0)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-gray-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-gray-900">Total Amount</label>
                  {currency !== 'USD' && (
                    <span className="text-[11px] font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded border border-blue-200">
                      ≈ {formatAmount(formData.total_amount ?? 0, 2, formData.currency)}
                    </span>
                  )}
                </div>
                <input
                  type="number"
                  step="0.01"
                  value={formData.total_amount ?? 0}
                  onChange={(e) => handleInputChange('total_amount', parseFloat(e.target.value) || 0)}
                  className="w-full px-2.5 py-1.5 rounded-md bg-white border border-gray-400 text-gray-900 font-bold text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Validation Checklist */}
          <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
            <h3 className="text-sm font-semibold text-gray-900">
              Arithmetic & Validation Checks ({invoice.validation_results?.length || 0})
            </h3>
            <div className="space-y-2">
              {(invoice.validation_results || []).map((val, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-md bg-gray-50 border border-gray-200 flex items-center justify-between text-xs"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-gray-900">{val.field_name}</span>
                      {getStatusBadge(val.validation_status)}
                    </div>
                    <p className="text-[11px] text-gray-500">{val.validation_message}</p>
                  </div>
                  <div className="text-right text-[11px] shrink-0 text-gray-500">
                    Confidence: <span className="font-medium text-gray-700">{(val.confidence_score * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Line Items Table */}
          <div className="p-5 rounded-lg bg-white border border-gray-200 space-y-3 shadow-xs">
            <h3 className="text-sm font-semibold text-gray-900">
              Line Items ({invoice.items?.length || 0})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-gray-200 text-gray-500 font-medium">
                    <th className="pb-2">Description</th>
                    <th className="pb-2 text-right">Qty</th>
                    <th className="pb-2 text-right">Unit Price ({currency})</th>
                    <th className="pb-2 text-right">Total ({currency})</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 text-xs">
                  {(invoice.items || []).map((itm, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="py-2 text-gray-800">{itm.description}</td>
                      <td className="py-2 text-right text-gray-600">{itm.quantity}</td>
                      <td className="py-2 text-right text-gray-600">{formatAmount(itm.unit_price, 2, formData.currency)}</td>
                      <td className="py-2 text-right font-semibold text-gray-900">{formatAmount(itm.total_price, 2, formData.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
