import { useEffect } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

/**
 * BrandingTitle — runs once at app boot. Fetches /api/config/branding and
 * updates document.title and the meta description so the browser tab shows
 * the configured site name (set in Admin → Website Administration → Branding).
 *
 * This replaces whatever was hardcoded in public/index.html the moment the
 * React app mounts. There is no UI rendered.
 */
export default function BrandingTitle() {
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/api/config/branding`)
      .then(res => {
        if (cancelled) return;
        const name = res.data?.site_name || 'StreamVault';
        const tagline = res.data?.tagline || '';
        const description = res.data?.description || `${name} — live streaming platform`;
        document.title = tagline ? `${name} — ${tagline}` : name;
        const m = document.querySelector('meta[name="description"]');
        if (m) m.setAttribute('content', description);
      })
      .catch(() => {/* keep fallback title */});
    return () => { cancelled = true; };
  }, []);
  return null;
}
