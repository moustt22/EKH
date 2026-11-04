import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useLogin } from "../auth";

const DEMOS = [
  ["admin@northwind.example", "Administrator"],
  ["hr.manager@northwind.example", "HR manager"],
  ["eng.employee@northwind.example", "Engineer"],
];

export function Login() {
  const login = useLogin();
  const navigate = useNavigate();
  const [email, setEmail] = useState("eng.employee@northwind.example");
  const [password, setPassword] = useState("ChangeMe123!");
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await login(email, password);
      navigate("/chat");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed");
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={(event) => void onSubmit(event)}>
        <p className="eyebrow">Northwind</p>
        <h1>Enterprise Knowledge Hub</h1>
        <p className="lede">Ask the company library. Answers stay inside the documents you are allowed to read.</p>
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error ? <p className="error">{error}</p> : null}
        <button className="button" type="submit">
          Sign in
        </button>
        <ul className="demo-accounts">
          {DEMOS.map(([address, label]) => (
            <li key={address}>
              <button type="button" onClick={() => setEmail(address)}>
                {label}
              </button>
              <span>{address}</span>
            </li>
          ))}
        </ul>
      </form>
    </div>
  );
}
