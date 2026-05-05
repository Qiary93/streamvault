import React from "react";

export default function Footer() {
  return (
    <footer className="border-t border-border/60 mt-24">
      <div className="max-w-6xl mx-auto px-6 py-8 text-xs text-muted flex flex-wrap items-center justify-between gap-2">
        <span>
          © {new Date().getFullYear()} DramaroSub. Built by{" "}
          <span className="text-white font-semibold">Qiary93</span>.
        </span>
        <span>
          Questions? <a href="mailto:stancu.daniel1993@gmail.com" className="text-accent hover:underline">stancu.daniel1993@gmail.com</a>
        </span>
      </div>
    </footer>
  );
}
