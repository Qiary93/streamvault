import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import axios from 'axios';
import { 
  House, 
  Compass, 
  User, 
  Broadcast, 
  CaretLeft,
  CaretRight,
  Play,
  UsersThree,
  CaretDown,
  CaretUp
} from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

const navItems = [
  { icon: House, label: 'Home', path: '/' },
  { icon: Compass, label: 'Browse', path: '/browse' },
  { icon: Play, label: 'VODs', path: '/vods' },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [recommended, setRecommended] = useState([]);
  const [following, setFollowing] = useState([]);
  const [totalFollowing, setTotalFollowing] = useState(0);
  const [followersLimit, setFollowersLimit] = useState(10);
  const location = useLocation();
  const { user } = useAuth();

  useEffect(() => {
    const fetchRecommended = async () => {
      try {
        const res = await axios.get(`${API}/api/recommended`, { withCredentials: true });
        setRecommended(res.data || []);
      } catch (e) {}
    };
    fetchRecommended();
  }, [user?.user_id]);

  useEffect(() => {
    if (!user) {
      setFollowing([]);
      return;
    }
    const fetchFollowing = async () => {
      try {
        const res = await axios.get(`${API}/api/my/following?limit=100`, { withCredentials: true });
        setFollowing(res.data.items || []);
        setTotalFollowing(res.data.total || 0);
      } catch (e) {}
    };
    fetchFollowing();
  }, [user?.user_id]);

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside 
        className={`fixed left-0 top-0 h-full bg-[#0F0F16] border-r border-white/5 z-50 transition-all duration-300 flex flex-col
          ${collapsed ? 'w-16' : 'w-64'} 
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-white/5 flex-shrink-0">
          {!collapsed && (
            <Link to="/" className="flex items-center gap-2" data-testid="sidebar-logo">
              <Broadcast weight="fill" className="w-8 h-8 text-[#00E5FF]" />
              <span className="font-bold text-xl font-['Outfit'] text-white">StreamVault</span>
            </Link>
          )}
          {collapsed && (
            <Broadcast weight="fill" className="w-8 h-8 text-[#00E5FF] mx-auto" />
          )}
          <button 
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:flex items-center justify-center w-6 h-6 rounded hover:bg-white/10 transition-colors"
            data-testid="sidebar-collapse-btn"
          >
            {collapsed ? <CaretRight className="w-4 h-4 text-[#A0A0AB]" /> : <CaretLeft className="w-4 h-4 text-[#A0A0AB]" />}
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden">
        {/* Navigation */}
        <nav className="p-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200
                  ${isActive 
                    ? 'bg-[#00E5FF]/10 text-[#00E5FF]' 
                    : 'text-[#A0A0AB] hover:bg-white/5 hover:text-white'}`}
                data-testid={`nav-${item.label.toLowerCase()}`}
              >
                <Icon weight={isActive ? 'fill' : 'regular'} className="w-5 h-5 flex-shrink-0" />
                {!collapsed && <span className="font-medium">{item.label}</span>}
              </Link>
            );
          })}

          {user && (
            <>
              <Link
                to="/dashboard"
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200
                  ${location.pathname === '/dashboard' 
                    ? 'bg-[#00E5FF]/10 text-[#00E5FF]' 
                    : 'text-[#A0A0AB] hover:bg-white/5 hover:text-white'}`}
                data-testid="nav-dashboard"
              >
                <Broadcast weight={location.pathname === '/dashboard' ? 'fill' : 'regular'} className="w-5 h-5 flex-shrink-0" />
                {!collapsed && <span className="font-medium">Dashboard</span>}
              </Link>
              <Link
                to={`/user/${user.username}`}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200 text-[#A0A0AB] hover:bg-white/5 hover:text-white`}
                data-testid="nav-profile"
              >
                <User weight="regular" className="w-5 h-5 flex-shrink-0" />
                {!collapsed && <span className="font-medium">Profile</span>}
              </Link>
            </>
          )}
        </nav>

        {/* Followers (users you follow) */}
        {!collapsed && user && following.length > 0 && (
          <div className="mt-4 px-4" data-testid="sidebar-followers">
            <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-3 flex items-center gap-2">
              <UsersThree className="w-3.5 h-3.5" /> Followers ({totalFollowing})
            </h3>
            <div className="space-y-1">
              {following.slice(0, followersLimit).map((f) => (
                <Link
                  key={f.user_id}
                  to={f.active_stream_id ? `/stream/${f.active_stream_id}` : `/user/${f.username}`}
                  className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[#A0A0AB] hover:bg-white/5 hover:text-white transition-all duration-200"
                  data-testid={`follow-${f.user_id}`}
                >
                  <Avatar className="w-6 h-6 flex-shrink-0">
                    <AvatarImage src={f.avatar_url} alt={f.display_name || f.username} />
                    <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-[10px]">
                      {(f.display_name || f.username)?.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{f.display_name || f.username}</p>
                    {f.is_live && f.game_name && (
                      <p className="text-[10px] text-[#A0A0AB] truncate">{f.game_name}</p>
                    )}
                  </div>
                  {f.is_live && (
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                      <span className="text-[10px] text-white font-medium tabular-nums">{(f.viewer_count || 0).toLocaleString()}</span>
                    </div>
                  )}
                </Link>
              ))}
              {totalFollowing > 10 && (
                <div className="pt-2 flex gap-2">
                  {followersLimit < totalFollowing && (
                    <button
                      onClick={() => setFollowersLimit(prev => Math.min(prev + 10, totalFollowing))}
                      className="flex-1 text-xs text-[#00E5FF] hover:text-[#00B3CC] py-1.5 flex items-center justify-center gap-1"
                      data-testid="followers-show-more"
                    >
                      <CaretDown className="w-3 h-3" /> Show more
                    </button>
                  )}
                  {followersLimit > 10 && (
                    <button
                      onClick={() => setFollowersLimit(10)}
                      className="flex-1 text-xs text-[#A0A0AB] hover:text-white py-1.5 flex items-center justify-center gap-1"
                      data-testid="followers-show-less"
                    >
                      <CaretUp className="w-3 h-3" /> Show less
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Recommended Streamers */}
        {!collapsed && recommended.length > 0 && (
          <div className="mt-4 px-4 pb-4" data-testid="sidebar-recommended">
            <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-3">Recommended · Live</h3>
            <div className="space-y-1">
              {recommended.slice(0, 10).map((s) => (
                <Link
                  key={s.user_id}
                  to={s.active_stream_id ? `/stream/${s.active_stream_id}` : `/user/${s.username}`}
                  className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[#A0A0AB] hover:bg-white/5 hover:text-white transition-all duration-200"
                  data-testid={`rec-side-${s.user_id}`}
                >
                  <Avatar className="w-6 h-6 flex-shrink-0">
                    <AvatarImage src={s.avatar_url} alt={s.display_name || s.username} />
                    <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-[10px]">
                      {(s.display_name || s.username)?.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{s.display_name || s.username}</p>
                    {s.game_name && <p className="text-[10px] text-[#A0A0AB] truncate">{s.game_name}</p>}
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                    <span className="text-[10px] text-white font-medium tabular-nums">{(s.viewer_count || 0).toLocaleString()}</span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
        </div>
      </aside>

      {/* Mobile menu button */}
      <button
        onClick={() => setMobileOpen(true)}
        className="fixed bottom-4 left-4 z-40 lg:hidden bg-[#00E5FF] text-black p-3 rounded-full shadow-lg"
        data-testid="mobile-menu-btn"
      >
        <Broadcast weight="fill" className="w-6 h-6" />
      </button>
    </>
  );
}
