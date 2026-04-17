import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import axios from 'axios';
import { 
  House, 
  Compass, 
  Heart, 
  User, 
  Broadcast, 
  GameController, 
  MusicNote, 
  ChatsCircle,
  Trophy,
  Palette,
  Barbell,
  Code,
  CaretLeft,
  CaretRight,
  Play
} from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

const navItems = [
  { icon: House, label: 'Home', path: '/' },
  { icon: Compass, label: 'Browse', path: '/browse' },
  { icon: Play, label: 'VODs', path: '/vods' },
];

const categories = [
  { icon: GameController, label: 'Gaming', id: 'cat_gaming' },
  { icon: ChatsCircle, label: 'Just Chatting', id: 'cat_justchatting' },
  { icon: MusicNote, label: 'Music', id: 'cat_music' },
  { icon: Trophy, label: 'Esports', id: 'cat_esports' },
  { icon: Palette, label: 'Creative', id: 'cat_creative' },
  { icon: Barbell, label: 'Sports', id: 'cat_sports' },
  { icon: Code, label: 'Technology', id: 'cat_tech' },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [recommended, setRecommended] = useState([]);
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
        className={`fixed left-0 top-0 h-full bg-[#0F0F16] border-r border-white/5 z-50 transition-all duration-300
          ${collapsed ? 'w-16' : 'w-64'} 
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
        data-testid="sidebar"
      >
        {/* Logo */}
        <div className="h-16 flex items-center justify-between px-4 border-b border-white/5">
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

        {/* Categories */}
        {!collapsed && (
          <div className="mt-4 px-4">
            <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-3">Categories</h3>
            <div className="space-y-1">
              {categories.map((cat) => {
                const Icon = cat.icon;
                const isActive = location.pathname === `/category/${cat.id}`;
                return (
                  <Link
                    key={cat.id}
                    to={`/category/${cat.id}`}
                    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200
                      ${isActive 
                        ? 'bg-[#00E5FF]/10 text-[#00E5FF]' 
                        : 'text-[#A0A0AB] hover:bg-white/5 hover:text-white'}`}
                    data-testid={`cat-${cat.id}`}
                  >
                    <Icon weight={isActive ? 'fill' : 'regular'} className="w-4 h-4" />
                    <span className="text-sm">{cat.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        {/* Recommended Streamers */}
        {!collapsed && recommended.length > 0 && (
          <div className="mt-4 px-4 pb-4" data-testid="sidebar-recommended">
            <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-[#00E5FF] mb-3">Recommended</h3>
            <div className="space-y-1">
              {recommended.slice(0, 10).map((s) => (
                <Link
                  key={s.user_id}
                  to={s.active_stream_id ? `/stream/${s.active_stream_id}` : `/user/${s.username}`}
                  className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg text-[#A0A0AB] hover:bg-white/5 hover:text-white transition-all duration-200"
                  data-testid={`rec-${s.user_id}`}
                >
                  <Avatar className={`w-6 h-6 flex-shrink-0 ${s.is_streaming ? 'avatar-live' : ''}`}>
                    <AvatarImage src={s.avatar_url} alt={s.display_name || s.username} />
                    <AvatarFallback className="bg-[#292938] text-[#00E5FF] text-[10px]">
                      {(s.display_name || s.username)?.charAt(0).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                  <span className="text-sm truncate">{s.display_name || s.username}</span>
                  {s.is_streaming && (
                    <span className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0 ml-auto" />
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}
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
