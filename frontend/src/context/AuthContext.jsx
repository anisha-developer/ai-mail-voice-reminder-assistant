import { createContext, useContext, useEffect, useState } from "react";
import { apiRequest, clearToken, getToken, setToken } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const bootstrap = async () => {
      if (!getToken()) {
        setLoading(false);
        return;
      }

      try {
        const me = await apiRequest("/users/me");
        setUser(me);
      } catch {
        clearToken();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    bootstrap();
  }, []);

  const login = (token, nextUser) => {
    setToken(token);
    setUser(nextUser);
  };

  const logout = () => {
    clearToken();
    setUser(null);
  };

  return <AuthContext.Provider value={{ user, setUser, login, logout, loading }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

