import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  MessageSquare,
  Inbox,
  Users,
  Settings as SettingsIcon,
  FlaskConical,
  Check,
  X,
  Send,
  Paperclip,
  RefreshCw,
  Phone,
  Mail,
  ShieldCheck,
  ShieldOff,
  Wrench,
  Plus,
  Trash2,
  Pencil,
} from 'lucide-react';
import { agentApi, ContactInput } from '../services/api';
import {
  AgentApproval,
  AgentContact,
  AgentConversation,
  AgentMessage,
  AgentSettings,
  SimulateResult,
} from '../types';

type Tab = 'inbox' | 'approvals' | 'contacts' | 'settings' | 'console';

const errorText = (err: any, fallback: string) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d: any) => d.msg).join(', ');
  return fallback;
};

const fmtTime = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
  return d.toLocaleString(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};

const APPROVAL_LABELS: Record<AgentApproval['type'], string> = {
  invoice_action: 'Invoice action',
  outbound_message: 'Message to send',
  document_copy: 'Send invoice copy',
  held_reply: 'Reply waiting (auto-reply off)',
  handoff: 'Needs a person',
  new_contact: 'New vendor / customer',
};

const LANGS: [string, string][] = [
  ['auto', 'Same as sender'],
  ['en', 'English'],
  ['ta', 'Tamil'],
  ['te', 'Telugu'],
  ['hi', 'Hindi'],
];

const Badge: React.FC<{ tone?: 'gray' | 'blue' | 'green' | 'amber' | 'red'; children: React.ReactNode }> = ({
  tone = 'gray',
  children,
}) => {
  const tones = {
    gray: 'bg-gray-50 text-gray-600 border-gray-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-800 border-amber-200',
    red: 'bg-red-50 text-red-700 border-red-200',
  };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
};

const ChannelIcon: React.FC<{ channel: string }> = ({ channel }) =>
  channel === 'email' ? <Mail className="w-3.5 h-3.5 text-gray-400" /> : <Phone className="w-3.5 h-3.5 text-gray-400" />;

// ============================================================================ Inbox
const InboxTab: React.FC = () => {
  const [conversations, setConversations] = useState<AgentConversation[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const threadEnd = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(async () => {
    try {
      const res = await agentApi.getConversations();
      setConversations(res.data);
      setSelected((cur) => cur ?? res.data[0]?.id ?? null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    const t = setInterval(loadConversations, 15000);
    return () => clearInterval(t);
  }, [loadConversations]);

  useEffect(() => {
    if (selected == null) return;
    agentApi.getMessages(selected).then((res) => setMessages(res.data.messages));
  }, [selected, conversations]);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  const current = conversations.find((c) => c.id === selected);

  if (loading) return <Spinner />;
  if (!conversations.length) {
    return (
      <EmptyState
        icon={MessageSquare}
        title="No conversations yet"
        text="When vendors or staff message your WhatsApp number or email, conversations appear here. Try the Test console tab."
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] border border-gray-200 rounded-lg bg-white overflow-hidden min-h-[520px]">
      <div className="border-b md:border-b-0 md:border-r border-gray-200 max-h-[560px] overflow-y-auto">
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => setSelected(c.id)}
            className={`w-full text-left px-3 py-2.5 border-b border-gray-100 transition-colors ${
              c.id === selected ? 'bg-blue-50' : 'hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 min-w-0">
                <ChannelIcon channel={c.channel} />
                <span className="text-xs font-semibold text-gray-900 truncate">
                  {c.contact?.display_name || c.sender_address}
                </span>
              </div>
              <span className="text-[10px] text-gray-400 shrink-0">{fmtTime(c.last_message_at)}</span>
            </div>
            <div className="flex items-center gap-1.5 mt-1">
              {c.contact && !c.contact.verified && <Badge tone="amber">unverified</Badge>}
              {c.contact?.kind === 'staff' && <Badge tone="blue">staff</Badge>}
              <p className="text-[11px] text-gray-500 truncate">
                {c.last_direction === 'outbound' ? 'Assistant: ' : ''}
                {c.last_message}
              </p>
            </div>
          </button>
        ))}
      </div>

      <div className="flex flex-col min-w-0">
        {current && (
          <div className="px-4 py-2.5 border-b border-gray-200 flex items-center justify-between gap-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">
                {current.contact?.display_name || current.sender_address}
              </p>
              <p className="text-[11px] text-gray-500 font-mono truncate">
                {current.channel} · {current.sender_address}
                {current.contact?.vendor_name ? ` · ${current.contact.vendor_name}` : ''}
              </p>
            </div>
            <button
              onClick={loadConversations}
              className="p-1.5 rounded border border-gray-200 text-gray-500 hover:bg-gray-50"
              aria-label="Refresh"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto max-h-[500px] p-4 space-y-3 bg-slate-50">
          {messages.map((m) => (
            <div key={m.id} className={`flex ${m.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] sm:max-w-[70%] rounded-lg px-3 py-2 text-xs whitespace-pre-wrap break-words ${
                  m.direction === 'outbound'
                    ? 'bg-blue-600 text-white rounded-br-sm'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm'
                }`}
              >
                {m.media.length > 0 && (
                  <div className="flex items-center gap-1 mb-1 opacity-80">
                    <Paperclip className="w-3 h-3" />
                    <span>{m.media.map((x) => x.filename).join(', ')}</span>
                  </div>
                )}
                {m.content}
                {m.tool_calls.length > 0 && (
                  <div className="mt-1.5 pt-1.5 border-t border-white/20 flex flex-wrap gap-1">
                    {m.tool_calls.map((t, i) => (
                      <span key={i} className="inline-flex items-center gap-0.5 text-[10px] opacity-80 font-mono">
                        <Wrench className="w-2.5 h-2.5" />
                        {t.name}
                        {t.outcome !== 'ok' ? ` (${t.outcome})` : ''}
                      </span>
                    ))}
                  </div>
                )}
                <div
                  className={`mt-1 text-[10px] ${m.direction === 'outbound' ? 'text-blue-100' : 'text-gray-400'}`}
                >
                  {fmtTime(m.created_at)}
                  {m.status !== 'sent' && m.status !== 'received' ? ` · ${m.status}` : ''}
                </div>
              </div>
            </div>
          ))}
          <div ref={threadEnd} />
        </div>
      </div>
    </div>
  );
};

// ============================================================================ Approvals
const ApprovalsTab: React.FC<{ onCountChange: (n: number) => void }> = ({ onCountChange }) => {
  const [items, setItems] = useState<AgentApproval[]>([]);
  const [filter, setFilter] = useState('pending');
  const [edits, setEdits] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const res = await agentApi.getApprovals(filter);
    setItems(res.data);
    if (filter === 'pending') onCountChange(res.data.length);
    setLoading(false);
  }, [filter, onCountChange]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = async (item: AgentApproval, approve: boolean) => {
    setBusy(item.id);
    setError(null);
    try {
      if (approve) await agentApi.approve(item.id, edits[item.id]);
      else await agentApi.reject(item.id);
      await load();
    } catch (err) {
      setError(errorText(err, 'Could not update this item.'));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs text-gray-500">
          Nothing in this list reaches a vendor until someone approves it here.
        </p>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white"
        >
          <option value="pending">Pending</option>
          <option value="sent">Sent</option>
          <option value="resolved">Resolved</option>
          <option value="rejected">Rejected</option>
          <option value="all">All</option>
        </select>
      </div>
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
      {loading ? (
        <Spinner />
      ) : !items.length ? (
        <EmptyState icon={Inbox} title="Nothing waiting" text="Approval requests from the assistant will appear here." />
      ) : (
        <div className="space-y-2">
          {items.map((item) => {
            const editable =
              item.status === 'pending' && (item.type === 'outbound_message' || item.type === 'held_reply');
            return (
              <div key={item.id} className="bg-white border border-gray-200 rounded-lg p-3">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Badge tone={item.type === 'handoff' ? 'amber' : item.type === 'new_contact' ? 'green' : 'blue'}>{APPROVAL_LABELS[item.type]}</Badge>
                      <Badge tone={item.status === 'pending' ? 'gray' : item.status === 'rejected' ? 'red' : 'green'}>
                        {item.status}
                      </Badge>
                      <span className="text-[10px] text-gray-400">{fmtTime(item.created_at)}</span>
                    </div>
                    <p className="text-xs text-gray-800 mt-1.5">{item.summary}</p>
                    {item.type === 'handoff' && item.payload.summary && (
                      <p className="text-[11px] text-gray-500 mt-1 whitespace-pre-wrap">{item.payload.summary}</p>
                    )}
                  </div>
                  {item.status === 'pending' && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        disabled={busy === item.id}
                        onClick={() => decide(item, true)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50"
                      >
                        <Check className="w-3.5 h-3.5" />
                        {item.type === 'handoff' || item.type === 'new_contact' ? 'Mark handled' : editable || item.type === 'document_copy' ? 'Approve & send' : 'Approve'}
                      </button>
                      <button
                        disabled={busy === item.id}
                        onClick={() => decide(item, false)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded border border-gray-200 text-gray-700 text-xs hover:bg-gray-50 disabled:opacity-50"
                      >
                        <X className="w-3.5 h-3.5" />
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
                {editable && (
                  <textarea
                    value={edits[item.id] ?? item.payload.text ?? ''}
                    onChange={(e) => setEdits({ ...edits, [item.id]: e.target.value })}
                    rows={3}
                    className="mt-2 w-full text-xs border border-gray-200 rounded px-2.5 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// ============================================================================ Contacts
const emptyContact: ContactInput = {
  display_name: '',
  kind: 'vendor',
  vendor_name: '',
  user_email: '',
  phone: '',
  email: '',
  verified: true,
  preferred_language: 'auto',
  notes: '',
};

const ContactsTab: React.FC = () => {
  const [contacts, setContacts] = useState<AgentContact[]>([]);
  const [form, setForm] = useState<ContactInput | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    const res = await agentApi.getContacts();
    setContacts(res.data);
    setLoading(false);
  };
  useEffect(() => {
    load();
  }, []);

  const startEdit = (c?: AgentContact) => {
    setError(null);
    if (!c) {
      setEditingId(null);
      setForm({ ...emptyContact });
      return;
    }
    setEditingId(c.id);
    setForm({
      display_name: c.display_name.replace(/^Unknown /, ''),
      kind: c.kind,
      vendor_name: c.vendor_name || '',
      user_email: c.user_email || '',
      phone: c.phone_e164 || '',
      email: c.email || '',
      verified: true, // saving from this form verifies the contact
      preferred_language: c.preferred_language || 'auto',
      notes: c.notes || '',
    });
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form) return;
    setError(null);
    const body: ContactInput = {
      ...form,
      vendor_name: form.kind === 'vendor' ? form.vendor_name : undefined,
      user_email: form.kind === 'staff' ? form.user_email : undefined,
      phone: form.phone || undefined,
      email: form.email || undefined,
    };
    try {
      if (editingId) await agentApi.updateContact(editingId, body);
      else await agentApi.createContact(body);
      setForm(null);
      await load();
    } catch (err) {
      setError(errorText(err, 'Could not save contact.'));
    }
  };

  const remove = async (c: AgentContact) => {
    if (!window.confirm(`Remove ${c.display_name}? They will no longer get invoice details from the assistant.`)) return;
    await agentApi.deleteContact(c.id);
    await load();
  };

  const input = 'w-full text-xs border border-gray-200 rounded px-2.5 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500';

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <p className="text-xs text-gray-500 max-w-xl">
          Verified vendors see invoices for their vendor name; staff get the permissions of their linked login.
          New vendors who introduce themselves on chat appear here as “new” and only see invoices they sent
          until you edit and save them.
        </p>
        <button
          onClick={() => startEdit()}
          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded bg-blue-600 text-white text-xs font-medium hover:bg-blue-700"
        >
          <Plus className="w-3.5 h-3.5" /> Add contact
        </button>
      </div>

      {form && (
        <form onSubmit={save} className="bg-white border border-blue-200 rounded-lg p-4 space-y-3">
          <p className="text-sm font-semibold text-gray-900">{editingId ? 'Edit contact' : 'New contact'}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-gray-600">Name</span>
              <input required className={input} value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="Ravi (Quantum Solutions)" />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-gray-600">Type</span>
              <select className={input} value={form.kind}
                onChange={(e) => setForm({ ...form, kind: e.target.value as 'vendor' | 'staff' })}>
                <option value="vendor">Vendor</option>
                <option value="staff">Staff (owner / reviewer)</option>
              </select>
            </label>
            {form.kind === 'vendor' ? (
              <label className="space-y-1 sm:col-span-2">
                <span className="text-[11px] font-medium text-gray-600">Vendor name exactly as on their invoices</span>
                <input required className={input} value={form.vendor_name}
                  onChange={(e) => setForm({ ...form, vendor_name: e.target.value })} placeholder="Quantum Solutions LLC" />
              </label>
            ) : (
              <label className="space-y-1 sm:col-span-2">
                <span className="text-[11px] font-medium text-gray-600">Linked InvoShield user (email)</span>
                <input required className={input} value={form.user_email}
                  onChange={(e) => setForm({ ...form, user_email: e.target.value })} placeholder="owner@yourshop.in" />
              </label>
            )}
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-gray-600">WhatsApp number</span>
              <input className={input} value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 98765 43210" />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-gray-600">Email</span>
              <input className={input} type="email" value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="accounts@vendor.in" />
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-medium text-gray-600">Preferred language</span>
              <select className={input} value={form.preferred_language}
                onChange={(e) => setForm({ ...form, preferred_language: e.target.value })}>
                {LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label className="flex items-center gap-2 pt-5">
              <input type="checkbox" checked={form.verified}
                onChange={(e) => setForm({ ...form, verified: e.target.checked })} />
              <span className="text-xs text-gray-700">Verified (allowed to receive invoice details)</span>
            </label>
          </div>
          {error && <p className="text-xs text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button type="submit" className="px-3 py-1.5 rounded bg-blue-600 text-white text-xs font-medium hover:bg-blue-700">
              Save
            </button>
            <button type="button" onClick={() => setForm(null)}
              className="px-3 py-1.5 rounded border border-gray-200 text-gray-700 text-xs hover:bg-gray-50">
              Cancel
            </button>
          </div>
        </form>
      )}

      {loading ? <Spinner /> : !contacts.length ? (
        <EmptyState icon={Users} title="No contacts yet" text="Add your vendors' WhatsApp numbers and your own number as staff." />
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-50 text-gray-500 text-[11px] uppercase tracking-wide">
              <tr>
                <th className="text-left font-medium px-3 py-2">Contact</th>
                <th className="text-left font-medium px-3 py-2">Access</th>
                <th className="text-left font-medium px-3 py-2">Reach</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {contacts.map((c) => (
                <tr key={c.id}>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      {c.verified ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> : <ShieldOff className="w-3.5 h-3.5 text-amber-600" />}
                      <span className="font-medium text-gray-900">{c.display_name}</span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-gray-600">
                    {!c.verified ? (
                      c.self_registered && c.onboarding_step !== 'blocked' ? (
                        <span className="flex items-center gap-1.5 flex-wrap">
                          <Badge tone="green">new · self-registered</Badge>
                          <span className="text-[11px] text-gray-500">
                            {c.vendor_name ? `says: ${c.vendor_name}` : 'name not given yet'} · edit &amp; save to verify
                          </span>
                        </span>
                      ) : <Badge tone="amber">unverified</Badge>
                    ) : c.kind === 'staff'
                      ? <span>Staff · {c.user_email} ({c.user_role})</span>
                      : <span>Vendor · {c.vendor_name}</span>}
                  </td>
                  <td className="px-3 py-2 text-gray-600 font-mono text-[11px]">
                    {[c.phone_e164, c.email].filter(Boolean).join(' · ')}
                  </td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    <button onClick={() => startEdit(c)} className="p-1 text-gray-500 hover:text-blue-600" aria-label="Edit">
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => remove(c)} className="p-1 text-gray-500 hover:text-red-600" aria-label="Remove">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

// ============================================================================ Settings
const StatusRow: React.FC<{ label: string; ok: boolean; detail?: string; okText?: string; offText?: string }> = ({
  label,
  ok,
  detail,
  okText = 'ready',
  offText = 'not set',
}) => (
  <div className="flex items-center justify-between gap-2 py-1.5 text-xs">
    <span className="text-gray-600">{label}</span>
    <span className="flex items-center gap-1.5 min-w-0">
      {detail && <span className="text-[11px] text-gray-400 font-mono truncate">{detail}</span>}
      <Badge tone={ok ? 'green' : offText === 'not set' ? 'gray' : 'amber'}>{ok ? okText : offText}</Badge>
    </span>
  </div>
);

const SettingsTab: React.FC = () => {
  const [s, setS] = useState<AgentSettings | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    agentApi.getSettings().then((res) => setS(res.data));
  }, []);

  if (!s) return <Spinner />;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await agentApi.updateSettings({
        business_name: s.business_name,
        default_language: s.default_language,
        auto_reply: s.auto_reply,
        notify_vendors: s.notify_vendors,
        allow_new_contacts: s.allow_new_contacts,
      });
      setS(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      setError(errorText(err, 'Could not save settings.'));
    }
  };

  const input = 'w-full text-xs border border-gray-200 rounded px-2.5 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <form onSubmit={save} className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
        <p className="text-sm font-semibold text-gray-900">Assistant behaviour</p>
        <label className="block space-y-1">
          <span className="text-[11px] font-medium text-gray-600">Business name (used in replies and templates)</span>
          <input required className={input} value={s.business_name || ''}
            onChange={(e) => setS({ ...s, business_name: e.target.value })} />
        </label>
        <label className="block space-y-1">
          <span className="text-[11px] font-medium text-gray-600">Default reply language</span>
          <select className={input} value={s.default_language}
            onChange={(e) => setS({ ...s, default_language: e.target.value })}>
            {LANGS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="flex items-start gap-2">
          <input type="checkbox" className="mt-0.5" checked={s.auto_reply}
            onChange={(e) => setS({ ...s, auto_reply: e.target.checked })} />
          <span className="text-xs text-gray-700">
            Auto-reply to vendors
            <span className="block text-[11px] text-gray-500">When off, every reply waits in Approvals for you to send.</span>
          </span>
        </label>
        <label className="flex items-start gap-2">
          <input type="checkbox" className="mt-0.5" checked={s.allow_new_contacts}
            onChange={(e) => setS({ ...s, allow_new_contacts: e.target.checked })} />
          <span className="text-xs text-gray-700">
            Welcome new vendors and customers
            <span className="block text-[11px] text-gray-500">
              Unknown numbers are greeted, asked their name and business, and can send invoices straight away.
              They only see invoices they sent until you verify them in Contacts.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2">
          <input type="checkbox" className="mt-0.5" checked={s.notify_vendors}
            onChange={(e) => setS({ ...s, notify_vendors: e.target.checked })} />
          <span className="text-xs text-gray-700">
            Notify vendors when invoices are approved, rejected or paid
            <span className="block text-[11px] text-gray-500">Sent as WhatsApp templates, so they work outside the 24-hour window.</span>
          </span>
        </label>
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button type="submit" className="px-3 py-1.5 rounded bg-blue-600 text-white text-xs font-medium hover:bg-blue-700">
          {saved ? 'Saved' : 'Save settings'}
        </button>
      </form>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <p className="text-sm font-semibold text-gray-900 mb-1">Connections</p>
        <p className="text-[11px] text-gray-500 mb-2">Configured on the server through .env (see README).</p>
        <div className="divide-y divide-gray-100">
          <StatusRow label="Channel mode" ok={s.channel_mode === 'live'} okText="live" offText="mock" />
          <StatusRow label="Language model" ok={s.llm.provider === 'anthropic'} detail={s.llm.model || undefined}
            okText="Claude" offText="offline demo" />
          <StatusRow label="WhatsApp sending" ok={s.whatsapp.configured} />
          <StatusRow label="WhatsApp webhook secret" ok={s.whatsapp.webhook_secret_set} detail={s.whatsapp.webhook_path} />
          <StatusRow label="Email sending (SMTP)" ok={s.email.configured} />
          <StatusRow label="Email inbound" ok={s.email.webhook_secret_set || s.email.imap_configured} detail={s.email.webhook_path} />
        </div>
        {s.llm.provider !== 'anthropic' && (
          <p className="mt-3 text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-2.5 py-2">
            No ANTHROPIC_API_KEY is set, so the assistant uses a simple offline brain that only understands English.
            Add a key for Tamil, Telugu, Hindi and natural conversation.
          </p>
        )}
        <details className="mt-3">
          <summary className="text-xs text-gray-600 cursor-pointer">WhatsApp templates to submit to Meta</summary>
          <div className="mt-2 space-y-2">
            {Object.entries(s.templates).map(([name, body]) => (
              <div key={name} className="text-[11px]">
                <p className="font-mono font-medium text-gray-800">{name}</p>
                <p className="text-gray-500">{body}</p>
              </div>
            ))}
          </div>
        </details>
      </div>
    </div>
  );
};

// ============================================================================ Test console
const ConsoleTab: React.FC<{ onActivity: () => void }> = ({ onActivity }) => {
  const [contacts, setContacts] = useState<AgentContact[]>([]);
  const [sender, setSender] = useState('');
  const [channel, setChannel] = useState('whatsapp');
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [log, setLog] = useState<{ from: string; text: string; result?: SimulateResult }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    agentApi.getContacts().then((res) => {
      setContacts(res.data);
      const first = res.data.find((c) => c.verified && c.phone_e164);
      if (first?.phone_e164) setSender(first.phone_e164);
    });
  }, []);

  const options = useMemo(
    () => contacts.filter((c) => (channel === 'email' ? c.email : c.phone_e164)),
    [contacts, channel],
  );

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sender || (!text && !file)) return;
    setBusy(true);
    setError(null);
    const shown = text + (file ? `  [${file.name}]` : '');
    try {
      const res = await agentApi.simulate(sender, text, channel, file);
      setLog((l) => [...l, { from: sender, text: shown, result: res.data }]);
      setText('');
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
      onActivity();
    } catch (err) {
      setError(errorText(err, 'The test console is unavailable.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-500">
        Send a message as one of your contacts (or any number) to see exactly how the assistant replies. Works only
        in mock mode: nothing is really sent on WhatsApp or email.
      </p>
      <div className="bg-white border border-gray-200 rounded-lg">
        <div className="p-4 space-y-3 max-h-[420px] overflow-y-auto bg-slate-50 rounded-t-lg">
          {!log.length && <p className="text-xs text-gray-400 text-center py-8">Try “Did you get my bill?” as a vendor, or “Any suspicious invoices this week?” as staff.</p>}
          {log.map((entry, i) => (
            <div key={i} className="space-y-2">
              <div className="flex justify-start">
                <div className="max-w-[80%] bg-white border border-gray-200 rounded-lg rounded-bl-sm px-3 py-2 text-xs text-gray-800">
                  <p className="text-[10px] text-gray-400 font-mono mb-0.5">{entry.from}</p>
                  {entry.text}
                </div>
              </div>
              {entry.result?.outbox.map((o, j) => (
                <div key={j} className="flex justify-end">
                  <div className="max-w-[80%] bg-blue-600 text-white rounded-lg rounded-br-sm px-3 py-2 text-xs whitespace-pre-wrap">
                    {o.to !== entry.from && <p className="text-[10px] text-blue-100 font-mono mb-0.5">to {o.to}</p>}
                    {o.template ? <span className="text-[10px] uppercase tracking-wide text-blue-100 block">template · {o.template}</span> : null}
                    {o.text}
                    {o.buttons.length > 0 && (
                      <div className="flex gap-1 mt-1.5">
                        {o.buttons.map(([id, title]) => (
                          <span key={id} className="px-2 py-0.5 rounded bg-white/20 text-[10px]">{title}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {entry.result && entry.result.tool_calls.length > 0 && (
                <p className="text-right text-[10px] text-gray-400 font-mono">
                  {entry.result.tool_calls.map((t) => `${t.name}${t.outcome !== 'ok' ? ` (${t.outcome})` : ''}`).join(' · ')}
                </p>
              )}
              {entry.result?.status === 'held' && (
                <p className="text-right text-[10px] text-amber-700">Reply held for approval (auto-reply is off)</p>
              )}
            </div>
          ))}
        </div>
        <form onSubmit={send} className="border-t border-gray-200 p-3 space-y-2">
          <div className="flex gap-2 flex-wrap">
            <select value={channel} onChange={(e) => setChannel(e.target.value)}
              className="text-xs border border-gray-200 rounded px-2 py-1.5 bg-white">
              <option value="whatsapp">WhatsApp</option>
              <option value="email">Email</option>
            </select>
            <input list="console-senders" value={sender} onChange={(e) => setSender(e.target.value)}
              placeholder={channel === 'email' ? 'sender@example.com' : '+91 98765 43210'}
              className="flex-1 min-w-[180px] text-xs border border-gray-200 rounded px-2.5 py-1.5 font-mono" />
            <datalist id="console-senders">
              {options.map((c) => (
                <option key={c.id} value={(channel === 'email' ? c.email : c.phone_e164) || ''}>{c.display_name}</option>
              ))}
            </datalist>
          </div>
          <div className="flex gap-2">
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message…"
              className="flex-1 min-w-0 text-xs border border-gray-200 rounded px-2.5 py-2 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            <button type="button" onClick={() => fileRef.current?.click()}
              className={`px-2.5 rounded border text-xs ${file ? 'border-blue-300 bg-blue-50 text-blue-700' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}
              aria-label="Attach invoice">
              <Paperclip className="w-3.5 h-3.5" />
            </button>
            <input ref={fileRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.txt"
              onChange={(e) => setFile(e.target.files?.[0] || null)} />
            <button type="submit" disabled={busy}
              className="inline-flex items-center gap-1 px-3 rounded bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
              <Send className="w-3.5 h-3.5" /> Send
            </button>
          </div>
          {file && <p className="text-[11px] text-gray-500">Attached: {file.name}</p>}
          {error && <p className="text-xs text-red-600">{error}</p>}
        </form>
      </div>
    </div>
  );
};

// ============================================================================ shared bits
const Spinner: React.FC = () => (
  <div className="flex items-center justify-center min-h-[200px]">
    <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
  </div>
);

const EmptyState: React.FC<{ icon: React.ElementType; title: string; text: string }> = ({ icon: Icon, title, text }) => (
  <div className="bg-white border border-dashed border-gray-300 rounded-lg py-12 px-6 text-center">
    <Icon className="w-6 h-6 text-gray-300 mx-auto" />
    <p className="text-sm font-medium text-gray-700 mt-2">{title}</p>
    <p className="text-xs text-gray-500 mt-1 max-w-md mx-auto">{text}</p>
  </div>
);

// ============================================================================ page
export const AssistantInboxPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('inbox');
  const [pending, setPending] = useState(0);
  const [mode, setMode] = useState<'mock' | 'live' | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    agentApi.getSettings().then((res) => setMode(res.data.channel_mode)).catch(() => setMode(null));
    agentApi.getApprovals('pending').then((res) => setPending(res.data.length)).catch(() => undefined);
  }, [refreshKey]);

  const tabs: { id: Tab; label: string; icon: React.ElementType; hidden?: boolean }[] = [
    { id: 'inbox', label: 'Conversations', icon: MessageSquare },
    { id: 'approvals', label: 'Approvals', icon: Inbox },
    { id: 'contacts', label: 'Contacts', icon: Users },
    { id: 'settings', label: 'Settings', icon: SettingsIcon },
    { id: 'console', label: 'Test console', icon: FlaskConical, hidden: mode !== 'mock' },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 tracking-tight">Assistant Inbox</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            WhatsApp and email conversations handled by the InvoShield Assistant, and everything waiting for your OK.
          </p>
        </div>
        {mode && (
          <span className={`self-start sm:self-auto px-2.5 py-1 rounded border text-xs font-mono ${
            mode === 'live' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-amber-50 border-amber-200 text-amber-800'
          }`}>
            {mode === 'live' ? 'Live channels' : 'Mock mode · nothing is really sent'}
          </span>
        )}
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-gray-200 -mt-2">
        {tabs.filter((t) => !t.hidden).map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium whitespace-nowrap border-b-2 -mb-px transition-colors ${
                tab === t.id ? 'border-blue-600 text-blue-700' : 'border-transparent text-gray-500 hover:text-gray-800'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
              {t.id === 'approvals' && pending > 0 && (
                <span className="ml-0.5 px-1.5 rounded-full bg-blue-600 text-white text-[10px]">{pending}</span>
              )}
            </button>
          );
        })}
      </div>

      {tab === 'inbox' && <InboxTab key={refreshKey} />}
      {tab === 'approvals' && <ApprovalsTab onCountChange={setPending} />}
      {tab === 'contacts' && <ContactsTab />}
      {tab === 'settings' && <SettingsTab />}
      {tab === 'console' && <ConsoleTab onActivity={() => setRefreshKey((k) => k + 1)} />}
    </div>
  );
};

export default AssistantInboxPage;
