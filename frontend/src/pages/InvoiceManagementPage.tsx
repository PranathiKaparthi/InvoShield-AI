import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  Search,
  Download,
  Check,
  X,
  UploadCloud,
  Eye,
  ArrowRight,
  Filter,
} from 'lucide-react';
import { invoicesApi } from '../services/api';
import { Invoice } from '../types';
import { useAuth } from '../context/AuthContext';
import { useCurrency } from '../context/CurrencyContext';

export const InvoiceManagementPage: React.FC = () => {
  const { currency, formatAmount, convertAmount } = useCurrency();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [riskFilter, setRiskFilter] = useState<string>('');
  const [validationFilter, setValidationFilter] = useState<string>('');

  const { canApprove } = useAuth();

  const fetchInvoices = async () => {
    setLoading(true);
    try {
      const res = await invoicesApi.getAll({
        search: search || undefined,
        status: statusFilter || undefined,
        risk_level: riskFilter || undefined,
        validation_status: validationFilter || undefined,
        page,
        limit: 10,
      });
      setInvoices(res.data.items);
      setTotal(res.data.total);
      setTotalPages(res.data.total_pages);
    } catch (err) {
      console.error('Failed to load invoices', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInvoices();
  }, [page, statusFilter, riskFilter, validationFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchInvoices();
  };

  const exportCSV = () => {
    if (invoices.length === 0) return;
    const headers = ['ID', 'Invoice Number', 'Vendor Name', 'Date', `Total Amount (${currency})`, 'Status', 'Risk Level', 'Validation Status', 'Duplicate Status'];
    const rows = invoices.map((inv) => [
      inv.id,
      inv.invoice_number || '',
      `"${inv.vendor_name || ''}"`,
      inv.invoice_date || '',
      convertAmount(inv.total_amount).toFixed(2),
      inv.status,
      inv.risk_level,
      inv.validation_status,
      inv.duplicate_status,
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `invoshield_invoices_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleQuickApprove = async (id: number) => {
    try {
      await invoicesApi.approve(id);
      fetchInvoices();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Approval failed.');
    }
  };

  const handleQuickReject = async (id: number) => {
    try {
      await invoicesApi.reject(id);
      fetchInvoices();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Rejection failed.');
    }
  };

  return (
    <div className="space-y-5">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Invoice Archive</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Searchable repository of processed invoices and validation records
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={exportCSV}
            className="px-3.5 py-2 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <Download className="w-3.5 h-3.5 text-gray-500" />
            <span>Export CSV</span>
          </button>
          <Link
            to="/upload"
            className="px-3.5 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium text-xs flex items-center gap-1.5 transition-colors shadow-xs"
          >
            <UploadCloud className="w-3.5 h-3.5" />
            <span>Upload Invoice</span>
          </Link>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3.5 rounded-lg bg-white border border-gray-200 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <form onSubmit={handleSearchSubmit} className="flex items-center space-x-2 flex-1 max-w-md">
          <div className="relative w-full">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search invoice #, vendor, or customer..."
              className="w-full pl-8 pr-3 py-1.5 rounded-md bg-white border border-gray-300 text-xs text-gray-900 placeholder-gray-400 focus:border-blue-600 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            className="px-3.5 py-1.5 rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700 text-xs font-medium transition-colors"
          >
            Search
          </button>
        </form>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-xs text-gray-700 focus:border-blue-600 focus:outline-none"
          >
            <option value="">All Statuses</option>
            <option value="pending_review">Pending Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="flagged">Flagged</option>
          </select>

          {/* Risk Level Filter */}
          <select
            value={riskFilter}
            onChange={(e) => {
              setRiskFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-xs text-gray-700 focus:border-blue-600 focus:outline-none"
          >
            <option value="">All Risk Levels</option>
            <option value="Low">Low Risk</option>
            <option value="Medium">Medium Risk</option>
            <option value="High">High Risk</option>
          </select>

          {/* Validation Filter */}
          <select
            value={validationFilter}
            onChange={(e) => {
              setValidationFilter(e.target.value);
              setPage(1);
            }}
            className="px-2.5 py-1.5 rounded-md bg-white border border-gray-300 text-xs text-gray-700 focus:border-blue-600 focus:outline-none"
          >
            <option value="">All Validations</option>
            <option value="valid">Valid</option>
            <option value="warning">Warnings</option>
            <option value="invalid">Invalid</option>
          </select>
        </div>
      </div>

      {/* Clean Admin Table */}
      <div className="rounded-lg bg-white border border-gray-200 overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-600 font-semibold border-b border-gray-200">
              <tr>
                <th className="py-2.5 px-3.5">Invoice #</th>
                <th className="py-2.5 px-3.5">Vendor</th>
                <th className="py-2.5 px-3.5">Date</th>
                <th className="py-2.5 px-3.5 text-right">Amount ({currency})</th>
                <th className="py-2.5 px-3.5 text-center">Status</th>
                <th className="py-2.5 px-3.5 text-center">Math Check</th>
                <th className="py-2.5 px-3.5 text-center">Duplicate Check</th>
                <th className="py-2.5 px-3.5 text-center">Risk Level</th>
                <th className="py-2.5 px-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-gray-500">
                    <div className="flex flex-col items-center justify-center space-y-2">
                      <div className="w-5 h-5 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                      <span className="text-xs">Loading records...</span>
                    </div>
                  </td>
                </tr>
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-gray-500">
                    No invoices matching the current filter criteria.
                  </td>
                </tr>
              ) : (
                invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-3.5 font-medium text-gray-900">
                      <Link to={`/invoices/${inv.id}/details`} className="hover:text-blue-600 hover:underline">
                        {inv.invoice_number || `INV-${inv.id}`}
                      </Link>
                    </td>
                    <td className="py-3 px-3.5 text-gray-700 truncate max-w-[150px]">{inv.vendor_name || 'N/A'}</td>
                    <td className="py-3 px-3.5 text-gray-500 text-[11px]">{inv.invoice_date || 'N/A'}</td>
                    <td className="py-3 px-3.5 font-semibold text-gray-900 text-right">
                      {formatAmount(inv.total_amount)}
                    </td>
                    <td className="py-3 px-3.5 text-center">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${
                        inv.status === 'approved' ? 'bg-green-50 text-green-700 border-green-200' :
                        inv.status === 'rejected' ? 'bg-red-50 text-red-700 border-red-200' :
                        inv.status === 'flagged' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        'bg-blue-50 text-blue-700 border-blue-200'
                      }`}>
                        {inv.status === 'pending_review' ? 'Pending' : inv.status}
                      </span>
                    </td>
                    <td className="py-3 px-3.5 text-center">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] capitalize font-medium ${
                        inv.validation_status === 'valid' ? 'text-green-700 bg-green-50' :
                        inv.validation_status === 'warning' ? 'text-amber-700 bg-amber-50' :
                        'text-red-700 bg-red-50'
                      }`}>
                        {inv.validation_status}
                      </span>
                    </td>
                    <td className="py-3 px-3.5 text-center">
                      <span className={`text-[11px] ${
                        inv.duplicate_status?.includes('Highly') ? 'text-red-600 font-semibold' :
                        inv.duplicate_status?.includes('Possible') ? 'text-amber-600 font-medium' :
                        'text-gray-500'
                      }`}>
                        {inv.duplicate_status || 'Unique'}
                      </span>
                    </td>
                    <td className="py-3 px-3.5 text-center">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                        inv.risk_level === 'High' ? 'text-red-700 bg-red-50 border-red-200' :
                        inv.risk_level === 'Medium' ? 'text-amber-700 bg-amber-50 border-amber-200' :
                        'text-gray-700 bg-gray-100 border-gray-200'
                      }`}>
                        {inv.risk_level} ({inv.risk_score})
                      </span>
                    </td>
                    <td className="py-3 px-3.5 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        <Link
                          to={`/invoices/${inv.id}/result`}
                          className="p-1.5 rounded bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
                          title="Inspect & Edit"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </Link>
                        {canApprove && inv.status !== 'approved' && (
                          <button
                            type="button"
                            onClick={() => handleQuickApprove(inv.id)}
                            className="p-1.5 rounded bg-green-50 hover:bg-green-100 text-green-700 border border-green-200 transition-colors"
                            title="Quick Approve"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {canApprove && inv.status !== 'rejected' && (
                          <button
                            type="button"
                            onClick={() => handleQuickReject(inv.id)}
                            className="p-1.5 rounded bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 transition-colors"
                            title="Quick Reject"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Clean Pagination Bar */}
        <div className="p-3 bg-gray-50 border-t border-gray-200 flex items-center justify-between text-xs text-gray-600">
          <span>
            Showing {invoices.length} of {total} records
          </span>
          <div className="flex items-center space-x-1.5">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-2.5 py-1 rounded bg-white border border-gray-300 text-gray-700 text-xs disabled:opacity-40 hover:bg-gray-100 transition-colors"
            >
              Previous
            </button>
            <span className="px-2 text-[11px] font-medium">
              Page {page} of {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="px-2.5 py-1 rounded bg-white border border-gray-300 text-gray-700 text-xs disabled:opacity-40 hover:bg-gray-100 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
