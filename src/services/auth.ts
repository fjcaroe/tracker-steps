// src/services/auth.ts
import { apiJson, setToken } from "./http";

export type UserOut = { id: number; username: string; full_name: string };
export type CostCenterOut = { id: number; name: string; external_id?: string | null; hectares?: number | null };

export type TokenOut = {
  access_token: string;
  token_type: string;
  user: UserOut;
  cost_centers: CostCenterOut[];
};

export async function login(username: string, password: string): Promise<TokenOut> {
  const data = await apiJson<TokenOut>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

  setToken(data.access_token);
  return data;
}

export function logout() {
  setToken(null);
}
