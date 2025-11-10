import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getCurrentUser, logout as apiLogout } from "../api/agent";

type AuthContextValue = {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string, userInfo?: Record<string, unknown>) => void;
  logout: () => Promise<void>;
  userInfo: Record<string, unknown> | null;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY_TOKEN = "agent_token";
const STORAGE_KEY_USER = "agent_user";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY_TOKEN));
  const [userInfo, setUserInfo] = useState<Record<string, unknown> | null>(() => {
    const stored = localStorage.getItem(STORAGE_KEY_USER);
    if (!stored) return null;
    try {
      return JSON.parse(stored);
    } catch (error) {
      console.warn("Failed to parse stored user info", error);
      return null;
    }
  });

  useEffect(() => {
    if (!token || userInfo) return;

    let cancelled = false;
    (async () => {
      try {
        const current = await getCurrentUser();
        if (!cancelled && current?.username) {
          setUserInfo({ username: current.username });
        }
      } catch (error) {
        console.warn("Failed to fetch current user info", error);
        setToken(null);
        localStorage.removeItem(STORAGE_KEY_TOKEN);
        localStorage.removeItem(STORAGE_KEY_USER);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, userInfo]);

  useEffect(() => {
    if (token) {
      localStorage.setItem(STORAGE_KEY_TOKEN, token);
    } else {
      localStorage.removeItem(STORAGE_KEY_TOKEN);
    }
  }, [token]);

  useEffect(() => {
    if (userInfo) {
      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(userInfo));
    } else {
      localStorage.removeItem(STORAGE_KEY_USER);
    }
  }, [userInfo]);

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      login: (newToken, info) => {
        setToken(newToken);
        if (info) {
          setUserInfo(info);
        } else {
          setUserInfo(null);
        }
      },
      logout: async () => {
        try {
          await apiLogout();
        } catch (error) {
          console.warn("Logout request failed", error);
        } finally {
          setToken(null);
          setUserInfo(null);
          localStorage.removeItem(STORAGE_KEY_TOKEN);
          localStorage.removeItem(STORAGE_KEY_USER);
        }
      },
      userInfo
    }),
    [token, userInfo]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
};
