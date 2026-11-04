import { FormEvent, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import type { Department, User } from "../types";

export function Users() {
  const { token, user } = useAuth();
  const [people, setPeople] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("ChangeMe123!");
  const [departmentId, setDepartmentId] = useState("");
  const [role, setRole] = useState("employee");
  const [error, setError] = useState("");
  const admin = user.role === "administrator";

  async function refresh() {
    setPeople(await api<User[]>("/users", {}, token));
  }

  useEffect(() => {
    if (!admin) {
      return;
    }
    void refresh().catch((caught) => setError(messageOf(caught)));
    void api<Department[]>("/departments", {}, token)
      .then((items) => {
        setDepartments(items);
        setDepartmentId(items[0]?.id ?? "");
      })
      .catch((caught) => setError(messageOf(caught)));
  }, [token, admin]);

  if (!admin) {
    return <Navigate to="/documents" replace />;
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api(
        "/users",
        { method: "POST", body: JSON.stringify({ name, email, password, department_id: departmentId, role }) },
        token,
      );
      setName("");
      setEmail("");
      await refresh();
    } catch (caught) {
      setError(messageOf(caught));
    }
  }

  async function toggle(person: User) {
    await api(`/users/${person.id}`, { method: "PATCH", body: JSON.stringify({ is_active: !person.is_active }) }, token);
    await refresh();
  }

  return (
    <section className="page">
      <h1>People</h1>
      <form className="card form-grid" onSubmit={(event) => void onCreate(event)}>
        <label>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} required />
        </label>
        <label>
          Email
          <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label>
          Password
          <input value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required />
        </label>
        <label>
          Department
          <select value={departmentId} onChange={(event) => setDepartmentId(event.target.value)}>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Role
          <select value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="employee">employee</option>
            <option value="department_manager">department manager</option>
            <option value="administrator">administrator</option>
          </select>
        </label>
        <button className="button" type="submit">
          Add person
        </button>
      </form>
      {error ? <p className="error">{error}</p> : null}
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Department</th>
            <th>Role</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={person.id}>
              <td>{person.name}</td>
              <td>{person.email}</td>
              <td>{person.department_name}</td>
              <td>{person.role.replaceAll("_", " ")}</td>
              <td>{person.is_active ? "active" : "inactive"}</td>
              <td>
                <button type="button" onClick={() => void toggle(person)}>
                  {person.is_active ? "Deactivate" : "Activate"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function messageOf(caught: unknown): string {
  return caught instanceof ApiError ? caught.message : "People could not be loaded";
}
