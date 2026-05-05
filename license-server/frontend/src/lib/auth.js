import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { auth } from "./api";

const Ctx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await auth.me();
      setUser(data);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const login = async (email, password) => {
    const { data } = await auth.login({ email, password });
    setUser(data);
    return data;
  };
  const register = async (payload) => {
    const { data } = await auth.register(payload);
    setUser(data);
    return data;
  };
  const logout = async () => {
    await auth.logout();
    setUser(null);
  };

  return (
    <Ctx.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
