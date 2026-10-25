import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Users,
  History,
  AlertTriangle,
  Check,
} from 'lucide-react';
import { adminApi } from '../services/api';
import { User, Invoice } from '../types';
import { useCurrency } from '../context/CurrencyContext';

export const AdminDashboardPage: React.FC = () => {
  const { currency, formatAmount } = useCurrency();
  const [users, setUsers] = useState<User[]>([]);
  const [flagged, setFlagged] = useState<Invoice[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [msg, setMsg] = useState<string | null>(null);

  const fetchAdminData = async () => {
    try {
      setLoading(true);
      const [uRes, fRes, aRes] = await Promise.all([
        adminApi.getUsers(),
        adminApi.getFlagged(),
        adminApi.getAuditLogs(),
      ]);
      setUsers(uRes.data);
      setFlagged(fRes.data);
      setAuditLogs(aRes.data);
    } catch (err) {
      console.error('Failed to load admin data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleRoleChange = async (userId: number, newRole: string) => {
    try {
      await adminApi.updateUserRole(userId, newRole);
      setMsg(`User role updated to '${newRole}'.`);
      setTimeout(() => setMsg(null), 3500);
      fetchAdminData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update role.');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[300px]">
        <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 tracking-tight">Admin & User Management</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Manage user roles, triage flagged invoices, and inspect system audit events.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2.5 py-1 rounded bg-white border border-gray-200 text-gray-700 font-mono">
            {users.length} Users
          </span>
          <span className="px-2.5 py-1 rounded bg-amber-50 border border-amber-200 text-amber-800 font-mono font-medium">
            {flagged.length} Flagged
          </span>
        </div>
      </div>

      {msg && (
        <div className="p-3 rounded bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{msg}</span>
        </div>
      )}

      {/* Flagged Invoices Queue */}
      <div className="bg-white border border-gray-200 rounded shadow-xs overflow-hidden">
        <div className="p-3.5 border-b border-gray-200 flex items-center justify-between bg-gray-50/70">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <h2 className="text-xs font-semibold text-gray-800 uppercase tracking-wide">
              Flagged Invoices Pending Triage
            </h2>
          </div>
          <span className="text-xs font-mono text-gray-500">
            {flagged.length} require action
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-600 font-medium border-b border-gray-200">
              <tr>
                <th className="py-2.5 px-3.5">Invoice #</th>
                <th className="py-2.5 px-3.5">Vendor</th>
                <th className="py-2.5 px-3.5 text-right">Amount ({currency})</th>
                <th className="py-2.5 px-3.5 text-center">Status</th>
                <th className="py-2.5 px-3.5 text-center">Risk Tier</th>
                <th className="py-2.5 px-3.5 text-center">Duplicate Status</th>
                <th className="py-2.5 px-3.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {flagged.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500 text-xs">
                    No flagged or high-risk invoices currently pending triage.
                  </td>
                </tr>
              ) : (
                flagged.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-2.5 px-3.5 font-mono font-medium text-gray-900">
                      #{inv.invoice_number || inv.id}
                    </td>
                    <td className="py-2.5 px-3.5 text-gray-800">{inv.vendor_name || 'Unknown'}</td>
                    <td className="py-2.5 px-3.5 font-mono font-medium text-gray-900 text-right">
                      {formatAmount(inv.total_amount, 2, inv.currency)}
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono uppercase bg-amber-50 text-amber-800 border border-amber-200">
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold border ${
                        inv.risk_level === 'High' ? 'bg-red-50 text-red-700 border-red-200' :
                        inv.risk_level === 'Medium' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                        'bg-emerald-50 text-emerald-700 border-emerald-200'
                      }`}>
                        {inv.risk_level} ({inv.risk_score})
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center font-mono text-xs text-gray-600">
                      {inv.duplicate_status}
                    </td>
                    <td className="py-2.5 px-3.5 text-right">
                      <Link
                        to={`/invoices/${inv.id}/result`}
                        className="px-2.5 py-1 rounded bg-white hover:bg-gray-50 border border-gray-300 text-blue-600 hover:text-blue-800 text-xs font-medium transition-colors"
                      >
                        Inspect
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* User Governance Table */}
      <div className="bg-white border border-gray-200 rounded shadow-xs overflow-hidden">
        <div className="p-3.5 border-b border-gray-200 flex items-center justify-between bg-gray-50/70">
          <div className="flex items-center space-x-2">
            <Users className="w-4 h-4 text-blue-600" />
            <h2 className="text-xs font-semibold text-gray-800 uppercase tracking-wide">
              User Accounts & Role Permissions
            </h2>
          </div>
          <span className="text-xs font-mono text-gray-500">{users.length} Accounts</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-600 font-medium border-b border-gray-200">
              <tr>
                <th className="py-2.5 px-3.5">Name</th>
                <th className="py-2.5 px-3.5">Email</th>
                <th className="py-2.5 px-3.5">Organization</th>
                <th className="py-2.5 px-3.5 text-center">Assigned Role</th>
                <th className="py-2.5 px-3.5 text-right">Change Role</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="py-2.5 px-3.5 font-medium text-gray-900">{u.name}</td>
                  <td className="py-2.5 px-3.5 font-mono text-gray-500 text-[11px]">{u.email}</td>
                  <td className="py-2.5 px-3.5 text-gray-700">{u.organization}</td>
                  <td className="py-2.5 px-3.5 text-center">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border ${
                      u.role === 'admin' ? 'bg-purple-50 text-purple-700 border-purple-200' :
                      u.role === 'reviewer' ? 'bg-blue-50 text-blue-700 border-blue-200' :
                      'bg-gray-100 text-gray-700 border-gray-200'
                    }`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2.5 px-3.5 text-right">
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      aria-label={`Change role for ${u.name}`}
                      className="px-2.5 py-1 rounded bg-white border border-gray-300 text-xs font-sans text-gray-800 focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="admin">Admin</option>
                      <option value="reviewer">Reviewer</option>
                      <option value="user">User</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* System Audit Trail */}
      <div className="bg-white border border-gray-200 rounded shadow-xs overflow-hidden">
        <div className="p-3.5 border-b border-gray-200 flex items-center justify-between bg-gray-50/70">
          <div className="flex items-center space-x-2">
            <History className="w-4 h-4 text-gray-500" />
            <h2 className="text-xs font-semibold text-gray-800 uppercase tracking-wide">
              System Audit Activity Log
            </h2>
          </div>
          <span className="text-xs font-mono text-gray-500">Immutable Ledger</span>
        </div>

        <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
          {auditLogs.length === 0 ? (
            <div className="p-6 text-center text-xs text-gray-500">No audit events recorded yet.</div>
          ) : (
            auditLogs.map((log) => (
              <div key={log.id} className="p-3 flex items-center justify-between text-xs hover:bg-gray-50/50">
                <div className="flex items-center space-x-2.5 min-w-0">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-gray-100 text-gray-700 border border-gray-200 shrink-0">
                    {log.action}
                  </span>
                  <span className="text-gray-800 font-sans truncate">{log.details}</span>
                </div>
                <div className="flex items-center space-x-3 text-gray-500 text-xs shrink-0 font-mono">
                  <span>by {log.user_name} ({log.user_role})</span>
                  <span>{log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}</span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
