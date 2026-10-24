import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, User as UserIcon, LogOut, ExternalLink, Building2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useCurrency } from '../context/CurrencyContext';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const { currency, setCurrency } = useCurrency();

  const getRoleBadge = (role?: string) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'reviewer':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6 z-30 sticky top-0">
      {/* Brand & Identity */}
      <div className="flex items-center space-x-3">
        <Link to="/dashboard" className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center text-white">
            <Shield className="w-4 h-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-gray-900 tracking-tight">
              InvoShield
            </span>
            <span className="hidden sm:inline-block text-xs text-gray-500 font-normal border-l border-gray-200 pl-2">
              Invoice Processing System
            </span>
          </div>
        </Link>
      </div>

      {/* Right User & Org Controls */}
      <div className="flex items-center space-x-3">
        {/* Currency Switcher */}
        <div
          className="flex items-center bg-gray-100 p-0.5 rounded-md border border-gray-200 text-xs"
          role="group"
          aria-label="Currency Selector"
        >
          <button
            type="button"
            onClick={() => setCurrency('USD')}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all ${
              currency === 'USD'
                ? 'bg-white text-blue-700 shadow-xs border border-gray-200'
                : 'text-gray-500 hover:text-gray-900 border border-transparent'
            }`}
            title="Display amounts in US Dollars ($)"
          >
            $ USD
          </button>
          <button
            type="button"
            onClick={() => setCurrency('INR')}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all ${
              currency === 'INR'
                ? 'bg-white text-blue-700 shadow-xs border border-gray-200'
                : 'text-gray-500 hover:text-gray-900 border border-transparent'
            }`}
            title="Display amounts in Indian Rupees (₹)"
          >
            ₹ INR
          </button>
        </div>

        <Link
          to="/"
          target="_blank"
          className="text-xs text-gray-500 hover:text-gray-900 flex items-center gap-1 transition-colors px-2.5 py-1 rounded hover:bg-gray-100"
          title="System Architecture & Docs"
        >
          <span className="hidden md:inline">Documentation</span>
          <ExternalLink className="w-3 h-3" />
        </Link>

        {user ? (
          <div className="flex items-center space-x-3 border-l border-gray-200 pl-3">
            {/* Organization Tag */}
            <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded bg-gray-50 border border-gray-200 text-xs text-gray-700">
              <Building2 className="w-3.5 h-3.5 text-gray-500" />
              <span className="truncate max-w-[140px] font-medium">{user.organization || 'Enterprise'}</span>
            </div>

            {/* User Profile */}
            <div className="flex items-center space-x-2">
              <div className="w-7 h-7 rounded bg-gray-100 border border-gray-200 flex items-center justify-center text-gray-700 text-xs font-semibold">
                {user.name ? user.name.charAt(0).toUpperCase() : <UserIcon className="w-3.5 h-3.5" />}
              </div>
              <div className="hidden sm:flex flex-col text-left">
                <span className="text-xs font-medium text-gray-900 leading-tight">{user.name}</span>
                <span className={`text-[10px] capitalize px-1.5 py-0.2 rounded border w-fit leading-tight mt-0.5 font-medium ${getRoleBadge(user.role)}`}>
                  {user.role}
                </span>
              </div>
            </div>

            {/* Logout Action */}
            <button
              onClick={logout}
              className="p-1.5 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="flex items-center space-x-2">
            <Link
              to="/login"
              className="px-3 py-1.5 rounded text-xs font-medium text-gray-700 hover:bg-gray-100 transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="px-3 py-1.5 rounded text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              Register
            </Link>
          </div>
        )}
      </div>
    </header>
  );
};
