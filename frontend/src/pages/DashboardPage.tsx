import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Upload,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Clock,
  FileText,
  Eye,
} from 'lucide-react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { dashboardApi, invoicesApi } from '../services/api';
import { DashboardStats, DashboardAnalytics, Invoice } from '../types';
import { useAuth } from '../context/AuthContext';
import { useCurrency } from '../context/CurrencyContext';

export const DashboardPage: React.FC = () => {
  const { user, isAdmin, isReviewer } = useAuth();
  const { currency, formatAmount } = useCurrency();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [analytics, setAnalytics] = useState<DashboardAnalytics | null>(null);
  const [recentInvoices, setRecentInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, analyticsRes, invoicesRes] = await Promise.all([
          dashboardApi.getStatistics(),
          dashboardApi.getAnalytics(),
          invoicesApi.getAll({ limit: 6 }),
        ]);
        setStats(statsRes.data);
        setAnalytics(analyticsRes.data);
        setRecentInvoices(invoicesRes.data.items || []);
      } catch (err) {
        console.error('Failed to load dashboard metrics', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[350px]">
        <div className="flex flex-col items-center space-y-2">
          <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-gray-500">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header Section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Overview of invoice processing activity and validation status.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            to="/upload"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm transition-colors shadow-xs"
          >
            <Upload className="w-4 h-4" />
            <span>Upload Invoice</span>
          </Link>
          <Link
            to="/invoices"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-white hover:bg-gray-50 border border-gray-300 text-gray-700 text-sm font-medium transition-colors"
          >
            <span>View All</span>
          </Link>
        </div>
      </div>

      {/* Summary Section: 4 Compact Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Invoices */}
        <div className="p-4 bg-white border border-gray-200 rounded-lg">
          <span className="text-xs font-medium text-gray-500 block">Total Invoices</span>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold text-gray-900">{stats?.total_invoices || 0}</span>
            <span className="text-xs text-gray-500">Ingested records</span>
          </div>
        </div>

        {/* Awaiting Review */}
        <div className="p-4 bg-white border border-gray-200 rounded-lg">
          <span className="text-xs font-medium text-gray-500 block">Awaiting Review</span>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold text-blue-600">{stats?.pending_invoices || 0}</span>
            <span className="text-xs text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-medium">
              {(stats?.pending_invoices || 0) > 0 ? 'Action required' : 'Clear'}
            </span>
          </div>
        </div>

        {/* Processed Amount */}
        <div className="p-4 bg-white border border-gray-200 rounded-lg">
          <span className="text-xs font-medium text-gray-500 block">Processed Amount</span>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl font-bold text-gray-900">
              {formatAmount(stats?.total_amount_processed || 0)}
            </span>
            <span className="text-xs text-green-700 bg-green-50 px-2 py-0.5 rounded font-medium">
              {stats?.approved_invoices || 0} approved
            </span>
          </div>
        </div>

        {/* Flagged for Review */}
        <div className="p-4 bg-white border border-gray-200 rounded-lg">
          <span className="text-xs font-medium text-gray-500 block">Flagged for Review</span>
          <div className="mt-2 flex items-baseline justify-between">
            <span className={`text-2xl font-bold ${(stats?.flagged_invoices || 0) > 0 ? 'text-amber-600' : 'text-gray-900'}`}>
              {stats?.flagged_invoices || 0}
            </span>
            <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded font-medium">
              {stats?.high_risk_count || 0} high risk
            </span>
          </div>
        </div>
      </div>

      {/* Priority Section: Invoices Requiring Review & Recent Activity */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Recent Invoices</h2>
            <p className="text-xs text-gray-500 mt-0.5">Latest documents ingested into the processing pipeline</p>
          </div>
          <Link
            to="/invoices"
            className="text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            <span>View all invoices</span>
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500 font-medium border-b border-gray-200">
              <tr>
                <th className="py-2.5 px-4">Invoice #</th>
                <th className="py-2.5 px-4">Vendor</th>
                <th className="py-2.5 px-4">Date</th>
                <th className="py-2.5 px-4 text-right">Amount ({currency})</th>
                <th className="py-2.5 px-4 text-center">Status</th>
                <th className="py-2.5 px-4 text-center">Risk Level</th>
                <th className="py-2.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {recentInvoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500">
                    No invoices recorded yet. Click "Upload Invoice" to get started.
                  </td>
                </tr>
              ) : (
                recentInvoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      <Link to={`/invoices/${inv.id}/result`} className="hover:text-blue-600 hover:underline">
                        {inv.invoice_number || `INV-${inv.id}`}
                      </Link>
                    </td>
                    <td className="py-3 px-4 text-gray-700 truncate max-w-[180px]">{inv.vendor_name || 'N/A'}</td>
                    <td className="py-3 px-4 text-gray-500">{inv.invoice_date || 'N/A'}</td>
                    <td className="py-3 px-4 text-right font-medium text-gray-900">
                      {formatAmount(inv.total_amount)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                          inv.status === 'approved'
                            ? 'bg-green-50 text-green-700 border border-green-200'
                            : inv.status === 'rejected'
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : inv.status === 'flagged'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-blue-50 text-blue-700 border border-blue-200'
                        }`}
                      >
                        {inv.status === 'pending_review' ? 'Pending' : inv.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium ${
                          inv.risk_level === 'High'
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : inv.risk_level === 'Medium'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-gray-100 text-gray-700 border border-gray-200'
                        }`}
                      >
                        {inv.risk_level} ({inv.risk_score})
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        to={`/invoices/${inv.id}/result`}
                        className="text-xs font-medium text-blue-600 hover:text-blue-800 hover:underline"
                      >
                        Review
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Secondary Information: Processing Trend & Validation Status */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Processing Activity Trend (7 cols) */}
        <div className="lg:col-span-7 bg-white border border-gray-200 rounded-lg p-5 space-y-3">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Processing Volume Trend</h2>
            <p className="text-xs text-gray-500">Invoices processed over recent dates</p>
          </div>

          <div className="h-56 w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={analytics?.processing_over_time || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#e2e8f0',
                    borderRadius: '6px',
                    fontSize: '12px',
                    boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
                  }}
                  itemStyle={{ color: '#2563eb' }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#2563eb"
                  strokeWidth={2}
                  fill="#dbeafe"
                  name="Invoices"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Status & Alerts Overview (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-gray-200 rounded-lg p-5 flex flex-col justify-between space-y-4">
          <div>
            <h2 className="text-base font-semibold text-gray-900">Validation & Status Summary</h2>
            <p className="text-xs text-gray-500">Breakdown of active invoice verification states</p>
          </div>

          <div className="space-y-2.5">
            <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded border border-gray-100 text-xs">
              <span className="text-gray-600 font-medium">Approved Invoices</span>
              <span className="font-semibold text-green-700 bg-green-50 px-2 py-0.5 rounded border border-green-200">
                {stats?.approved_invoices || 0}
              </span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded border border-gray-100 text-xs">
              <span className="text-gray-600 font-medium">Pending Review</span>
              <span className="font-semibold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                {stats?.pending_invoices || 0}
              </span>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded border border-gray-100 text-xs">
              <span className="text-gray-600 font-medium">Duplicate Alerts</span>
              <Link
                to="/duplicates"
                className="font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 hover:underline"
              >
                {stats?.duplicate_alerts || 0} detected
              </Link>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded border border-gray-100 text-xs">
              <span className="text-gray-600 font-medium">High Risk Invoices</span>
              <Link
                to="/risk-analysis"
                className="font-semibold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200 hover:underline"
              >
                {stats?.high_risk_count || 0} flagged
              </Link>
            </div>

            <div className="flex items-center justify-between p-2.5 bg-gray-50 rounded border border-gray-100 text-xs">
              <span className="text-gray-600 font-medium">Rejected Invoices</span>
              <span className="font-semibold text-gray-700 bg-gray-100 px-2 py-0.5 rounded border border-gray-200">
                {stats?.rejected_invoices || 0}
              </span>
            </div>
          </div>

          {/* Quick link */}
          <div className="pt-2 border-t border-gray-100">
            <Link
              to="/invoices"
              className="text-xs text-blue-600 hover:text-blue-800 font-medium flex items-center justify-center gap-1"
            >
              <span>Go to Full Invoice Archive</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
