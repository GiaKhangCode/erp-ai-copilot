"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserProfile, fetchMeApi, getAuthToken, loginApi } from "./api";

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
  isAdmin: boolean;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  hasPermission: (permissionCode: string) => boolean;
  hasRole: (roleCode: string) => boolean;
  hasAnyRole: (roleCodes: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isLoading: true,
  isAdmin: false,
  login: async () => {},
  logout: () => {},
  refreshUser: async () => {},
  hasPermission: () => false,
  hasRole: () => false,
  hasAnyRole: () => false,
});

function setCookie(name: string, value: string, days = 7) {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

function deleteCookie(name: string) {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const initAuth = async () => {
    try {
      const storedToken = await getAuthToken();
      if (storedToken) {
        setToken(storedToken);
        setCookie("erp_access_token", storedToken);

        const storedUser = localStorage.getItem("erp_user");
        if (storedUser) {
          try {
            setUser(JSON.parse(storedUser));
          } catch {
            // ignore
          }
        }
        // Gọi API /auth/me để cập nhật profile và permissions mới nhất
        try {
          const profile = await fetchMeApi();
          setUser(profile);
          localStorage.setItem("erp_user", JSON.stringify(profile));
        } catch (err: any) {
          if (
            err?.message &&
            (err.message.includes("401") ||
              err.message.includes("hết hạn") ||
              err.message.includes("chưa được cấp quyền"))
          ) {
            localStorage.removeItem("erp_access_token");
            localStorage.removeItem("erp_user");
            deleteCookie("erp_access_token");
            setToken(null);
            setUser(null);
          }
        }
      }
    } catch {
      // offline fallback
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    initAuth();
  }, []);

  const login = async (email: string, pass: string) => {
    setIsLoading(true);
    try {
      const res = await loginApi(email, pass);
      setToken(res.access_token);
      setCookie("erp_access_token", res.access_token);
      setUser(res.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("erp_access_token");
      localStorage.removeItem("erp_user");
      deleteCookie("erp_access_token");
    }
    setToken(null);
    setUser(null);
  };

  const refreshUser = async () => {
    try {
      const profile = await fetchMeApi();
      setUser(profile);
      if (typeof window !== "undefined") {
        localStorage.setItem("erp_user", JSON.stringify(profile));
      }
    } catch {
      // ignore
    }
  };

  const isAdmin = Boolean(
    user?.is_superuser ||
      user?.role === "admin" ||
      user?.roles?.includes("admin") ||
      user?.permissions?.includes("*")
  );

  const hasPermission = (permissionCode: string): boolean => {
    if (!user) return false;
    if (user.is_superuser) return true;
    if (!user.permissions || user.permissions.length === 0) return false;
    if (user.permissions.includes("*")) return true;
    return user.permissions.includes(permissionCode);
  };

  const hasRole = (roleCode: string): boolean => {
    if (!user) return false;
    if (user.is_superuser) return true;
    if (user.role === roleCode) return true;
    return Boolean(user.roles?.includes(roleCode));
  };

  const hasAnyRole = (roleCodes: string[]): boolean => {
    if (!user) return false;
    if (user.is_superuser) return true;
    return roleCodes.some((code) => hasRole(code));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAdmin,
        login,
        logout,
        refreshUser,
        hasPermission,
        hasRole,
        hasAnyRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
