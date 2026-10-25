import React, { createContext, useContext, useState, useEffect } from 'react';
import { User, UserRole } from '../types';
import { authApi } from '../services/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (credentials: any) => Promise<void>;
  register: (data: any) => Promise<void>;
  logout: () => void;
  updateUser: (u: User) => void;
  isAdmin: boolean;
  isReviewer: boolean;
  canApprove: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('invoshield_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('invoshield_token'));
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('invoshield_token');
      if (storedToken) {
        try {
          const res = await authApi.getMe();
          setUser(res.data);
          localStorage.setItem('invoshield_user', JSON.stringify(res.data));
        } catch (err) {
          localStorage.removeItem('invoshield_token');
          localStorage.removeItem('invoshield_user');
          setUser(null);
          setToken(null);
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const login = async (credentials: any) => {
    const res = await authApi.login(credentials);
    const { access_token, user: userData } = res.data;
    localStorage.setItem('invoshield_token', access_token);
    localStorage.setItem('invoshield_user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
  };

  const register = async (data: any) => {
    const res = await authApi.register(data);
    const { access_token, user: userData } = res.data;
    localStorage.setItem('invoshield_token', access_token);
    localStorage.setItem('invoshield_user', JSON.stringify(userData));
    setToken(access_token);
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('invoshield_token');
    localStorage.removeItem('invoshield_user');
    setToken(null);
    setUser(null);
    window.location.href = '/login';
  };

  const updateUser = (u: User) => {
    localStorage.setItem('invoshield_user', JSON.stringify(u));
    setUser(u);
  };

  const isAdmin = user?.role === 'admin';
  const isReviewer = user?.role === 'reviewer';
  const canApprove = isAdmin || isReviewer;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        updateUser,
        isAdmin,
        isReviewer,
        canApprove,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
