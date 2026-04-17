import React, { useState, useEffect } from 'react';
import { CurrencyDollar, ArrowUp, Clock, Check, X, Warning, Bank } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from './ui/dialog';
import { toast } from 'sonner';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export default function RevenueSection() {
  const [revenue, setRevenue] = useState(null);
  const [withdrawals, setWithdrawals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [withdrawOpen, setWithdrawOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    amount: '',
    iban: '',
    paypal_email: ''
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [revRes, wdRes] = await Promise.all([
        axios.get(`${API}/api/my/revenue`, { withCredentials: true }),
        axios.get(`${API}/api/my/withdrawals`, { withCredentials: true })
      ]);
      setRevenue(revRes.data);
      setWithdrawals(wdRes.data);
    } catch (e) {
      console.error('Error fetching revenue:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleWithdraw = async (e) => {
    e.preventDefault();
    if (!form.first_name || !form.last_name || !form.iban) {
      toast.error('Please fill in all required fields');
      return;
    }
    const amount = parseFloat(form.amount);
    if (!amount || amount < 50) {
      toast.error('Minimum withdrawal amount is $50');
      return;
    }
    if (amount > (revenue?.available_balance || 0)) {
      toast.error('Amount exceeds available balance');
      return;
    }

    setSubmitting(true);
    try {
      await axios.post(`${API}/api/my/withdraw`, {
        first_name: form.first_name,
        last_name: form.last_name,
        amount,
        iban: form.iban,
        paypal_email: form.paypal_email
      }, { withCredentials: true });
      toast.success('Withdrawal request submitted!');
      setWithdrawOpen(false);
      setForm({ first_name: '', last_name: '', amount: '', iban: '', paypal_email: '' });
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to submit withdrawal');
    } finally {
      setSubmitting(false);
    }
  };

  const statusColors = {
    pending: 'text-yellow-400 bg-yellow-500/10',
    completed: 'text-green-400 bg-green-500/10',
    rejected: 'text-red-400 bg-red-500/10'
  };

  const statusIcons = {
    pending: <Clock className="w-3.5 h-3.5" />,
    completed: <Check className="w-3.5 h-3.5" />,
    rejected: <X className="w-3.5 h-3.5" />
  };

  if (loading) return null;

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="revenue-section">
      <div className="flex items-center gap-3 mb-6">
        <CurrencyDollar className="w-6 h-6 text-green-400" />
        <h2 className="text-lg font-semibold text-white">Revenue</h2>
      </div>

      {/* Revenue Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <div className="p-4 bg-[#1A1A24] rounded-lg">
          <p className="text-xs text-[#A0A0AB] mb-1">Total Earned</p>
          <p className="text-xl font-bold text-white">${revenue?.total_earned?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="p-4 bg-[#1A1A24] rounded-lg">
          <p className="text-xs text-[#A0A0AB] mb-1">From Donations</p>
          <p className="text-xl font-bold text-purple-400">${revenue?.total_donations?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="p-4 bg-[#1A1A24] rounded-lg">
          <p className="text-xs text-[#A0A0AB] mb-1">From Subscriptions</p>
          <p className="text-xl font-bold text-yellow-400">${revenue?.total_subscriptions?.toFixed(2) || '0.00'}</p>
        </div>
        <div className="p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
          <p className="text-xs text-green-400 mb-1">Available to Withdraw</p>
          <p className="text-xl font-bold text-green-400">${revenue?.available_balance?.toFixed(2) || '0.00'}</p>
        </div>
      </div>

      {/* Withdraw Button */}
      <div className="flex items-center gap-4 mb-6">
        <Dialog open={withdrawOpen} onOpenChange={setWithdrawOpen}>
          <DialogTrigger asChild>
            <Button
              disabled={(revenue?.available_balance || 0) < 50}
              className="bg-green-500 text-white font-bold hover:bg-green-600 disabled:opacity-50 gap-2"
              data-testid="withdraw-btn"
            >
              <ArrowUp className="w-4 h-4" /> Withdraw Funds
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#0F0F16] border-white/10 max-w-md">
            <DialogHeader>
              <DialogTitle className="text-white flex items-center gap-2">
                <Bank className="w-5 h-5 text-green-400" /> Withdraw Funds
              </DialogTitle>
            </DialogHeader>
            <form onSubmit={handleWithdraw} className="space-y-4 pt-4">
              <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg text-center">
                <p className="text-xs text-green-400">Available Balance</p>
                <p className="text-2xl font-bold text-green-400">${revenue?.available_balance?.toFixed(2)}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1">First Name *</label>
                  <Input
                    value={form.first_name}
                    onChange={(e) => setForm(prev => ({ ...prev, first_name: e.target.value }))}
                    className="bg-[#1A1A24] border-white/10 text-white"
                    data-testid="wd-first-name"
                  />
                </div>
                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1">Last Name *</label>
                  <Input
                    value={form.last_name}
                    onChange={(e) => setForm(prev => ({ ...prev, last_name: e.target.value }))}
                    className="bg-[#1A1A24] border-white/10 text-white"
                    data-testid="wd-last-name"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-[#A0A0AB] block mb-1">Amount * (min $50)</label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#A0A0AB] font-bold">$</span>
                  <Input
                    type="number"
                    min="50"
                    max={revenue?.available_balance || 0}
                    step="0.01"
                    value={form.amount}
                    onChange={(e) => setForm(prev => ({ ...prev, amount: e.target.value }))}
                    className="pl-8 bg-[#1A1A24] border-white/10 text-white"
                    data-testid="wd-amount"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-[#A0A0AB] block mb-1">IBAN *</label>
                <Input
                  value={form.iban}
                  onChange={(e) => setForm(prev => ({ ...prev, iban: e.target.value.toUpperCase() }))}
                  placeholder="e.g. DE89370400440532013000"
                  className="bg-[#1A1A24] border-white/10 text-white font-mono"
                  data-testid="wd-iban"
                />
              </div>

              <div>
                <label className="text-sm text-[#A0A0AB] block mb-1">PayPal Email <span className="text-[#A0A0AB]/50">(optional)</span></label>
                <Input
                  type="email"
                  value={form.paypal_email}
                  onChange={(e) => setForm(prev => ({ ...prev, paypal_email: e.target.value }))}
                  placeholder="your@paypal.com"
                  className="bg-[#1A1A24] border-white/10 text-white"
                  data-testid="wd-paypal"
                />
              </div>

              <div className="p-3 bg-[#1A1A24] rounded-lg flex items-start gap-2">
                <Warning className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                <p className="text-xs text-[#A0A0AB]">
                  Withdrawals are processed by the admin. You will be notified once your request is approved and funds are sent.
                </p>
              </div>

              <Button
                type="submit"
                disabled={submitting}
                className="w-full bg-green-500 text-white font-bold hover:bg-green-600 disabled:opacity-50"
                data-testid="wd-submit-btn"
              >
                {submitting ? 'Submitting...' : `Request Withdrawal`}
              </Button>
            </form>
          </DialogContent>
        </Dialog>

        {(revenue?.available_balance || 0) < 50 && (
          <p className="text-xs text-[#A0A0AB]">Minimum $50 required to withdraw</p>
        )}

        {revenue?.total_pending > 0 && (
          <span className="text-xs text-yellow-400 bg-yellow-500/10 px-3 py-1 rounded-full flex items-center gap-1">
            <Clock className="w-3 h-3" /> ${revenue.total_pending.toFixed(2)} pending
          </span>
        )}
      </div>

      {/* Withdrawal History */}
      {withdrawals.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-white mb-3">Withdrawal History</h3>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {withdrawals.map((wd) => (
              <div key={wd.withdrawal_id} className="flex items-center justify-between p-3 bg-[#1A1A24] rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[wd.status]}`}>
                    {statusIcons[wd.status]} {wd.status}
                  </span>
                  <div>
                    <p className="text-sm text-white font-medium">${wd.amount?.toFixed(2)}</p>
                    <p className="text-xs text-[#A0A0AB]">{wd.first_name} {wd.last_name} - {wd.iban?.substring(0, 8)}...</p>
                  </div>
                </div>
                <p className="text-xs text-[#A0A0AB]">{new Date(wd.created_at).toLocaleDateString()}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
