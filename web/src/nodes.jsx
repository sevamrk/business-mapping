import React from 'react';
import { Handle, Position } from '@xyflow/react';
import { CURRENT_STATES, PATTERNS, SEVERITY } from './vocab.js';

const hideH = { opacity: 0, width: 1, height: 1, minWidth: 0, border: 0 };
const KICKER = { company: 'Company', area: 'Area', lens: 'Lens', unlock: 'Unlock', finding: 'Finding' };
const ACCENT = { company: '#7da2c0', area: '#5f9ec9', unlocks: '#ffce6a', findings: '#ff9a6a' };
export const sentence = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const fmt = (n) => Math.round(n).toLocaleString('en-GB');

const Handles = () => (
  <>
    <Handle type="target" position={Position.Left} style={hideH} />
    <Handle type="source" position={Position.Right} style={hideH} />
  </>
);

// The current tier's own node, drawn in the centre as "you are here".
export function TierHubNode({ data }) {
  const c = ACCENT[data.kind] || ACCENT.area;
  return (
    <div className="tierhub-node" style={{ '--hc': c }}>
      <Handles />
      <div className="th-kicker">{KICKER[data.nodeType] || ''}</div>
      <div className="th-name">{data.label}</div>
    </div>
  );
}

export function AreaNode({ data }) {
  const empty = !data.drillable;
  return (
    <div className={'area-node' + (empty ? ' empty' : '')} style={{ '--hc': ACCENT.area }}>
      <Handles />
      <div className="dn-name">{sentence(data.label)}</div>
      <div className="dn-meta">
        <span className="dn-hc">{fmt(data.hours)} h/yr</span>
        {empty ? <span className="dn-none">all filtered</span> : <span className="dn-count">{data.childCount} ⤵</span>}
      </div>
    </div>
  );
}

export function FunctionNode({ data, selected }) {
  const p = PATTERNS[data.pattern] || {};
  const st = CURRENT_STATES[data.fn.current_state] || {};
  const worst = data.findings[0];
  return (
    <div className={'fn-node' + (selected ? ' sel' : '')} style={{ '--mc': p.color, '--sc': st.color }}>
      <Handle type="target" position={Position.Left} style={hideH} />
      <div className="fn-name">{data.label}</div>
      <div className="fn-meta">
        <span className="fn-pat"><span className="fn-led" />{p.label}</span>
        <span className="fn-st">{st.label}</span>
      </div>
      <div className="fn-hours">{fmt(data.verdict.hours_per_year)} h/yr · {fmt(data.verdict.recoverable_hours)} recoverable</div>
      {worst ? (
        <div className="fn-flag" style={{ '--fc': SEVERITY[worst.severity] }}>
          ⚑ {data.findings.length} finding{data.findings.length > 1 ? 's' : ''}
        </div>
      ) : null}
      <Handle type="source" position={Position.Right} style={hideH} />
    </div>
  );
}

// Root-tier entry into a cross-cutting view: Unlocks or Findings.
export function LensNode({ data }) {
  const c = ACCENT[data.kind];
  return (
    <div className="hub-node lens-node" style={{ '--hc': c }}>
      <Handles />
      <div className="hub-name">{data.label}</div>
      <div className="hub-sub">{data.kind === 'unlocks' ? 'what blocks the most hours' : `${data.count} things to look at`}</div>
    </div>
  );
}

export function UnlockNode({ data }) {
  const p = PATTERNS[data.pattern] || {};
  return (
    <div className="unlock-node" style={{ '--hc': p.color }}>
      <Handles />
      <div className="dn-name">{data.label}</div>
      <div className="dn-meta">
        <span className="dn-hc">{data.count} fn</span>
        <span className="dn-count">{fmt(data.hours)} h/yr</span>
      </div>
    </div>
  );
}

export function FindingNode({ data }) {
  return (
    <div className="unlock-node" style={{ '--hc': SEVERITY[data.severity] }}>
      <Handles />
      <div className="dn-name">{data.label}</div>
      <div className="dn-meta">
        <span className="dn-hc">{data.severity}</span>
        <span className="dn-count">{data.items.length}</span>
      </div>
    </div>
  );
}

export const nodeTypes = {
  tierhub: TierHubNode,
  area: AreaNode,
  function: FunctionNode,
  lens: LensNode,
  unlock: UnlockNode,
  finding: FindingNode,
};
