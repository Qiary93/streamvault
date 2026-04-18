import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import { ChartLineUp, CalendarBlank } from '@phosphor-icons/react';

const API = process.env.REACT_APP_BACKEND_URL;

const PERIODS = [
  { value: 'daily', label: 'Daily (30d)' },
  { value: 'weekly', label: 'Weekly (12w)' },
  { value: 'monthly', label: 'Monthly (12m)' },
];

export default function RevenueAnalyticsChart() {
  const [period, setPeriod] = useState('daily');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('line');

  useEffect(() => {
    let active = true;
    setLoading(true);
    axios.get(`${API}/api/my/revenue/analytics?period=${period}`, { withCredentials: true })
      .then(res => { if (active) setData(res.data.series || []); })
      .catch(() => { if (active) setData([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [period]);

  const total = data.reduce((a, b) => a + (b.total || 0), 0);

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="revenue-analytics">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <ChartLineUp className="w-6 h-6 text-[#00E5FF]" />
          <div>
            <h2 className="text-lg font-semibold text-white">Revenue Analytics</h2>
            <p className="text-sm text-[#A0A0AB]">Trend of donations, subs and ads earnings</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center bg-[#1A1A24] rounded-lg p-1">
            {PERIODS.map(p => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                data-testid={`period-${p.value}`}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${period === p.value ? 'bg-[#00E5FF] text-black' : 'text-[#A0A0AB] hover:text-white'}`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="flex items-center bg-[#1A1A24] rounded-lg p-1">
            <button onClick={() => setView('line')} data-testid="chart-view-line" className={`px-3 py-1.5 text-xs font-medium rounded-md ${view === 'line' ? 'bg-white/10 text-white' : 'text-[#A0A0AB]'}`}>Line</button>
            <button onClick={() => setView('bar')} data-testid="chart-view-bar" className={`px-3 py-1.5 text-xs font-medium rounded-md ${view === 'bar' ? 'bg-white/10 text-white' : 'text-[#A0A0AB]'}`}>Bar</button>
          </div>
        </div>
      </div>

      <div className="mb-4 p-3 bg-[#1A1A24] rounded-lg flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-[#A0A0AB]">
          <CalendarBlank className="w-4 h-4" /> Showing {data.length} data point{data.length !== 1 ? 's' : ''}
        </div>
        <div className="text-sm">
          <span className="text-[#A0A0AB]">Total in range:</span>{' '}
          <span className="text-green-400 font-bold">${total.toFixed(2)}</span>
        </div>
      </div>

      {loading ? (
        <div className="h-72 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-[#00E5FF] border-t-transparent rounded-full animate-spin" />
        </div>
      ) : data.length === 0 ? (
        <div className="h-72 flex flex-col items-center justify-center text-[#A0A0AB]">
          <ChartLineUp className="w-12 h-12 mb-3 text-[#292938]" />
          <p>No revenue data yet for this period.</p>
          <p className="text-xs mt-1">Donations, subscriptions and ad impressions will appear here.</p>
        </div>
      ) : (
        <div className="h-72" data-testid="chart-container">
          <ResponsiveContainer width="100%" height="100%">
            {view === 'line' ? (
              <LineChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#292938" />
                <XAxis dataKey="period" stroke="#A0A0AB" fontSize={11} />
                <YAxis stroke="#A0A0AB" fontSize={11} />
                <Tooltip contentStyle={{ background: '#0F0F16', border: '1px solid #292938', borderRadius: '8px' }} labelStyle={{ color: '#fff' }} />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Line type="monotone" dataKey="donations" stroke="#C084FC" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="subscriptions" stroke="#FACC15" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="ads" stroke="#00E5FF" strokeWidth={2} dot={{ r: 3 }} />
                <Line type="monotone" dataKey="total" stroke="#22C55E" strokeWidth={3} dot={{ r: 3 }} />
              </LineChart>
            ) : (
              <BarChart data={data} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#292938" />
                <XAxis dataKey="period" stroke="#A0A0AB" fontSize={11} />
                <YAxis stroke="#A0A0AB" fontSize={11} />
                <Tooltip contentStyle={{ background: '#0F0F16', border: '1px solid #292938', borderRadius: '8px' }} labelStyle={{ color: '#fff' }} />
                <Legend wrapperStyle={{ fontSize: '12px' }} />
                <Bar dataKey="donations" stackId="a" fill="#C084FC" />
                <Bar dataKey="subscriptions" stackId="a" fill="#FACC15" />
                <Bar dataKey="ads" stackId="a" fill="#00E5FF" />
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
