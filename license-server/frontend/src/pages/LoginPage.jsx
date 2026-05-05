import React, { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

export default function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const next = new URLSearchParams(loc.search).get("next") || "/dashboard";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      toast.success("Welcome back");
      nav(next, { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <h1 className="text-3xl font-black mb-2">Welcome back</h1>
      <p className="text-muted mb-8">Sign in to manage your licenses.</p>
      <form onSubmit={submit} className="space-y-4">
        <input
          type="email"
          required
          autoFocus
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-surface border border-border rounded-lg px-4 py-3 focus:border-accent focus:outline-none"
        />
        <input
          type="password"
          required
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full bg-surface border border-border rounded-lg px-4 py-3 focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="w-full bg-accent text-black font-bold py-3 rounded-lg hover:bg-accent/80 disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="text-sm text-muted text-center mt-6">
        Don't have an account?{" "}
        <Link to="/register" className="text-accent hover:underline">Create one</Link>
      </p>
    </div>
  );
}
