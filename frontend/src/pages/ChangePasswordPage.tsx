import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { KeyRound } from 'lucide-react';
import { authApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const ChangePasswordPage: React.FC = () => {
  const { user, updateUser, logout } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (next.length < 10) return setError('Use at least 10 characters.');
    if (next !== confirm) return setError('The new passwords do not match.');
    setBusy(true);
    try {
      const res = await authApi.changePassword(current, next);
      updateUser(res.data);
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Could not change the password.');
    } finally {
      setBusy(false);
    }
  };

  const input = 'w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500';

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <form onSubmit={submit} className="w-full max-w-sm bg-white border border-gray-200 rounded-lg p-6 space-y-4">
        <div className="flex items-center gap-2">
          <KeyRound className="w-5 h-5 text-blue-600" />
          <h1 className="text-lg font-semibold text-gray-900">Set a new password</h1>
        </div>
        <p className="text-xs text-gray-500">
          {user?.must_change_password
            ? 'Your account was created with an initial password. Choose your own before continuing.'
            : 'Change the password for your account.'}
        </p>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-600">Current password</span>
          <input type="password" required className={input} value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-600">New password (10+ characters)</span>
          <input type="password" required className={input} value={next} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-gray-600">Confirm new password</span>
          <input type="password" required className={input} value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="new-password" />
        </label>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button type="submit" disabled={busy}
          className="w-full py-2 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {busy ? 'Saving…' : 'Save password'}
        </button>
        <button type="button" onClick={logout} className="w-full text-xs text-gray-500 hover:text-gray-700">
          Sign out
        </button>
      </form>
    </div>
  );
};

export default ChangePasswordPage;
