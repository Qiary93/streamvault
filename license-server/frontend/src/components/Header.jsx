import React from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { SignOut, User } from "@phosphor-icons/react";

export default function Header() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  return (
    <header className="border-b border-border/60 backdrop-blur sticky top-0 z-30 bg-bg/80">
      <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <span className="font-black text-xl tracking-tight">
            Dramaro<span className="text-accent">Sub</span>
          </span>
          <span className="text-[10px] text-muted uppercase tracking-widest border border-border/60 rounded px-1.5 py-0.5">
            License
          </span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          {[
            { to: "/", label: "Home" },
            { to: "/pricing", label: "Pricing" },
            user && { to: "/dashboard", label: "Dashboard" },
          ]
            .filter(Boolean)
            .map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                end={l.to === "/"}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded transition-colors ${
                    isActive ? "text-white bg-card" : "text-muted hover:text-white"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          {user ? (
            <div className="flex items-center gap-2 ml-3 pl-3 border-l border-border/60">
              <span className="text-xs text-muted hidden sm:flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" /> {user.email}
              </span>
              <button
                onClick={async () => { await logout(); nav("/"); }}
                className="text-muted hover:text-danger transition-colors p-2"
                title="Logout"
              >
                <SignOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2 ml-3">
              <Link to="/login" className="text-muted hover:text-white px-3 py-1.5 rounded text-sm">
                Login
              </Link>
              <Link
                to="/register"
                className="bg-accent text-black hover:bg-accent/80 transition-colors px-4 py-1.5 rounded font-bold text-sm"
              >
                Sign up
              </Link>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
