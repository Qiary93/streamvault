import React, { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle, Spinner, Copy, Warning } from "@phosphor-icons/react";
import { checkout } from "../lib/api";

const MAX_ATTEMPTS = 15;
const POLL_MS = 2000;

export default function CheckoutSuccessPage() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [state, setState] = useState({ status: "polling", attempts: 0, license_key: null, message: "" });
  const stop = useRef(false);

  useEffect(() => {
    stop.current = false;
    if (!sessionId) {
      setState({ status: "error", message: "Missing session_id in URL" });
      return;
    }

    let attempt = 0;
    const poll = async () => {
      if (stop.current) return;
      attempt += 1;
      try {
        const { data } = await checkout.status(sessionId);
        if (data.status === "paid" && data.license_key) {
          setState({ status: "paid", license_key: data.license_key, attempts: attempt });
          return;
        }
        if (data.status === "failed" || data.status === "expired") {
          setState({ status: "failed", message: `Payment ${data.status}`, attempts: attempt });
          return;
        }
        if (attempt >= MAX_ATTEMPTS) {
          setState({
            status: "timeout",
            message: "Still waiting for Stripe to confirm. We'll email you when it's done — or refresh in a minute.",
            attempts: attempt,
          });
          return;
        }
        setState((s) => ({ ...s, attempts: attempt }));
        setTimeout(poll, POLL_MS);
      } catch (e) {
        setState({ status: "error", message: e.response?.data?.detail || "Could not check status", attempts: attempt });
      }
    };
    poll();
    return () => { stop.current = true; };
  }, [sessionId]);

  const copy = () => {
    navigator.clipboard.writeText(state.license_key);
    toast.success("Copied");
  };

  return (
    <div className="max-w-2xl mx-auto px-6 py-20 text-center">
      {state.status === "polling" && (
        <>
          <Spinner className="w-12 h-12 text-accent mx-auto animate-spin mb-5" />
          <h1 className="text-2xl font-black">Confirming your payment…</h1>
          <p className="text-muted mt-3">This usually takes 5–10 seconds. (Attempt {state.attempts}/{MAX_ATTEMPTS})</p>
        </>
      )}
      {state.status === "paid" && (
        <>
          <CheckCircle weight="fill" className="w-14 h-14 text-[#4ADE80] mx-auto mb-5" />
          <h1 className="text-3xl font-black">Payment successful</h1>
          <p className="text-muted mt-3">Your license is ready. Copy this key and add it to your StreamVault `.env`:</p>
          <div className="bg-surface border border-accent/40 rounded-xl p-5 mt-6 flex items-center justify-between gap-3">
            <code className="font-mono text-lg break-all text-left">{state.license_key}</code>
            <button onClick={copy} className="bg-accent text-black hover:bg-accent/80 p-2.5 rounded-lg shrink-0" title="Copy">
              <Copy className="w-4 h-4" />
            </button>
          </div>
          <Link to="/dashboard" className="inline-block mt-8 bg-accent text-black hover:bg-accent/80 px-6 py-3 rounded-lg font-bold">
            Open dashboard →
          </Link>
        </>
      )}
      {(state.status === "timeout" || state.status === "error" || state.status === "failed") && (
        <>
          <Warning weight="fill" className="w-12 h-12 text-accent2 mx-auto mb-5" />
          <h1 className="text-2xl font-black">{state.status === "failed" ? "Payment didn't complete" : "Hmm…"}</h1>
          <p className="text-muted mt-3">{state.message}</p>
          <Link to="/dashboard" className="inline-block mt-8 border border-border hover:border-accent px-6 py-3 rounded-lg font-semibold">
            Go to dashboard
          </Link>
        </>
      )}
    </div>
  );
}
