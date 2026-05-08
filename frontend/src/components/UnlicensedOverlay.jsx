import React, { useEffect, useState } from "react";
import { ShieldWarning, Key } from "@phosphor-icons/react";
import axios from "axios";
import { Button } from "./ui/button";

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * Listens for `streamvault:unlicensed` window events (dispatched by api/axios
 * interceptor when any API call returns 503 with code: "UNLICENSED") and
 * renders a fullscreen lockout. Admins can paste a new license key here
 * without going through the admin panel.
 */
export default function UnlicensedOverlay() {
  const [shown, setShown] = useState(false);
  const [reason, setReason] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    const onEvt = (e) => {
      setShown(true);
      setReason(e.detail?.detail || "License invalid.");
    };
    window.addEventListener("streamvault:unlicensed", onEvt);
    return () => window.removeEventListener("streamvault:unlicensed", onEvt);
  }, []);

  const revalidate = async () => {
    setBusy(true);
    setMsg("");
    try {
      const res = await axios.post(`${API}/api/admin/license/revalidate`, {}, { withCredentials: true });
      if (res.data.valid) {
        setMsg("✓ License accepted — reloading…");
        setTimeout(() => window.location.reload(), 1500);
      } else {
        setMsg(`Still invalid: ${res.data.message || res.data.status}`);
      }
    } catch (e) {
      setMsg(e.response?.data?.detail || "Could not contact backend.");
    } finally {
      setBusy(false);
    }
  };

  if (!shown) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] bg-[#0A0A0F]/95 backdrop-blur-md flex items-center justify-center p-6"
      data-testid="unlicensed-overlay"
    >
      <div className="max-w-lg w-full bg-[#0F0F16] border border-red-500/30 rounded-2xl p-8 text-center">
        <ShieldWarning weight="fill" className="w-14 h-14 text-red-400 mx-auto mb-4" />
        <h1 className="text-2xl font-black text-white mb-2">License required</h1>
        <p className="text-[#A0A0AB] text-sm mb-6 leading-relaxed">
          This StreamVault install requires a valid license to operate.
          {reason && (
            <>
              <br />
              <span className="text-red-400 text-xs mt-2 block font-mono">{reason}</span>
            </>
          )}
        </p>

        <div className="bg-[#1A1A24] rounded-lg p-4 mb-4 text-left">
          <p className="text-xs text-[#A0A0AB] mb-2">If you have a license key, log in as admin and paste it in:</p>
          <code className="text-xs text-[#00E5FF] block bg-black/40 p-2 rounded">
            /app/backend/.env → STREAMVAULT_LICENSE_KEY=DSB-XXXXX-XXXXX-XXXXX-XXXXX
          </code>
          <p className="text-xs text-[#A0A0AB] mt-2">
            Then restart the backend. Or click below to re-check after editing.
          </p>
        </div>

        <Button
          onClick={revalidate}
          disabled={busy}
          className="w-full bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold mb-3"
          data-testid="unlicensed-recheck"
        >
          <Key className="w-4 h-4 mr-2" />
          {busy ? "Re-checking…" : "I've added my license — re-check"}
        </Button>
        {msg && <p className="text-sm text-[#A0A0AB]">{msg}</p>}

        <a
          href="https://license.stream-vault.eu/pricing"
          target="_blank"
          rel="noopener noreferrer"
          className="block mt-4 text-sm text-[#00E5FF] hover:underline"
        >
          Don't have a license? Get one →
        </a>
      </div>
    </div>
  );
}
