// src/services/AuthContext.tsx
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getToken, setToken, apiJson } from "./http";
import type { CostCenterOut, UserOut } from "./auth";
import { login as loginApi, logout as logoutApi } from "./auth";

type AuthState = {
  token: string | null;
  user: UserOut | null;
  costCenters: CostCenterOut[];
  isReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getToken());
  const [user, setUser] = useState<UserOut | null>(null);
  const [costCenters, setCostCenters] = useState<CostCenterOut[]>([]);
  const [isReady, setIsReady] = useState(false);

  // “Hidratación”: si hay token guardado, intentamos cargar /auth/me y /auth/me/cost_centers
  useEffect(() => {
    (async () => {
      const t = getToken();
      setTokenState(t);

      if (!t) {
        setIsReady(true);
        return;
      }

      try {
        const me = await apiJson<UserOut>("/auth/me");
        const ccs = await apiJson<CostCenterOut[]>("/auth/me/cost_centers");
        setUser(me);
        setCostCenters(ccs);
      } catch (e: any) {
        // Si falló (401 típico), limpiamos
        setToken(null);
        setTokenState(null);
        setUser(null);
        setCostCenters([]);
      } finally {
        setIsReady(true);
      }
    })();
  }, []);

  const value = useMemo<AuthState>(() => ({
    token,
    user,
    costCenters,
    isReady,
    login: async (username: string, password: string) => {
      const data = await loginApi(username, password);
      setTokenState(data.access_token);
      setUser(data.user);
      setCostCenters(data.cost_centers);
    },
    logout: () => {
      logoutApi();
      setTokenState(null);
      setUser(null);
      setCostCenters([]);
    },
  }), [token, user, costCenters, isReady]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuthWeb() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuthWeb must be used within AuthProvider");
  return v;
}
