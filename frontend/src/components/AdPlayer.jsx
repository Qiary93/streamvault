import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

// Generate/persist a viewer key for impression deduplication
const getViewerKey = () => {
  try {
    let v = localStorage.getItem('sv_viewer_id');
    if (!v) {
      v = `vk_${Math.random().toString(36).slice(2, 12)}${Date.now().toString(36)}`;
      localStorage.setItem('sv_viewer_id', v);
    }
    return v;
  } catch {
    return `vk_${Math.random().toString(36).slice(2, 12)}`;
  }
};

/**
 * Pre-roll ad overlay. Renders full-screen over the video container until:
 *  - no ad configured → calls onFinish() immediately
 *  - countdown expires OR user clicks Skip (after 5s by default)
 */
export default function AdPlayer({ streamId, placement = 'live_pre_roll', onFinish }) {
  const [ad, setAd] = useState(null);
  const [loading, setLoading] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const [impressionSent, setImpressionSent] = useState(false);
  const adRef = useRef(null);

  useEffect(() => {
    let active = true;
    axios.get(`${API}/api/ads/active?placement=${placement}`)
      .then(res => {
        if (!active) return;
        if (res.data?.enabled && res.data?.ad) {
          setAd(res.data.ad);
        } else {
          onFinish && onFinish();
        }
      })
      .catch(() => onFinish && onFinish())
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [placement]);

  // Countdown + impression credit
  useEffect(() => {
    if (!ad) return;
    const duration = ad.duration_sec || 15;
    const interval = setInterval(() => {
      setElapsed(e => {
        const next = e + 1;
        if (next >= duration) {
          clearInterval(interval);
          finish();
        }
        return next;
      });
    }, 1000);
    // Record impression on show (after 1s to avoid false impressions from fast skippers)
    const impTimer = setTimeout(() => {
      if (impressionSent) return;
      setImpressionSent(true);
      axios.post(`${API}/api/ads/impression`, {
        stream_id: streamId,
        slot_id: ad.slot_id,
        placement,
        viewer_id: getViewerKey(),
      }, { withCredentials: true }).catch(() => {});
    }, 1500);
    return () => {
      clearInterval(interval);
      clearTimeout(impTimer);
    };
  }, [ad]);

  // Inject HTML ad code safely via innerHTML so ad tags execute scripts
  useEffect(() => {
    if (!ad || ad.ad_type !== 'html' || !adRef.current) return;
    adRef.current.innerHTML = ad.ad_code || '';
    // Re-execute scripts (innerHTML does not run <script>)
    const scripts = adRef.current.querySelectorAll('script');
    scripts.forEach(old => {
      const s = document.createElement('script');
      [...old.attributes].forEach(a => s.setAttribute(a.name, a.value));
      s.text = old.textContent || '';
      old.parentNode.replaceChild(s, old);
    });
  }, [ad]);

  const finish = () => {
    onFinish && onFinish();
  };

  if (loading || !ad) return null;

  const duration = ad.duration_sec || 15;
  const remaining = Math.max(0, duration - elapsed);
  const canSkip = elapsed >= Math.min(5, duration);

  return (
    <div className="absolute inset-0 z-30 bg-black flex flex-col" data-testid="ad-player">
      <div className="flex-1 relative overflow-hidden">
        {ad.ad_type === 'video' && ad.video_url && (
          <video
            src={ad.video_url}
            autoPlay
            muted
            playsInline
            onEnded={finish}
            className="w-full h-full object-contain"
            data-testid="ad-video"
          />
        )}
        {ad.ad_type === 'image' && ad.image_url && (
          <a href={ad.click_url || '#'} target="_blank" rel="noopener noreferrer" onClick={() => {}}>
            <img src={ad.image_url} alt={ad.name} className="w-full h-full object-contain" data-testid="ad-image" />
          </a>
        )}
        {ad.ad_type === 'html' && (
          <div ref={adRef} className="w-full h-full flex items-center justify-center" data-testid="ad-html" />
        )}
      </div>
      <div className="flex items-center justify-between px-4 py-2 bg-black/80 border-t border-white/10">
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded text-[10px] font-bold uppercase">Ad</span>
          <span className="text-white/70">{ad.name || 'Sponsor'}</span>
          <span className="text-[#A0A0AB]">· {remaining}s</span>
        </div>
        <button
          onClick={finish}
          disabled={!canSkip}
          data-testid="ad-skip-btn"
          className={`text-xs px-3 py-1.5 rounded font-medium transition-colors ${canSkip ? 'bg-white text-black hover:bg-white/90' : 'bg-white/10 text-white/50 cursor-not-allowed'}`}
        >
          {canSkip ? 'Skip Ad ›' : `Skip in ${Math.min(5, duration) - elapsed}s`}
        </button>
      </div>
    </div>
  );
}
