import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider, LoginGate, RequireAuth } from "./auth";
import { Shell } from "./components/Shell";
import { Audit } from "./pages/Audit";
import { Chat } from "./pages/Chat";
import { DocumentDetail } from "./pages/DocumentDetail";
import { Documents } from "./pages/Documents";
import { Login } from "./pages/Login";
import { Search } from "./pages/Search";
import { Users } from "./pages/Users";

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<LoginGate />}>
            <Route path="/login" element={<Login />} />
          </Route>
          <Route element={<RequireAuth />}>
            <Route element={<Shell />}>
              <Route index element={<Navigate to="/chat" replace />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/chat/:id" element={<Chat />} />
              <Route path="/search" element={<Search />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/documents/:id" element={<DocumentDetail />} />
              <Route path="/users" element={<Users />} />
              <Route path="/audit" element={<Audit />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
