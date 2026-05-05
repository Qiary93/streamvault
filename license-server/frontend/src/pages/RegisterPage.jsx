import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", full_name: "" });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (form.password.length < 8) return toast.error("Password must be at least 8 characters");
    setBusy(true);
    try {
      await register(form);
      toast.success("Account created");
      nav("/dashboard", { replace: true });
    } catch (err) {
      toast.error(err.response?.data?.detail || "Registration failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <h1 className="text-3xl font-black mb-2">Create your account</h1>
      <p className="text-muted mb-8">One account, all your licenses.</p>
      <form onSubmit={submit} className="space-y-4">
        <input
          required
          autoFocus
          placeholder="Full name (optional)"
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          className="w-full bg-surface border border-border rounded-lg px-4 py-3 focus:border-accent focus:outline-none"
        />
        <input
          type="email"
          required
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          className="w-full bg-surface border border-border rounded-lg px-4 py-3 focus:border-accent focus:outline-none"
        />
        <input
          type="password"
          required
          minLength={8}
          placeholder="Password (min 8 characters)"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
          className="w-full bg-surface border border-border rounded-lg px-4 py-3 focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={busy}
          className="w-full bg-accent text-black font-bold py-3 rounded-lg hover:bg-accent/80 disabled:opacity-50"
        >
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
      <p className="text-sm text-muted text-center mt-6">
        Already have one?{" "}
        <Link to="/login" className="text-accent hover:underline">Sign in</Link>
      </p>
    </div>
  );
}
