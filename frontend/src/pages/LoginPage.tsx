import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Shield, Lock, Mail, ArrowRight, AlertCircle, KeyRound } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();

  const isExpired = searchParams.get('expired') === '1';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login({ email, password });
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed. Please check your email and password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const fillDemo = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setError(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-center items-center px-4 py-12 font-sans">
      <div className="w-full max-w-sm space-y-5">
        {/* Header Branding */}
        <div className="text-center space-y-1">
          <Link to="/" className="inline-flex items-center space-x-2">
            <div className="w-8 h-8 rounded bg-blue-600 text-white flex items-center justify-center font-bold">
              <Shield className="w-4 h-4" />
            </div>
            <span className="text-lg font-bold text-gray-900 tracking-tight">
              InvoShield
            </span>
          </Link>
          <h2 className="text-sm font-semibold text-gray-800">Sign in to your account</h2>
          <p className="text-xs text-gray-500">Automated invoice validation & fraud detection</p>
        </div>

        {isExpired && (
          <div className="p-2.5 rounded bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-amber-600" />
            <span>Session expired. Please log in again.</span>
          </div>
        )}

        {error && (
          <div className="p-2.5 rounded bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form Box */}
        <div className="p-5 rounded bg-white border border-gray-200 shadow-xs space-y-4">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Email address</label>
              <div className="relative">
                <Mail className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  className="w-full pl-8 pr-3 py-1.5 rounded border border-gray-300 text-gray-900 placeholder-gray-400 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full pl-8 pr-3 py-1.5 rounded border border-gray-300 text-gray-900 placeholder-gray-400 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-2 rounded font-medium bg-blue-600 hover:bg-blue-700 text-white flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 text-xs mt-1"
            >
              {isSubmitting ? 'Signing In...' : 'Sign In'}
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>

          {/* Quick-Fill Demo Credentials */}
          <div className="pt-3 border-t border-gray-200 space-y-2">
            <div className="flex items-center gap-1 text-[11px] font-mono text-gray-500">
              <KeyRound className="w-3 h-3 text-blue-600" />
              <span>Demo Test Accounts:</span>
            </div>
            <div className="grid grid-cols-3 gap-1.5">
              <button
                type="button"
                onClick={() => fillDemo('reviewer@invoshield.ai', 'Reviewer@12345')}
                className="px-2 py-1.5 rounded bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-700 text-xs font-medium transition-colors"
                title="Reviewer Role (Can approve/reject invoices, enforces Segregation of Duties)"
              >
                Reviewer
              </button>
              <button
                type="button"
                onClick={() => fillDemo('admin@invoshield.ai', 'Admin@12345')}
                className="px-2 py-1.5 rounded bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-700 text-xs font-medium transition-colors"
                title="Admin Role (User management, audit logs, triage queue)"
              >
                Admin
              </button>
              <button
                type="button"
                onClick={() => fillDemo('user@invoshield.ai', 'User@12345')}
                className="px-2 py-1.5 rounded bg-gray-50 hover:bg-gray-100 border border-gray-200 text-gray-700 text-xs font-medium transition-colors"
                title="Submitter Role (Upload invoices and track statuses)"
              >
                Submitter
              </button>
            </div>
          </div>
        </div>

        <p className="text-center text-xs text-gray-500">
          Need an account?{' '}
          <Link to="/register" className="text-blue-600 hover:underline font-medium">
            Register new account
          </Link>
        </p>
      </div>
    </div>
  );
};
