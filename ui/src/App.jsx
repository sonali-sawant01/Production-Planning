import React, { useState, useEffect, useRef } from 'react';
import { marked } from 'marked';
import './App.css';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SESSION_ID = 'planner-session-1';

// Pre-defined test questions
const QUICK_QUESTIONS = [
  "Which production orders are at risk this week?",
  "Why is order 100045 at risk?",
  "What should I do?",
  "What if PO 4500012345 arrives two days earlier?",
  "Release order 100045 now.",
];

function RiskBadge({ rating }) {
  const cfg = {
    HIGH:   { bg: '#fce8e8', color: '#bb0000', emoji: '🔴' },
    MEDIUM: { bg: '#fef3e2', color: '#e76500', emoji: '🟡' },
    LOW:    { bg: '#e8f5e9', color: '#256f3a', emoji: '🟢' },
  };
  const c = cfg[rating] || { bg: '#f0f0f0', color: '#555', emoji: '⚪' };
  return (
    <span style={{
      background: c.bg, color: c.color,
      padding: '2px 10px', borderRadius: 20,
      fontWeight: 700, fontSize: 12,
      border: `1px solid ${c.color}30`,
    }}>
      {c.emoji} {rating}
    </span>
  );
}

function CapacityBadge({ classification }) {
  const cfg = {
    CRITICAL: { bg: '#fce8e8', color: '#bb0000' },
    HIGH:     { bg: '#fef3e2', color: '#e76500' },
    WATCH:    { bg: '#fff8e1', color: '#d47e00' },
    NORMAL:   { bg: '#e8f5e9', color: '#256f3a' },
  };
  const c = cfg[classification] || { bg: '#f0f0f0', color: '#555' };
  return (
    <span style={{
      background: c.bg, color: c.color,
      padding: '2px 10px', borderRadius: 20,
      fontWeight: 700, fontSize: 12,
      border: `1px solid ${c.color}30`,
    }}>
      {classification}
    </span>
  );
}

function ScenarioPanel({ scenario }) {
  if (!scenario) return null;
  const { demand_context, production_orders, work_centers, mrp_exceptions } = scenario;

  return (
    <div className="scenario-panel">
      <div className="scenario-header">
        <span className="scenario-title">📋 Monday Morning Disruption Scenario</span>
        <span className="simulated-badge">🧪 SIMULATED DATA</span>
      </div>
      <div className="scenario-stats">
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#e76500' }}>+{demand_context?.demand_increase_pct}%</div>
          <div className="stat-label">Customer Demand Spike</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#bb0000' }}>{mrp_exceptions?.length || 0}</div>
          <div className="stat-label">MRP Exceptions</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#bb0000' }}>
            {production_orders?.filter(o => [1].includes(o.priority)).length || 0}
          </div>
          <div className="stat-label">Priority 1 Orders</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{production_orders?.length || 0}</div>
          <div className="stat-label">Total Orders</div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="table-title">Production Orders</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Material</th>
              <th>Qty</th>
              <th>Start</th>
              <th>Finish</th>
              <th>Work Center</th>
              <th>Priority</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {production_orders?.map(o => (
              <tr key={o.order}>
                <td><strong>{o.order}</strong></td>
                <td>{o.material}</td>
                <td>{o.qty} {o.unit}</td>
                <td>{o.start_date}</td>
                <td>{o.finish_date}</td>
                <td>{o.work_center}</td>
                <td>
                  <span style={{
                    background: o.priority === 1 ? '#fce8e8' : o.priority === 2 ? '#fef3e2' : '#f0f0f0',
                    color: o.priority === 1 ? '#bb0000' : o.priority === 2 ? '#e76500' : '#555',
                    padding: '1px 8px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                  }}>
                    P{o.priority}
                  </span>
                </td>
                <td>
                  <span style={{
                    background: o.status === 'RELEASED' ? '#e3f0ff' : '#f5f5f5',
                    color: o.status === 'RELEASED' ? '#0057c8' : '#555',
                    padding: '1px 8px', borderRadius: 12, fontSize: 12,
                  }}>
                    {o.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 16 }}>
        <div className="table-title">MRP Exceptions</div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Material</th>
              <th>Exception</th>
              <th>Req Date</th>
              <th>Required</th>
              <th>Available</th>
              <th>Shortage</th>
            </tr>
          </thead>
          <tbody>
            {mrp_exceptions?.map((ex, i) => (
              <tr key={i}>
                <td><strong>{ex.material}</strong></td>
                <td>{ex.exception_text}</td>
                <td>{ex.requirement_date}</td>
                <td>{ex.requirement_qty} {ex.unit}</td>
                <td>{ex.available_qty} {ex.unit}</td>
                <td style={{ color: '#bb0000', fontWeight: 700 }}>{ex.shortage_qty} {ex.unit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {work_centers && (
        <div style={{ marginTop: 16 }}>
          <div className="table-title">Work Center Capacity</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Work Center</th>
                <th>Available (hr)</th>
                <th>Required (hr)</th>
                <th>Utilization</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {work_centers.map(wc => {
                const pct = wc.available_hours > 0
                  ? ((wc.required_hours / wc.available_hours) * 100).toFixed(1)
                  : '—';
                const cls = pct >= 110 ? 'CRITICAL' : pct >= 100 ? 'HIGH' : pct >= 90 ? 'WATCH' : 'NORMAL';
                return (
                  <tr key={wc.work_center}>
                    <td><strong>{wc.work_center}</strong></td>
                    <td>{wc.available_hours}</td>
                    <td>{wc.required_hours}</td>
                    <td style={{ fontWeight: 700 }}>{pct}%</td>
                    <td><CapacityBadge classification={cls} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  const html = !isUser ? marked.parse(msg.content || '') : null;

  return (
    <div className={`message-row ${isUser ? 'user-row' : 'agent-row'}`}>
      {!isUser && (
        <div className="agent-avatar">🤖</div>
      )}
      <div className={`message-bubble ${isUser ? 'user-bubble' : 'agent-bubble'}`}>
        {isUser
          ? <span>{msg.content}</span>
          : <div
              className="agent-content"
              dangerouslySetInnerHTML={{ __html: html }}
            />
        }
        {msg.loading && (
          <div className="typing-indicator">
            <span /><span /><span />
          </div>
        )}
      </div>
      {isUser && (
        <div className="user-avatar">👤</div>
      )}
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([
    {
      role: 'agent',
      content: `# 👋 Welcome to the Production Planning Risk Agent

I'm your AI assistant for analyzing production order risk. I'm working with **simulated SAP-like data** (prototype — no real SAP system connected).

**Today's scenario:** Monday morning disruption — customer demand is up **+20%**. Here's what I know:
- 🔴 **RM-101** shortage: 780 EA available vs. 1,000 EA required (shortage: **220 EA**)
- 🔴 **WC-100** at **118% utilization** (CRITICAL) — 40 hr available vs. 47.2 hr required
- ⚠️ **PO 4500012345** (RM-101) is due **after** order 100045's start date

Try asking me one of the questions on the right, or type your own. I'll retrieve the facts first, then give you my analysis.`,
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [scenario, setScenario] = useState(null);
  const [showScenario, setShowScenario] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    fetch(`${API_BASE}/scenario`)
      .then(r => r.json())
      .then(setScenario)
      .catch(() => {});
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text) => {
    if (!text.trim() || loading) return;
    const userMsg = { role: 'user', content: text };
    const loadingMsg = { role: 'agent', content: '', loading: true };
    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: SESSION_ID }),
      });
      const data = await res.json();
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'agent', content: data.reply || 'No response received.' },
      ]);
    } catch (err) {
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'agent', content: `❌ **Error:** Could not reach the agent backend. Make sure the server is running.\n\n\`${err.message}\`` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    await fetch(`${API_BASE}/reset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: SESSION_ID }),
    }).catch(() => {});
    setMessages([{
      role: 'agent',
      content: '🔄 Conversation reset. How can I help you with production planning today?',
    }]);
  };

  return (
    <div className="app-layout">
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="header-logo">⚙️</div>
          <div>
            <div className="header-title">Production Planning Risk Agent</div>
            <div className="header-subtitle">SAP PP Planner Assistant · <span className="simulated-tag">SIMULATED DATA</span></div>
          </div>
        </div>
        <div className="header-actions">
          <button className="btn-secondary" onClick={() => setShowScenario(v => !v)}>
            {showScenario ? '📊 Hide Data' : '📊 Show Scenario Data'}
          </button>
          <button className="btn-secondary" onClick={handleReset}>
            🔄 New Session
          </button>
        </div>
      </header>

      {/* Scenario panel (expandable) */}
      {showScenario && <ScenarioPanel scenario={scenario} />}

      {/* Main layout */}
      <div className="main-layout">
        {/* Chat area */}
        <div className="chat-area">
          <div className="messages-list">
            {messages.map((msg, i) => (
              <MessageBubble key={i} msg={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="input-area">
            <input
              className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
              placeholder="Ask about production order risk, capacity, materials…"
              disabled={loading}
            />
            <button
              className="btn-primary"
              onClick={() => sendMessage(input)}
              disabled={loading || !input.trim()}
            >
              {loading ? '⏳' : '➤ Send'}
            </button>
          </div>
        </div>

        {/* Sidebar: quick questions */}
        <aside className="sidebar">
          <div className="sidebar-title">💡 Test Questions</div>
          <div className="quick-questions">
            {QUICK_QUESTIONS.map((q, i) => (
              <button
                key={i}
                className="quick-btn"
                onClick={() => sendMessage(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>

          <div className="sidebar-title" style={{ marginTop: 24 }}>🔐 Guardrails Active</div>
          <div className="guardrail-list">
            {[
              'Read-only: no SAP transactions executed',
              'Facts retrieved before every answer',
              'Recommendations separated from facts',
              'Manager approval flagged for cost/impact items',
              'HIGH-priority orders never de-prioritized silently',
              'Missing data reported, never estimated',
              'Confidence & data basis stated for all recommendations',
            ].map((g, i) => (
              <div key={i} className="guardrail-item">✅ {g}</div>
            ))}
          </div>

          <div className="sidebar-title" style={{ marginTop: 24 }}>📐 Capacity Thresholds</div>
          <div className="threshold-list">
            {[
              { label: 'NORMAL', range: '< 90%', color: '#256f3a' },
              { label: 'WATCH',  range: '90–100%', color: '#d47e00' },
              { label: 'HIGH',   range: '100–110%', color: '#e76500' },
              { label: 'CRITICAL', range: '> 110%', color: '#bb0000' },
            ].map(t => (
              <div key={t.label} className="threshold-item">
                <span style={{
                  background: `${t.color}18`, color: t.color,
                  padding: '1px 8px', borderRadius: 10, fontWeight: 700, fontSize: 11,
                }}>
                  {t.label}
                </span>
                <span style={{ color: '#556b82', fontSize: 12, marginLeft: 8 }}>{t.range}</span>
              </div>
            ))}
          </div>
          <div style={{ color: '#888', fontSize: 11, marginTop: 6 }}>
            ⚠️ Prototype thresholds — not SAP standard
          </div>
        </aside>
      </div>

      {/* Footer */}
      <footer className="app-footer">
        🧪 All data is <strong>SIMULATED</strong> for prototype purposes only. No real SAP system is connected. · 
        Agent is read-only — no orders or POs are modified.
      </footer>
    </div>
  );
}
