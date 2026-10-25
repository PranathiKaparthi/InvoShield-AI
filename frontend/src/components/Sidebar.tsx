import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  UploadCloud,
  FileText,
  CopyCheck,
  AlertTriangle,
  ShieldAlert,
  CheckSquare,
  MessageCircle,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Sidebar: React.FC<{ open?: boolean; onClose?: () => void }> = ({ open = false, onClose }) => {
  const { isAdmin, isReviewer } = useAuth();

  const getNavItems = () => {
    if (isAdmin) {
      return [
        { label: 'Executive Overview', path: '/dashboard', icon: LayoutDashboard },
        { label: 'Upload Invoices', path: '/upload', icon: UploadCloud },
        { label: 'Invoice Archive', path: '/invoices', icon: FileText },
        { label: 'Duplicate Detection', path: '/duplicates', icon: CopyCheck },
        { label: 'Fraud & Risk Engine', path: '/risk-analysis', icon: AlertTriangle },
        { label: 'Assistant Inbox', path: '/assistant', icon: MessageCircle },
      ];
    }
    if (isReviewer) {
      return [
        { label: 'AP Dashboard', path: '/dashboard', icon: LayoutDashboard },
        { label: 'Upload Invoices', path: '/upload', icon: UploadCloud },
        { label: 'Invoice Review Queue', path: '/invoices', icon: CheckSquare },
        { label: 'Duplicate Detection', path: '/duplicates', icon: CopyCheck },
        { label: 'Fraud & Risk Engine', path: '/risk-analysis', icon: AlertTriangle },
        { label: 'Assistant Inbox', path: '/assistant', icon: MessageCircle },
      ];
    }
    // Standard User
    return [
      { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
      { label: 'Upload Invoice', path: '/upload', icon: UploadCloud },
      { label: 'My Invoices', path: '/invoices', icon: FileText },
      { label: 'Duplicate Check', path: '/duplicates', icon: CopyCheck },
      { label: 'Risk Insights', path: '/risk-analysis', icon: AlertTriangle },
    ];
  };

  const navItems = getNavItems();

  return (
    <>
    {/* Phone: dimmed backdrop behind the drawer */}
    {open && <div className="fixed inset-0 top-14 bg-black/30 z-30 md:hidden" onClick={onClose} aria-hidden="true" />}
    <aside
      className={`w-56 bg-white border-r border-gray-200 flex-col justify-between shrink-0 min-h-[calc(100vh-3.5rem)]
        md:flex md:static md:z-auto
        ${open ? 'flex fixed top-14 left-0 bottom-0 z-40 shadow-xl overflow-y-auto' : 'hidden'}`}
    >
      <div className="p-3 space-y-4">
        <div className="space-y-1">
          <div className="px-3 py-1 flex items-center justify-between">
            <span className="text-[11px] font-semibold tracking-wider text-gray-400 uppercase">
              {isAdmin ? 'System Core' : isReviewer ? 'Operations' : 'Workspace'}
            </span>
          </div>

          <nav className="space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center space-x-2.5 px-3 py-2 text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-50 text-blue-700 border-l-2 border-blue-600 font-semibold'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-r-md'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0 text-gray-500" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {isAdmin && (
          <div className="space-y-1 pt-3 border-t border-gray-100">
            <span className="px-3 text-[11px] font-semibold tracking-wider text-gray-400 uppercase block mb-1">
              Administration
            </span>
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `flex items-center space-x-2.5 px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 border-l-2 border-blue-600 font-semibold'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-r-md'
                }`
              }
            >
              <ShieldAlert className="w-4 h-4 text-gray-500 shrink-0" />
              <span>Admin Center</span>
            </NavLink>
          </div>
        )}
      </div>

      <div className="p-3 border-t border-gray-100 text-[11px] text-gray-400 space-y-1">
        <p className="font-medium text-gray-600">InvoShield AI</p>
        <p className="text-[10px]">Accounts Payable System</p>
      </div>
    </aside>
    </>
  );
};
