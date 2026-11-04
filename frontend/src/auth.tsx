import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";

import { api } from "./api";
import type { User } from "./types";

const TOKEN_KEY = "ekh.token";

type Session = {
  token: string | null;
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!token) {
      setUser(null);
      setReady(true);
      return;
    }
    let cancelled = false;
    api<User>("/auth/me", {}, token)
      .then((me) => {
        if (!cancelled) {
          setUser(me);
        }
      })
      .catch(() => {
        sessionStorage.removeItem(TOKEN_KEY);
        if (!cancelled) {
          setToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReady(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function login(email: string, password: string) {
    const response = await api<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    const me = await api<User>("/auth/me", {}, response.access_token);
    sessionStorage.setItem(TOKEN_KEY, response.access_token);
    setUser(me);
    setToken(response.access_token);
    setReady(true);
  }

  async function logout() {
    if (token) {
      await api("/auth/logout", { method: "POST" }, token).catch(() => undefined);
    }
    sessionStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setToken(null);
  }

  return (
    <SessionContext.Provider value={{ token, user, ready, login, logout }}>{children}</SessionContext.Provider>
  );
}

function useSession(): Session {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("Session missing");
  }
  return value;
}

export function useAuth(): Session & { token: string; user: User } {
  const session = useSession();
  if (!session.token || !session.user) {
    throw new Error("Not signed in");
  }
  return session as Session & { token: string; user: User };
}

export function RequireAuth() {
  const session = useSession();
  if (!session.ready) {
    return <p className="boot">Opening the hub…</p>;
  }
  if (!session.user) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}

export function LoginGate() {
  const session = useSession();
  if (!session.ready) {
    return <p className="boot">Opening the hub…</p>;
  }
  if (session.user) {
    return <Navigate to="/chat" replace />;
  }
  return <Outlet />;
}

export function useLogin(): Session["login"] {
  return useSession().login;
}

export function canUpload(user: User): boolean {
  return user.role === "administrator" || user.role === "department_manager";
}

export function canManageDocument(user: User, departmentId: string): boolean {
  if (user.role === "administrator") {
    return true;
  }
  return user.role === "department_manager" && user.department_id === departmentId;
}
