import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const API = 'http://localhost:5000';
const ax = axios.create({ baseURL: API, withCredentials: true });

// ── palette ──────────────────────────────────────────────────────────────────
// Brown/Cream theme — consistent with customer-facing pages
const C = {
  // Primary browns
  brown:      '#7f5539',    // Primary brand color
  brownDark:  '#5c3d2e',    // Darker shade for backgrounds
  brownMid:   '#9c6644',    // Mid-tone accent

  // Cream backgrounds
  cream:      '#e6ccb2',    // Light cream
  creamLight: '#ede0d4',    // Lightest cream (page bg)
  creamDark:  '#ddb892',    // Darker cream for contrast

  // Functional colors (keep for verdicts)
  gold:       '#F5A623',    // FLAG verdict
  orange:     '#F6AD55',    // ALERT verdict
  red:        '#E53E3E',    // BLOCK/error
  green:      '#4caf50',    // ALLOW/success
  purple:     '#805AD5',    // Case IDs

  // Text colors
  white:      '#FFFFFF',
  silver:     '#8b7b6f',    // Warm silver for secondary text
  slate:      '#6b5b4f',    // Warm slate for muted text
  mgray:      '#7a6a5e',    // Warm mid-gray
};

const VERDICT_CFG = {
  FLAG:   { color: C.gold,   bg: '#3d3020', label: 'FLAG' },
  ALERT:  { color: C.orange, bg: '#3d2a15', label: 'ALERT' },
  BLOCK:  { color: C.red,    bg: '#3d1010', label: 'BLOCK' },
  ALLOW:  { color: C.green,  bg: '#1a3d1a', label: 'ALLOW' },
};

const pill = (verdict) => {
  const cfg = VERDICT_CFG[verdict] || { color: C.silver, bg: C.brownDark, label: verdict || '—' };
  return (
    <span style={{
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}40`,
      borderRadius: 6, padding: '2px 10px',
      fontSize: 11, fontWeight: 700, letterSpacing: 1,
      fontFamily: 'monospace',
    }}>{cfg.label}</span>
  );
};

// ── tab bar ───────────────────────────────────────────────────────────────────
const TabBar = ({ tabs, active, onChange }) => (
  <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
    {tabs.map(t => (
      <button key={t.id} onClick={() => onChange(t.id)} style={{
        padding: '8px 18px', borderRadius: 8, border: 'none',
        background: active === t.id ? C.brown : C.cream,
        color: active === t.id ? C.white : C.brownDark,
        fontWeight: 700, fontSize: 13, cursor: 'pointer',
        transition: 'all .15s',
      }}>{t.label}{t.count !== undefined ? ` (${t.count})` : ''}</button>
    ))}
  </div>
);

// ── stat card ─────────────────────────────────────────────────────────────────
const StatCard = ({ label, value, accent, icon }) => (
  <div style={{
    background: C.white, borderRadius: 12, padding: '20px 24px',
    borderLeft: `4px solid ${accent}`, flex: 1, minWidth: 160,
    boxShadow: '0 2px 8px rgba(127,85,57,0.1)',
  }}>
    <div style={{ fontSize: 12, color: C.brownMid, marginBottom: 6, fontWeight: 600, letterSpacing: 1 }}>
      {icon} {label}
    </div>
    <div style={{ fontSize: 32, fontWeight: 800, color: accent }}>{value ?? '—'}</div>
  </div>
);

// ── main component ────────────────────────────────────────────────────────────
export default function AdminDashboardPage() {
  const navigate    = useNavigate();
  const [tab, setTab]         = useState('transactions');
  const [filter, setFilter]   = useState('ALL');
  const [txns, setTxns]       = useState([]);
  const [frozen, setFrozen]   = useState([]);
  const [cases, setCases]     = useState([]);
  const [stats, setStats]     = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [selected, setSelected] = useState(null);   // detail modal
  const [toastMsg, setToastMsg] = useState('');
  const [unfreezing, setUnfreezing] = useState(null);
  const [filings, setFilings]       = useState([]);

  // ── auth guard ──────────────────────────────────────────────────────────────
  useEffect(() => {
    ax.get('/api/admin/check_auth').then(r => {
      if (!r.data.authenticated) navigate('/goadmin');
    }).catch(() => navigate('/goadmin'));
  }, [navigate]);

  // ── data load ───────────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [statsR, txnsR, frozenR, casesR, filingsR] = await Promise.all([
        ax.get('/api/admin/dashboard'),
        ax.get('/api/admin/flagged-transactions?limit=100'),
        ax.get('/api/admin/frozen-accounts'),
        ax.get('/api/admin/cases?limit=50'),
        ax.get('/api/cla/filings?limit=50').catch(() => ({ data: { filings: [] } })),
      ]);
      setStats(statsR.data.stats        || {});
      setTxns(txnsR.data.transactions   || []);
      setFrozen(frozenR.data.frozen_accounts || []);
      setCases(casesR.data.cases        || []);
      setFilings(filingsR.data.filings  || []);
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ── toast helper ────────────────────────────────────────────────────────────
  const toast = (msg) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(''), 3500);
  };

  // ── unfreeze ────────────────────────────────────────────────────────────────
  const handleUnfreeze = async (customerId) => {
    if (!window.confirm(`Unfreeze account ${customerId}? This will allow the customer to transact again.`)) return;
    setUnfreezing(customerId);
    try {
      const r = await ax.post(`/api/admin/unfreeze/${customerId}`);
      toast(r.data.message || 'Account unfrozen.');
      load();
    } catch (e) {
      toast('❌ ' + (e.response?.data?.error || 'Unfreeze failed.'));
    } finally {
      setUnfreezing(null);
    }
  };

  // ── filing actions ────────────────────────────────────────────────────────
  const handleApproveFiling = async (filingId) => {
    try {
      await ax.post(`/api/cla/filings/${filingId}/approve`, {});
      toast('✅ Filing approved.');
      load();
    } catch (e) {
      toast('❌ ' + (e.response?.data?.error || 'Approve failed.'));
    }
  };

  const handleRejectFiling = async (filingId) => {
    if (!window.confirm(`Reject filing ${filingId}?`)) return;
    try {
      await ax.post(`/api/cla/filings/${filingId}/reject`, {});
      toast('Filing rejected.');
      load();
    } catch (e) {
      toast('❌ ' + (e.response?.data?.error || 'Reject failed.'));
    }
  };

  // ── pdf export ───────────────────────────────────────────────────────────────
  const handlePDF = (filingId) => {
    window.open(`${API}/api/cla/filings/${filingId}/export_pdf`, '_blank');
  };

  // ── alert pdf export ────────────────────────────────────────────────────────
  const handleAlertPDF = (alertId) => {
    window.open(`${API}/api/admin/alerts/${alertId}/pdf`, '_blank');
  };

  // ── block pdf export ────────────────────────────────────────────────────────
  const handleBlockPDF = (customerId) => {
    window.open(`${API}/api/admin/frozen/${customerId}/pdf`, '_blank');
  };

  // ── logout ───────────────────────────────────────────────────────────────────
  const handleLogout = async () => {
    await ax.post('/api/admin/logout').catch(() => {});
    navigate('/goadmin');
  };

  // ── filtered transactions ────────────────────────────────────────────────────
  const filteredTxns = filter === 'ALL' ? txns
    : txns.filter(t => t.tma_decision === filter);

  // ── counts ────────────────────────────────────────────────────────────────────
  const counts = {
    FLAG:  txns.filter(t => t.tma_decision === 'FLAG').length,
    ALERT: txns.filter(t => t.tma_decision === 'ALERT').length,
    BLOCK: txns.filter(t => t.tma_decision === 'BLOCK').length,
  };

  // ── styles ────────────────────────────────────────────────────────────────────
  const th = {
    padding: '10px 14px', fontSize: 11, fontWeight: 700,
    color: C.brownMid, textTransform: 'uppercase', letterSpacing: 1,
    borderBottom: `1px solid ${C.cream}`, background: C.creamLight,
    textAlign: 'left',
  };
  const td = {
    padding: '12px 14px', fontSize: 13, color: C.brownDark,
    borderBottom: `1px solid ${C.cream}22`,
  };

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: C.creamLight, fontFamily: "'DM Sans', 'Segoe UI', sans-serif" }}>
      {/* Header */}
      <div style={{
        background: `linear-gradient(135deg, ${C.brown} 0%, ${C.brownMid} 100%)`,
        borderBottom: `1px solid ${C.brownDark}`,
        padding: '0 32px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', height: 60,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: `linear-gradient(135deg, ${C.cream}, ${C.creamDark})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16,
          }}>🦅</div>
          <span style={{ color: C.white, fontWeight: 800, fontSize: 17, letterSpacing: 0.5 }}>
            Jatayu Admin
          </span>
          <span style={{
            background: C.creamDark, color: C.brownDark,
            fontSize: 11, padding: '2px 8px', borderRadius: 4, fontWeight: 600,
          }}>CLA Management</span>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button onClick={load} style={{
            background: C.cream, color: C.brownDark, border: 'none',
            borderRadius: 8, padding: '7px 14px', cursor: 'pointer', fontSize: 13,
          }}>↻ Refresh</button>
          <button onClick={handleLogout} style={{
            background: 'transparent', color: C.cream,
            border: `1px solid ${C.cream}66`, borderRadius: 8,
            padding: '7px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
          }}>Sign Out</button>
        </div>
      </div>

      {/* Toast */}
      {toastMsg && (
        <div style={{
          position: 'fixed', top: 72, right: 24, zIndex: 9999,
          background: toastMsg.startsWith('❌') ? '#fde8e8' : '#e8f5e9',
          color: toastMsg.startsWith('❌') ? C.red : C.green,
          border: `1px solid ${toastMsg.startsWith('❌') ? C.red : C.green}44`,
          borderRadius: 10, padding: '12px 20px', fontWeight: 600, fontSize: 14,
          boxShadow: '0 8px 32px rgba(127,85,57,0.2)',
        }}>{toastMsg}</div>
      )}

      <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto' }}>
        {/* Error */}
        {error && (
          <div style={{
            background: '#fde8e8', color: C.red, border: `1px solid ${C.red}44`,
            borderRadius: 10, padding: '12px 18px', marginBottom: 20, fontSize: 14,
          }}>⚠ {error}</div>
        )}

        {/* Stat cards */}
        <div style={{ display: 'flex', gap: 16, marginBottom: 28, flexWrap: 'wrap' }}>
          <StatCard label="PENDING STR"    value={stats.pending_str}    accent={C.gold}     icon="⏳" />
          <StatCard label="FILED STR"      value={stats.filed_str}      accent={C.green}    icon="✅" />
          <StatCard label="OPEN CASES"     value={stats.open_cases}     accent={C.purple}   icon="📁" />
          <StatCard label="TOTAL CITATIONS" value={stats.total_citations} accent={C.brownMid} icon="📜" />
          <StatCard label="FROZEN ACCOUNTS" value={frozen.length}        accent={C.red}      icon="🔒" />
        </div>

        {/* Tab nav */}
        <TabBar
          active={tab}
          onChange={setTab}
          tabs={[
            { id: 'transactions', label: 'Flagged Transactions', count: txns.length },
            { id: 'filings',      label: 'STR / CTR Filings',   count: filings.length },
            { id: 'frozen',       label: 'Frozen Accounts',      count: frozen.length },
            { id: 'cases',        label: 'Fraud Cases',          count: cases.length },
          ]}
        />

        {loading ? (
          <div style={{ textAlign: 'center', color: C.silver, padding: 60, fontSize: 15 }}>
            Loading…
          </div>
        ) : (
          <>
            {/* ── TAB: FLAGGED TRANSACTIONS ─────────────────────────────── */}
            {tab === 'transactions' && (
              <div>
                {/* Verdict filter */}
                <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                  {['ALL', 'FLAG', 'ALERT', 'BLOCK'].map(v => (
                    <button key={v} onClick={() => setFilter(v)} style={{
                      padding: '6px 16px', borderRadius: 7, border: 'none',
                      background: filter === v
                        ? (VERDICT_CFG[v]?.color || C.brown)
                        : C.cream,
                      color: filter === v ? C.white : C.brownDark,
                      fontWeight: 700, fontSize: 12, cursor: 'pointer',
                      letterSpacing: 1,
                    }}>
                      {v}{v !== 'ALL' ? ` · ${counts[v] || 0}` : ''}
                    </button>
                  ))}
                </div>

                <div style={{ background: C.white, borderRadius: 12, overflow: 'hidden', border: `1px solid ${C.cream}`, boxShadow: '0 2px 8px rgba(127,85,57,0.08)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {['Alert ID','Customer','Amount','TMA','RAA','Tier','Typology','Frozen?','Created','Actions'].map(h => (
                          <th key={h} style={th}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTxns.length === 0 ? (
                        <tr><td colSpan={10} style={{ ...td, textAlign: 'center', color: C.brownMid, padding: 40 }}>
                          No {filter === 'ALL' ? 'flagged' : filter} transactions found.
                        </td></tr>
                      ) : filteredTxns.map(t => (
                        <tr key={t.alert_id} style={{ cursor: 'pointer' }}
                          onMouseEnter={e => e.currentTarget.style.background = C.creamLight}
                          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                          <td style={{ ...td, fontFamily: 'monospace', fontSize: 12, color: C.brownMid }}>
                            #{t.alert_id}
                          </td>
                          <td style={td}>
                            <div style={{ fontWeight: 600 }}>{t.customer_name || t.customer_id}</div>
                            <div style={{ fontSize: 11, color: C.mgray }}>{t.account_number}</div>
                          </td>
                          <td style={{ ...td, fontWeight: 700, color: C.brown }}>
                            ₹{parseFloat(t.amount || 0).toLocaleString('en-IN')}
                          </td>
                          <td style={td}>{pill(t.tma_decision)}</td>
                          <td style={td}>{pill(t.raa_verdict)}</td>
                          <td style={{ ...td, color: C.brownMid, fontSize: 12 }}>{t.customer_tier || '—'}</td>
                          <td style={{ ...td, fontSize: 12, fontFamily: 'monospace', color: C.purple }}>
                            {t.typology_code || '—'}
                          </td>
                          <td style={td}>
                            {t.is_frozen
                              ? <span style={{ color: C.red, fontWeight: 700, fontSize: 12 }}>🔒 YES</span>
                              : <span style={{ color: C.green, fontSize: 12 }}>✓ No</span>}
                          </td>
                          <td style={{ ...td, fontSize: 11, color: C.brownMid }}>
                            {t.created_at ? new Date(t.created_at).toLocaleString('en-IN') : '—'}
                          </td>
                          <td style={td}>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button onClick={() => setSelected(t)} style={{
                                background: C.cream, color: C.brownDark, border: 'none',
                                borderRadius: 6, padding: '5px 10px', cursor: 'pointer', fontSize: 12,
                              }}>Details</button>
                              <button onClick={() => handleAlertPDF(t.alert_id)} style={{
                                background: `${C.brownMid}22`, color: C.brownMid,
                                border: `1px solid ${C.brownMid}44`,
                                borderRadius: 6, padding: '5px 10px',
                                cursor: 'pointer', fontSize: 12, fontWeight: 700,
                              }} title="Export Alert PDF">📄 PDF</button>
                              {t.is_frozen && (
                                <button
                                  onClick={() => handleUnfreeze(t.customer_id)}
                                  disabled={unfreezing === t.customer_id}
                                  style={{
                                    background: `${C.green}22`, color: C.green,
                                    border: `1px solid ${C.green}44`,
                                    borderRadius: 6, padding: '5px 10px',
                                    cursor: 'pointer', fontSize: 12, fontWeight: 700,
                                  }}>
                                  {unfreezing === t.customer_id ? '…' : '🔓 Unfreeze'}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* ── TAB: STR / CTR FILINGS ───────────────────────────────── */}
            {tab === 'filings' && (() => {
              const FILING_STATUS = {
                PENDING_APPROVAL: { color: C.gold,   label: 'PENDING' },
                APPROVED:         { color: C.green,  label: 'APPROVED' },
                AUTO_FILED:       { color: C.green,  label: 'AUTO FILED' },
                FILED:            { color: C.green,  label: 'FILED' },
                REJECTED:         { color: C.red,    label: 'REJECTED' },
              };
              return (
                <div style={{ background: C.white, borderRadius: 12, overflow: 'hidden', border: `1px solid ${C.cream}`, boxShadow: '0 2px 8px rgba(127,85,57,0.08)' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr>
                        {['Filing ID','Type','Customer','Amount','Status','Created','Actions'].map(h => (
                          <th key={h} style={th}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filings.length === 0 ? (
                        <tr><td colSpan={7} style={{ ...td, textAlign: 'center', color: C.brownMid, padding: 40 }}>
                          No regulatory filings found.
                        </td></tr>
                      ) : filings.map(f => {
                        const scfg = FILING_STATUS[f.status] || { color: C.brownMid, label: f.status };
                        return (
                          <tr key={f.filing_id}
                            onMouseEnter={e => e.currentTarget.style.background = C.creamLight}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                            <td style={{ ...td, fontFamily: 'monospace', fontSize: 12, color: C.brownMid }}>
                              {f.filing_id}
                            </td>
                            <td style={td}>
                              <span style={{
                                background: f.type === 'STR' ? `${C.red}22` : `${C.gold}22`,
                                color:      f.type === 'STR' ? C.red : C.gold,
                                border:     `1px solid ${f.type === 'STR' ? C.red : C.gold}44`,
                                borderRadius: 6, padding: '3px 10px',
                                fontSize: 11, fontWeight: 800, fontFamily: 'monospace',
                              }}>{f.type}</span>
                            </td>
                            <td style={td}>{f.customer_id}</td>
                            <td style={{ ...td, color: C.brown, fontWeight: 700 }}>
                              ₹{parseFloat(f.amount || 0).toLocaleString('en-IN')}
                            </td>
                            <td style={td}>
                              <span style={{
                                color: scfg.color,
                                background: `${scfg.color}22`,
                                border: `1px solid ${scfg.color}44`,
                                borderRadius: 6, padding: '3px 10px',
                                fontSize: 11, fontWeight: 700,
                              }}>{scfg.label}</span>
                            </td>
                            <td style={{ ...td, fontSize: 12, color: C.brownMid }}>
                              {f.created_at ? new Date(f.created_at).toLocaleDateString('en-IN') : '—'}
                            </td>
                            <td style={td}>
                              <div style={{ display: 'flex', gap: 6 }}>
                                {/* PDF export — always available */}
                                <button onClick={() => handlePDF(f.filing_id)} style={{
                                  background: `${C.brownMid}22`, color: C.brownMid,
                                  border: `1px solid ${C.brownMid}44`,
                                  borderRadius: 6, padding: '5px 10px',
                                  cursor: 'pointer', fontSize: 12, fontWeight: 700,
                                }}>📄 PDF</button>
                                {/* Approve / Reject — only for PENDING */}
                                {f.status === 'PENDING_APPROVAL' && (
                                  <>
                                    <button onClick={() => handleApproveFiling(f.filing_id)} style={{
                                      background: `${C.green}22`, color: C.green,
                                      border: `1px solid ${C.green}44`,
                                      borderRadius: 6, padding: '5px 10px',
                                      cursor: 'pointer', fontSize: 12, fontWeight: 700,
                                    }}>✅ Approve</button>
                                    <button onClick={() => handleRejectFiling(f.filing_id)} style={{
                                      background: `${C.red}22`, color: C.red,
                                      border: `1px solid ${C.red}44`,
                                      borderRadius: 6, padding: '5px 10px',
                                      cursor: 'pointer', fontSize: 12, fontWeight: 700,
                                    }}>✗ Reject</button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              );
            })()}

            {/* ── TAB: FROZEN ACCOUNTS ─────────────────────────────────── */}
            {tab === 'frozen' && (
              <div>
                {frozen.length === 0 ? (
                  <div style={{
                    background: C.white, borderRadius: 12, padding: 48,
                    textAlign: 'center', color: C.brownMid, border: `1px solid ${C.cream}`,
                    boxShadow: '0 2px 8px rgba(127,85,57,0.08)',
                  }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>✅</div>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>No frozen accounts</div>
                    <div style={{ fontSize: 13, marginTop: 6 }}>All customer accounts are currently active.</div>
                  </div>
                ) : (
                  <div style={{ background: C.white, borderRadius: 12, overflow: 'hidden', border: `1px solid ${C.cream}`, boxShadow: '0 2px 8px rgba(127,85,57,0.08)' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr>
                          {['Customer','Account','Frozen At','Reason','Alert ID','Actions'].map(h => (
                            <th key={h} style={th}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {frozen.map(f => (
                          <tr key={f.customer_id}
                            onMouseEnter={e => e.currentTarget.style.background = C.creamLight}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                            <td style={td}>
                              <div style={{ fontWeight: 600 }}>{f.full_name || f.customer_id}</div>
                              <div style={{ fontSize: 11, color: C.mgray }}>{f.customer_id}</div>
                            </td>
                            <td style={{ ...td, fontFamily: 'monospace', fontSize: 12 }}>
                              {f.account_number}
                            </td>
                            <td style={{ ...td, fontSize: 12, color: C.brownMid }}>
                              {f.frozen_at ? new Date(f.frozen_at).toLocaleString('en-IN') : '—'}
                            </td>
                            <td style={{ ...td, fontSize: 12, color: C.gold }}>
                              {f.frozen_reason || '—'}
                            </td>
                            <td style={{ ...td, fontFamily: 'monospace', fontSize: 12, color: C.brownMid }}>
                              #{f.frozen_by_alert_id || '—'}
                            </td>
                            <td style={td}>
                              <div style={{ display: 'flex', gap: 6 }}>
                                <button onClick={() => handleBlockPDF(f.customer_id)} style={{
                                  background: `${C.brownMid}22`, color: C.brownMid,
                                  border: `1px solid ${C.brownMid}44`,
                                  borderRadius: 6, padding: '5px 10px',
                                  cursor: 'pointer', fontSize: 12, fontWeight: 700,
                                }} title="Export Block Report PDF">📄 PDF</button>
                                <button
                                  onClick={() => handleUnfreeze(f.customer_id)}
                                  disabled={unfreezing === f.customer_id}
                                  style={{
                                    background: `${C.green}22`, color: C.green,
                                    border: `1px solid ${C.green}44`,
                                    borderRadius: 8, padding: '7px 16px',
                                    cursor: 'pointer', fontSize: 13, fontWeight: 700,
                                    opacity: unfreezing === f.customer_id ? 0.5 : 1,
                                  }}>
                                  {unfreezing === f.customer_id ? 'Unfreezing…' : '🔓 Unfreeze'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* ── TAB: FRAUD CASES ──────────────────────────────────────── */}
            {tab === 'cases' && (
              <div style={{ background: C.white, borderRadius: 12, overflow: 'hidden', border: `1px solid ${C.cream}`, boxShadow: '0 2px 8px rgba(127,85,57,0.08)' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      {['Case ID','Alert ID','Customer','Priority','Status','Created'].map(h => (
                        <th key={h} style={th}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {cases.length === 0 ? (
                      <tr><td colSpan={6} style={{ ...td, textAlign: 'center', color: C.brownMid, padding: 40 }}>
                        No open fraud cases.
                      </td></tr>
                    ) : cases.map(c => (
                      <tr key={c.case_id}
                        onMouseEnter={e => e.currentTarget.style.background = C.creamLight}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                        <td style={{ ...td, fontFamily: 'monospace', fontSize: 12, color: C.purple }}>
                          {c.case_id}
                        </td>
                        <td style={{ ...td, fontFamily: 'monospace', fontSize: 12, color: C.brownMid }}>
                          #{c.alert_id}
                        </td>
                        <td style={td}>
                          <div style={{ fontWeight: 600 }}>{c.customer_name || c.customer_id}</div>
                          <div style={{ fontSize: 11, color: C.mgray }}>{c.customer_id}</div>
                        </td>
                        <td style={td}>
                          <span style={{
                            color: c.priority === 'P1' ? C.red : C.gold,
                            fontWeight: 800, fontSize: 13,
                            fontFamily: 'monospace',
                          }}>{c.priority}</span>
                        </td>
                        <td style={td}>
                          <span style={{
                            background: `${C.green}22`, color: C.green,
                            borderRadius: 6, padding: '3px 10px', fontSize: 12, fontWeight: 700,
                          }}>{c.status}</span>
                        </td>
                        <td style={{ ...td, fontSize: 12, color: C.brownMid }}>
                          {c.created_at ? new Date(c.created_at).toLocaleString('en-IN') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      {/* ── Detail Modal ─────────────────────────────────────────────────────── */}
      {selected && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(127,85,57,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, padding: 24,
        }} onClick={() => setSelected(null)}>
          <div style={{
            background: C.white, borderRadius: 16, maxWidth: 680, width: '100%',
            border: `1px solid ${C.cream}`, maxHeight: '90vh', overflowY: 'auto',
            padding: 32, boxShadow: '0 16px 48px rgba(127,85,57,0.25)',
          }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <div style={{ color: C.brownDark, fontWeight: 800, fontSize: 20 }}>
                  Alert #{selected.alert_id}
                </div>
                <div style={{ color: C.brownMid, fontSize: 13, marginTop: 3 }}>
                  {selected.payment_id}
                </div>
              </div>
              {pill(selected.tma_decision)}
            </div>

            {[
              ['Customer', `${selected.customer_name || '—'} (${selected.customer_id})`],
              ['Account', selected.account_number || '—'],
              ['Amount', `₹${parseFloat(selected.amount || 0).toLocaleString('en-IN')}`],
              ['TMA Score', selected.tma_score],
              ['PRA Verdict', selected.pra_verdict || '—'],
              ['RAA Verdict', selected.raa_verdict || '—'],
              ['RAA Score', selected.final_raa_score != null ? `${parseFloat(selected.final_raa_score).toFixed(2)}/100` : '—'],
              ['Customer Tier', selected.customer_tier || '—'],
              ['Typology', selected.typology_code || '—'],
              ['STR Required', selected.str_required ? '✅ YES' : 'No'],
              ['CTR Flag', selected.ctr_flag ? '✅ YES' : 'No'],
              ['Account Frozen', selected.is_frozen ? '🔒 YES' : 'No'],
              ['Case ID', selected.aba_case_id || '—'],
              ['Gateway Action', selected.aba_gateway_action || '—'],
              ['Created', selected.created_at ? new Date(selected.created_at).toLocaleString('en-IN') : '—'],
            ].map(([k, v]) => (
              <div key={k} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '9px 0', borderBottom: `1px solid ${C.cream}`,
              }}>
                <span style={{ color: C.brownMid, fontSize: 13 }}>{k}</span>
                <span style={{ color: C.brownDark, fontSize: 13, fontWeight: 600, textAlign: 'right', maxWidth: '60%' }}>{String(v)}</span>
              </div>
            ))}

            {selected.investigation_note && (
              <div style={{ marginTop: 16 }}>
                <div style={{ color: C.brownMid, fontSize: 12, fontWeight: 700, marginBottom: 6, letterSpacing: 1 }}>
                  INVESTIGATION NOTE
                </div>
                <div style={{
                  background: C.creamLight, borderRadius: 8, padding: 14,
                  color: C.brownDark, fontSize: 13, lineHeight: 1.7,
                }}>{selected.investigation_note}</div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 12, marginTop: 24 }}>
              <button onClick={() => handleAlertPDF(selected.alert_id)} style={{
                flex: 1, background: `${C.brownMid}22`, color: C.brownMid,
                border: `1px solid ${C.brownMid}44`, borderRadius: 10,
                padding: '11px 0', cursor: 'pointer', fontWeight: 700, fontSize: 14,
              }}>📄 Export PDF</button>
              {selected.is_frozen && (
                <button onClick={() => { handleUnfreeze(selected.customer_id); setSelected(null); }} style={{
                  flex: 1, background: `${C.green}22`, color: C.green,
                  border: `1px solid ${C.green}44`, borderRadius: 10,
                  padding: '11px 0', cursor: 'pointer', fontWeight: 700, fontSize: 14,
                }}>🔓 Unfreeze Account</button>
              )}
              <button onClick={() => setSelected(null)} style={{
                flex: 1, background: C.cream, color: C.brownDark,
                border: 'none', borderRadius: 10, padding: '11px 0',
                cursor: 'pointer', fontSize: 14,
              }}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}