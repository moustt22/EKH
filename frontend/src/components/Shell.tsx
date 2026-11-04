import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth";

export function Shell() {
  const { user, logout } = useAuth();
  const admin = user.role === "administrator";

  return (
    <div className="shell">
      <aside className="rail">
        <p className="mark">Northwind</p>
        <p className="mark-sub">Knowledge Hub</p>
        <nav>
          <NavLink to="/chat">Ask</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/documents">Documents</NavLink>
          {admin ? <NavLink to="/users">People</NavLink> : null}
          {admin ? <NavLink to="/audit">Audit</NavLink> : null}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <strong>{user.name}</strong>
            <span className="muted">
              {user.role.replaceAll("_", " ")} · {user.department_name}
            </span>
          </div>
          <button className="button secondary" type="button" onClick={() => void logout()}>
            Sign out
          </button>
        </header>
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
