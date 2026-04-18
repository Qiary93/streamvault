import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Bank, Check, Warning, LockKey, Info } from '@phosphor-icons/react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

const API = process.env.REACT_APP_BACKEND_URL;

const COUNTRIES = [
  { code: 'US', name: 'United States', currency: 'usd', routing: true },
  { code: 'CA', name: 'Canada', currency: 'cad', routing: true },
  { code: 'GB', name: 'United Kingdom', currency: 'gbp', routing: true },
  { code: 'DE', name: 'Germany', currency: 'eur', routing: false },
  { code: 'FR', name: 'France', currency: 'eur', routing: false },
  { code: 'IT', name: 'Italy', currency: 'eur', routing: false },
  { code: 'ES', name: 'Spain', currency: 'eur', routing: false },
  { code: 'NL', name: 'Netherlands', currency: 'eur', routing: false },
  { code: 'AU', name: 'Australia', currency: 'aud', routing: true },
];

export default function StripeConnectSection() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    first_name: '', last_name: '', dob: '',
    country: 'US', currency: 'usd',
    address_line1: '', city: '', state: '', postal_code: '', phone: '',
    routing_number: '', account_number: '', holder_name: '',
    tos_accepted: false,
  });

  const selectedCountry = COUNTRIES.find(c => c.code === form.country) || COUNTRIES[0];

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/api/my/stripe-connect/status`, { withCredentials: true });
      setStatus(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.tos_accepted) {
      toast.error('Please accept the Stripe Services Agreement');
      return;
    }
    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/api/my/stripe-connect/create`, {
        ...form,
        currency: selectedCountry.currency,
      }, { withCredentials: true });
      toast.success(res.data.message || 'Stripe Connect account saved');
      setShowForm(false);
      fetchStatus();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save Stripe Connect account');
    } finally {
      setSubmitting(false);
    }
  };

  const onDisconnect = async () => {
    if (!window.confirm('Disconnect your Stripe payout account? Automated payouts will stop until you reconnect.')) return;
    try {
      await axios.delete(`${API}/api/my/stripe-connect`, { withCredentials: true });
      toast.success('Disconnected');
      fetchStatus();
    } catch {
      toast.error('Failed to disconnect');
    }
  };

  if (loading) return null;

  const connected = status?.connected;
  const verified = status?.verification_status === 'verified';
  const currentlyDue = status?.currently_due || [];

  return (
    <div className="bg-[#0F0F16] border border-white/5 rounded-xl p-6" data-testid="stripe-connect-section">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <div className="flex items-center gap-3">
          <Bank className="w-6 h-6 text-green-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Automated Payouts (Stripe Connect)</h2>
            <p className="text-sm text-[#A0A0AB]">Receive earnings directly to your bank account when automated payouts are enabled by admin.</p>
          </div>
        </div>
        {connected && (
          <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold ${verified ? 'text-green-400 bg-green-500/10' : 'text-yellow-400 bg-yellow-500/10'}`}>
            {verified ? <Check className="w-3 h-3" /> : <Warning className="w-3 h-3" />}
            {status?.verification_status}
          </span>
        )}
      </div>

      {connected && !showForm && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="p-3 bg-[#1A1A24] rounded-lg">
              <p className="text-xs text-[#A0A0AB]">Account holder</p>
              <p className="text-sm text-white font-medium">{status.holder_name || '—'}</p>
            </div>
            <div className="p-3 bg-[#1A1A24] rounded-lg">
              <p className="text-xs text-[#A0A0AB]">Bank ending</p>
              <p className="text-sm text-white font-mono">•••• {status.bank_last4 || '----'}</p>
            </div>
            <div className="p-3 bg-[#1A1A24] rounded-lg">
              <p className="text-xs text-[#A0A0AB]">Country</p>
              <p className="text-sm text-white">{status.country}</p>
            </div>
          </div>

          {currentlyDue.length > 0 && (
            <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-start gap-2">
              <Warning className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-yellow-200">
                <strong>Action required:</strong> {currentlyDue.join(', ')}
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <Button onClick={() => setShowForm(true)} className="bg-[#00E5FF] text-black hover:bg-[#00B3CC] font-bold" data-testid="connect-update-btn">Update details</Button>
            <Button onClick={onDisconnect} variant="ghost" className="text-red-400 hover:bg-red-500/10" data-testid="connect-disconnect-btn">Disconnect</Button>
          </div>
        </div>
      )}

      {(!connected || showForm) && (
        <form onSubmit={onSubmit} className="space-y-4" data-testid="connect-form">
          <div className="p-3 bg-[#1A1A24] rounded-lg flex items-start gap-2">
            <LockKey className="w-4 h-4 text-[#00E5FF] flex-shrink-0 mt-0.5" />
            <p className="text-xs text-[#A0A0AB]">All data is sent directly to Stripe. We store only the last 4 digits of your bank account number.</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1">First name *</label>
              <Input value={form.first_name} onChange={e => setForm(p => ({ ...p, first_name: e.target.value }))} className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-first-name" />
            </div>
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1">Last name *</label>
              <Input value={form.last_name} onChange={e => setForm(p => ({ ...p, last_name: e.target.value }))} className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-last-name" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1">Date of birth * (YYYY-MM-DD)</label>
              <Input type="date" value={form.dob} onChange={e => setForm(p => ({ ...p, dob: e.target.value }))} className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-dob" />
            </div>
            <div>
              <label className="text-sm text-[#A0A0AB] block mb-1">Phone</label>
              <Input value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} placeholder="+1 555..." className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-phone" />
            </div>
          </div>

          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1">Country *</label>
            <Select value={form.country} onValueChange={(v) => setForm(p => ({ ...p, country: v }))}>
              <SelectTrigger className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-country"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-[#0F0F16] border-white/10">
                {COUNTRIES.map(c => <SelectItem key={c.code} value={c.code} className="text-white">{c.name} ({c.currency.toUpperCase()})</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label className="text-sm text-[#A0A0AB] block mb-1">Address *</label>
            <Input value={form.address_line1} onChange={e => setForm(p => ({ ...p, address_line1: e.target.value }))} placeholder="Street address" className="bg-[#1A1A24] border-white/10 text-white mb-2" data-testid="connect-address" />
            <div className="grid grid-cols-3 gap-2">
              <Input value={form.city} onChange={e => setForm(p => ({ ...p, city: e.target.value }))} placeholder="City" className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-city" />
              <Input value={form.state} onChange={e => setForm(p => ({ ...p, state: e.target.value }))} placeholder="State / Region" className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-state" />
              <Input value={form.postal_code} onChange={e => setForm(p => ({ ...p, postal_code: e.target.value }))} placeholder="Postal code" className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-postal" />
            </div>
          </div>

          <div className="pt-2 border-t border-white/5">
            <h4 className="text-sm font-semibold text-white mb-2">Bank account</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm text-[#A0A0AB] block mb-1">Account holder name</label>
                <Input value={form.holder_name} onChange={e => setForm(p => ({ ...p, holder_name: e.target.value }))} placeholder={`${form.first_name} ${form.last_name}`.trim() || 'Full name'} className="bg-[#1A1A24] border-white/10 text-white" data-testid="connect-holder" />
              </div>
              {selectedCountry.routing && (
                <div>
                  <label className="text-sm text-[#A0A0AB] block mb-1">Routing / Transit number *</label>
                  <Input value={form.routing_number} onChange={e => setForm(p => ({ ...p, routing_number: e.target.value }))} placeholder="9 digits" className="bg-[#1A1A24] border-white/10 text-white font-mono" data-testid="connect-routing" />
                </div>
              )}
            </div>
            <div className="mt-2">
              <label className="text-sm text-[#A0A0AB] block mb-1">{selectedCountry.routing ? 'Account number *' : 'IBAN *'}</label>
              <Input value={form.account_number} onChange={e => setForm(p => ({ ...p, account_number: e.target.value.trim() }))} placeholder={selectedCountry.routing ? 'Bank account number' : 'DE89 3704 0044 0532 0130 00'} className="bg-[#1A1A24] border-white/10 text-white font-mono" data-testid="connect-account-number" />
            </div>
          </div>

          <label className="flex items-start gap-2 p-3 bg-[#1A1A24] rounded-lg cursor-pointer">
            <input type="checkbox" checked={form.tos_accepted} onChange={e => setForm(p => ({ ...p, tos_accepted: e.target.checked }))} className="mt-0.5" data-testid="connect-tos" />
            <span className="text-xs text-[#A0A0AB]">I accept the <a href="https://stripe.com/connect-account/legal" target="_blank" rel="noreferrer" className="text-[#00E5FF] hover:underline">Stripe Services Agreement</a> and authorize StreamVault to send my information to Stripe for identity verification and bank account setup.</span>
          </label>

          <div className="flex gap-2">
            <Button type="submit" disabled={submitting} className="bg-green-500 text-white hover:bg-green-600 font-bold" data-testid="connect-submit">
              {submitting ? 'Saving…' : (connected ? 'Update account' : 'Connect bank account')}
            </Button>
            {connected && (
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)} className="text-[#A0A0AB] hover:text-white" data-testid="connect-cancel">Cancel</Button>
            )}
          </div>

          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-start gap-2">
            <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-blue-200">Once verified by Stripe, approved withdrawals will be paid out automatically to your bank (if admin has enabled automated payouts). Payouts typically arrive within 1–2 business days.</p>
          </div>
        </form>
      )}
    </div>
  );
}
