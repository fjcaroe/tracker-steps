import { createContext, useContext } from "react";
import type { CostCenterOut, UserOut } from "./auth";

export type AuthState = {
  token: string | null;
  user: UserOut | null;
  costCenters: CostCenterOut[];
  isReady: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};

export const AuthContext = createContext<AuthState | null>(null);

export function useAuthWeb() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuthWeb must be used within AuthProvider");
  return value;
}
