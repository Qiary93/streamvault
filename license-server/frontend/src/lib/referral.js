// Captures ?ref=CODE on first visit, persists for 30 days.
const KEY = "sv_ref";
const DAYS = 30;

export function captureReferralFromUrl() {
  try {
    const url = new URL(window.location.href);
    const ref = (url.searchParams.get("ref") || "").trim();
    if (ref) {
      const expires = new Date(Date.now() + DAYS * 86400 * 1000);
      document.cookie = `${KEY}=${encodeURIComponent(ref)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
      // Strip the param so the URL stays clean
      url.searchParams.delete("ref");
      window.history.replaceState({}, "", url.toString());
    }
  } catch {
    /* ignore */
  }
}

export function getReferralCode() {
  const m = document.cookie.match(new RegExp(`(?:^|; )${KEY}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : "";
}
