import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, MarkerType,
  useReactFlow, applyNodeChanges,
} from '@xyflow/react';
import { forceSimulation, forceManyBody, forceLink, forceCollide, forceX, forceY } from 'd3-force';
import { nodeTypes } from './nodes.jsx';
import { MODEL } from './data.js';
import { ROOT_ID, UNLOCKS_ID, FINDINGS_ID, areaNodeId, functionNodeId, patternFilter } from './model.js';
import {
  CAPABILITY_FACTS, CURRENT_STATES, GAP_CODES, PATTERNS, PATTERN_ORDER, RISK_BANDS, SEVERITY,
} from './vocab.js';

// ELK is most of the bundle and only the Tree view needs it, so it loads on first use.
let elkPromise = null;
const getElk = () => {
  if (!elkPromise) {
    elkPromise = import('elkjs/lib/elk.bundled.js')
      .then((m) => new m.default())
      .catch((err) => { elkPromise = null; throw err; }); // let a later click retry
  }
  return elkPromise;
};

const SIZE = {
  tierhub: { w: 172, h: 172 }, area: { w: 188, h: 70 }, function: { w: 212, h: 104 },
  lens: { w: 150, h: 150 }, unlock: { w: 188, h: 74 }, finding: { w: 188, h: 70 },
};

const fmt = (n) => Math.round(n).toLocaleString('en-GB');
const factLabel = (f) => f.replace(/_/g, ' ');

// deterministic 0..1 from a string, so a tier looks the same every time you come back to it
const hash01 = (s) => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967295;
};

const miniColor = (n) => {
  if (n.type === 'function') return PATTERNS[n.data.pattern]?.color || '#888';
  if (n.type === 'unlock') return PATTERNS[n.data.pattern]?.color || '#ffce6a';
  if (n.type === 'finding') return SEVERITY[n.data.severity] || '#ff9a6a';
  if (n.type === 'lens') return n.data.kind === 'unlocks' ? '#ffce6a' : '#ff9a6a';
  return '#5f9ec9';
};

async function elkLayout(nodes, edges) {
  const g = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered', 'elk.direction': 'RIGHT',
      'elk.layered.spacing.nodeNodeBetweenLayers': '120', 'elk.spacing.nodeNode': '28',
      'elk.layered.nodePlacement.strategy': 'NETWORK_SIMPLEX',
    },
    children: nodes.map((n) => ({ id: n.id, width: SIZE[n.type]?.w || 150, height: SIZE[n.type]?.h || 80 })),
    edges: edges.map((e) => ({ id: e.id, sources: [e.source], targets: [e.target] })),
  };
  const elk = await getElk();
  const r = await elk.layout(g);
  const pos = {};
  for (const c of r.children) pos[c.id] = { x: c.x, y: c.y };
  return nodes.map((n) => ({ ...n, position: pos[n.id] || { x: 0, y: 0 } }));
}

function FnButton({ id, onNav, note }) {
  const n = MODEL.getNode(id);
  if (!n) return null;
  const p = PATTERNS[n.data.pattern] || {};
  return (
    <button className="unlock-item" onClick={() => onNav(id)}>
      <span className="ui-p" style={{ '--c': p.color }}>{fmt(n.data.verdict.hours_per_year)}h</span>
      <span className="ui-t">{n.label}</span>
      {note ? <span className="ui-co">{note}</span> : null}
    </button>
  );
}

function ArtifactRow({ id, dir, onNav }) {
  const a = MODEL.artifact(id);
  const others = dir === 'in' ? a.producers : a.consumers;
  return (
    <div className="art-row">
      <div className="art-name">{a.name} <span className="art-form">{a.form?.replace(/_/g, ' ')}</span></div>
      {others.length ? (
        others.map((fid) => (
          <button key={fid} className="art-link" onClick={() => onNav(fid)}>
            {dir === 'in' ? '← from ' : '→ into '}{MODEL.getNode(fid)?.label}
          </button>
        ))
      ) : (
        <div className="art-none">{a.boundary === 'internal' ? (dir === 'in' ? 'nothing in the map produces it' : 'nothing reads it') : `${a.boundary}, outside the map`}</div>
      )}
    </div>
  );
}

function DetailPanel({ node, onClose, onNav, visChildren }) {
  if (!node) return null;
  const { type, data, label } = node;
  const kids = visChildren(node.id);
  const hidden = MODEL.getChildren(node.id).length - kids.length;
  const openMap = () => { onNav(node.id); onClose(); };

  return (
    <aside className="detail">
      <button className="x" onClick={onClose} aria-label="close">✕</button>

      {type === 'company' && (() => {
        const s = data.summary;
        const areas = Object.entries(data.byArea);
        const mx = Math.max(...areas.map(([, a]) => a.hours)) || 1;
        return (
          <>
            <div className="d-co">Company · invented example</div>
            <h2>{label}</h2>
            <p className="d-det" style={{ borderTop: 'none', paddingTop: 0, marginBottom: 16 }}>{data.description}</p>
            <div className="dp-kpis">
              <div className="dp-kpi"><div className="dp-kpi-v">{fmt(s.hours)}</div><div className="dp-kpi-l">hours a year mapped</div></div>
              <div className="dp-kpi"><div className="dp-kpi-v">{fmt(s.automated)}</div><div className="dp-kpi-l">already automated</div></div>
              <div className="dp-kpi"><div className="dp-kpi-v">{fmt(s.recoverable)}</div><div className="dp-kpi-l">recoverable</div></div>
              <div className="dp-kpi"><div className="dp-kpi-v">{s.recoverableFte}</div><div className="dp-kpi-l">FTE at {fmt(s.hoursPerFte)} h</div></div>
            </div>
            <div className="d-sect">
              <div className="d-sect-h">Hours a year by area · lighter part is recoverable</div>
              <div className="area-bars">
                {areas.map(([name, a]) => (
                  <button className="area-bar" key={name} onClick={() => onNav(areaNodeId(name))}>
                    <span className="ab-l">{name}</span>
                    <span className="ab-track">
                      <span className="ab-fill" style={{ width: `${(a.hours / mx) * 100}%` }} />
                      <span className="ab-rec" style={{ width: `${(a.recoverable / mx) * 100}%` }} />
                    </span>
                    <span className="ab-v">{fmt(a.hours)}</span>
                  </button>
                ))}
              </div>
            </div>
            <p className="d-econ">Every hour here is volume a month times minutes a run, typed in by whoever wrote the map. The order is worth more than the totals.</p>
            <button className="d-act" onClick={openMap}>Open {s.areas} areas →</button>
          </>
        );
      })()}

      {type === 'area' && (
        <>
          <div className="d-co">Area</div>
          <h2>{label}</h2>
          <div className="dp-kpis">
            <div className="dp-kpi"><div className="dp-kpi-v">{data.functions}</div><div className="dp-kpi-l">functions</div></div>
            <div className="dp-kpi"><div className="dp-kpi-v">{fmt(data.hours)}</div><div className="dp-kpi-l">hours a year</div></div>
            <div className="dp-kpi"><div className="dp-kpi-v">{fmt(data.recoverable)}</div><div className="dp-kpi-l">recoverable</div></div>
            <div className={'dp-kpi' + (data.unowned ? ' warn' : '')}><div className="dp-kpi-v">{data.unowned}</div><div className="dp-kpi-l">with no owner</div></div>
          </div>
          <div className="d-sect">
            <div className="d-sect-h">Verdicts</div>
            <div className="chips">
              {PATTERN_ORDER.filter((p) => data.byPattern[p]).map((p) => (
                <span key={p} className="pill static" style={{ '--c': PATTERNS[p].color }}><span className="pd" />{PATTERNS[p].label} · {data.byPattern[p]}</span>
              ))}
            </div>
          </div>
          {data.owners.length > 0 && (
            <div className="d-sect">
              <div className="d-sect-h">Owners</div>
              <div className="dp-subs">{data.owners.map((o) => <span className="sub" key={o}>{o}</span>)}</div>
            </div>
          )}
          {kids.length > 0
            ? <button className="d-act" onClick={openMap}>Open {kids.length} functions →</button>
            : <div className="dp-empty">{hidden} function{hidden === 1 ? '' : 's'} hidden by the pattern filter.</div>}
        </>
      )}

      {type === 'function' && (() => {
        const { fn, verdict: v } = data;
        const p = PATTERNS[v.pattern] || {};
        const st = CURRENT_STATES[fn.current_state] || {};
        return (
          <>
            <div className="d-co">{fn.area} · function</div>
            <h2>{label}</h2>
            <div className="d-chips">
              <span className="chip" style={{ '--c': p.color }}><span className="cd" />{p.label}</span>
              <span className="chip" style={{ '--c': st.color }}><span className="cd" />{st.label}</span>
              <span className="chip" style={{ '--c': RISK_BANDS[v.risk_band] }}><span className="cd" />{v.risk_band} risk</span>
            </div>
            <p className="d-det" style={{ borderTop: 'none', paddingTop: 0, marginBottom: 14 }}>{fn.description}</p>
            {data.findings.length > 0 && (
              <div className="d-live">
                <div className="d-live-h">⚑ Findings from main.py gaps</div>
                {data.findings.map((f) => <div key={f.index} className="d-live-i" style={{ '--fc': SEVERITY[f.severity] }}>{f.message}</div>)}
              </div>
            )}
            <div className="d-kv">
              <div className="k">Owner</div><div>{data.ownerName || <span className="warn-t">nobody</span>}</div>
              <div className="k">Done by</div><div>{data.performerNames.join(', ') || <span className="warn-t">nobody listed</span>}</div>
              <div className="k">Trigger</div><div>{fn.trigger}</div>
              <div className="k">Volume</div><div>{fn.volume_per_month} a month × {fn.minutes_per_run} min</div>
              <div className="k">Hours</div><div>{fmt(v.hours_per_year)} a year · {fmt(v.recoverable_hours)} recoverable</div>
            </div>
            <div className="d-sect">
              <div className="d-sect-h">Readiness {v.readiness.toFixed(2)} · held back by {factLabel(v.limiting_fact)}</div>
              <div className="axes">
                {CAPABILITY_FACTS.map((f) => (
                  <div key={f} className={'axis' + (f === v.limiting_fact ? ' lim' : '')}>
                    <span className="ax-l">{factLabel(f)}</span>
                    <span className="ax-track"><span className="ax-fill" style={{ width: `${(v.axis_scores[f] ?? 0) * 100}%` }} /></span>
                    <span className="ax-v">{fn.automation[f].replace(/_/g, ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="d-sect d-gaps ok">
              <div className="d-sect-h">Why {p.label}</div>
              <ul><li>{v.reason}</li></ul>
            </div>
            <div className="d-act static">Next → {v.next_step}</div>
            <div className="d-sect" style={{ marginTop: 18 }}>
              <div className="d-sect-h">Needs</div>
              {fn.inputs.map((a) => <ArtifactRow key={a} id={a} dir="in" onNav={onNav} />)}
            </div>
            <div className="d-sect">
              <div className="d-sect-h">Makes</div>
              {fn.outputs.map((a) => <ArtifactRow key={a} id={a} dir="out" onNav={onNav} />)}
            </div>
            {fn.notes && <p className="d-econ">{fn.notes}</p>}
          </>
        );
      })()}

      {type === 'lens' && data.kind === 'unlocks' && (
        <>
          <div className="d-co">Lens</div>
          <h2>Unlocks</h2>
          <p className="d-det" style={{ borderTop: 'none', paddingTop: 0 }}>
            Every function the tool did not call agent-led or keep-human has one specific thing in the way. Grouped by that thing, most hours behind it first. Clearing the top one moves the most work at once.
          </p>
          {kids.length > 0 && <button className="d-act" onClick={openMap}>Open {kids.length} blockers →</button>}
        </>
      )}

      {type === 'lens' && data.kind === 'findings' && (
        <>
          <div className="d-co">Lens</div>
          <h2>Findings</h2>
          <p className="d-det" style={{ borderTop: 'none', paddingTop: 0 }}>
            What <code>main.py gaps</code> reports: things that are legal to write in a map and worth somebody's attention. {data.count} of them, grouped by kind.
          </p>
          {kids.length > 0 && <button className="d-act" onClick={openMap}>Open {kids.length} kinds →</button>}
        </>
      )}

      {type === 'unlock' && (
        <>
          <div className="d-co">Unlock · {data.count} functions · {fmt(data.hours)} h/yr</div>
          <h2>{data.nextStep}</h2>
          <div className="d-chips">
            <span className="chip" style={{ '--c': PATTERNS[data.pattern]?.color }}><span className="cd" />{PATTERNS[data.pattern]?.label}</span>
          </div>
          <p className="d-det" style={{ borderTop: 'none', paddingTop: 0 }}>Because {data.reason}. {fmt(data.recoverable)} of these hours are recoverable as the facts stand today.</p>
          <div className="unlock-list">{data.fnIds.map((id) => <FnButton key={id} id={functionNodeId(id)} onNav={onNav} />)}</div>
        </>
      )}

      {type === 'finding' && (
        <>
          <div className="d-co">Finding · {data.severity}</div>
          <h2>{GAP_CODES[data.code] || label}</h2>
          <div className="d-sect">
            {data.items.map((f) => (
              <div className="finding" key={f.index}>
                <div className="f-msg">{f.message}</div>
                <div className="unlock-list">{f.targets.map((t) => <FnButton key={t} id={functionNodeId(t)} onNav={onNav} />)}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}

const ALL_PATTERNS_ON = Object.fromEntries(PATTERN_ORDER.map((p) => [p, true]));

function Canvas() {
  const rf = useReactFlow();
  const [path, setPath] = useState([ROOT_ID]);
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [layout, setLayout] = useState('live'); // 'live' (d3-force) | 'tree' (ELK)
  const [hover, setHover] = useState(null);
  const [patOn, setPatOn] = useState(ALL_PATTERNS_ON);

  const simRef = useRef(null);
  const simNodesRef = useRef([]);
  const histRef = useRef([]);
  const draggedRef = useRef(false);

  const rootId = path[path.length - 1];
  // a hover belongs to the tier it happened on
  const [hoverTier, setHoverTier] = useState(rootId);
  if (hoverTier !== rootId) { setHoverTier(rootId); setHover(null); }
  const isVisible = useMemo(() => patternFilter(patOn), [patOn]);
  const tier = useMemo(() => MODEL.buildTierGraph(rootId, isVisible), [rootId, isVisible]);

  useEffect(() => {
    const n = tier.nodes;
    const e = tier.edges;
    if (simRef.current) { simRef.current.stop(); simRef.current = null; }

    if (layout === 'tree') {
      let alive = true;
      let tId;
      elkLayout(n, e).then((laid) => {
        if (!alive) return;
        // edges land with the laid-out nodes, never before them
        setEdges(e);
        setNodes(laid);
        tId = setTimeout(() => rf.fitView({ padding: 0.2, duration: 420 }), 60);
      }).catch((err) => {
        // the chunk failed to load or ELK threw: say so and fall back rather than freeze
        console.error('tree layout failed, back to live', err);
        if (alive) setLayout('live');
      });
      return () => { alive = false; clearTimeout(tId); };
    }

    // live: the hub pinned at the origin, children seeded on a ring that depends only on their ids
    const kids = n.filter((x) => x.type !== 'tierhub');
    const cnt = kids.length || 1;
    const sims = n.map((nd) => {
      if (nd.type === 'tierhub') return { id: nd.id, type: nd.type, data: nd.data, x: 0, y: 0, fx: 0, fy: 0 };
      const i = kids.indexOf(nd);
      const ang = (i / cnt) * Math.PI * 2 + hash01(nd.id) * 0.7 - Math.PI / 2;
      const rad = 310 + hash01(nd.id + 'r') * 140;
      return { id: nd.id, type: nd.type, data: nd.data, x: Math.cos(ang) * rad, y: Math.sin(ang) * rad };
    });
    simNodesRef.current = sims;
    const links = e.map((ed) => ({ source: ed.source, target: ed.target, kind: ed.kind }));
    const toRF = () => sims.map((s) => ({ id: s.id, type: s.type, data: s.data, position: { x: s.x, y: s.y } }));
    // This effect drives an external simulation, and the new tier's edges have to land in
    // the same commit as its first node positions or React Flow draws edges to nodes that
    // are not there yet. Setting both here is the synchronisation, not a slip.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEdges(e);
    setNodes(toRF());

    const sim = forceSimulation(sims)
      .velocityDecay(0.5)
      .force('link', forceLink(links).id((d) => d.id)
        .distance((l) => (l.kind === 'flow' ? 260 : 320))
        .strength((l) => (l.kind === 'flow' ? 0.05 : 0.22)))
      .force('charge', forceManyBody().strength(-720).distanceMax(900))
      .force('collide', forceCollide().radius((d) => (SIZE[d.type]?.w || 150) * 0.62).strength(0.95).iterations(2))
      .force('x', forceX(0).strength(0.045))
      .force('y', forceY(0).strength(0.06))
      .alpha(1).alphaDecay(0.045);
    // move the existing node objects rather than rebuilding them: a rebuilt node loses the
    // size React Flow measured, and an unmeasured node is hidden until measured again
    const byId = new Map(sims.map((x) => [x.id, x]));
    sim.on('tick', () => setNodes((ns) => ns.map((nd) => {
      const x = byId.get(nd.id);
      return x ? { ...nd, position: { x: x.x, y: x.y } } : nd;
    })));
    // fit when the tier settles, unless the user has dragged something on it: a drag
    // restarts the simulation, and the camera must stay on what they just arranged
    draggedRef.current = false;
    sim.on('end', () => { if (!draggedRef.current) rf.fitView({ padding: 0.24, duration: 480 }); });
    simRef.current = sim;
    const ft = setTimeout(() => rf.fitView({ padding: 0.24, duration: 600 }), 500);
    return () => { sim.stop(); clearTimeout(ft); };
  }, [tier, layout, rf]);

  const onNodesChange = useCallback((ch) => setNodes((ns) => applyNodeChanges(ch, ns)), []);

  // dragging pins a node in the simulation; letting go releases it back to the forces
  const onNodeDrag = useCallback((_, node) => {
    if (layout !== 'live') return;
    const s = simNodesRef.current.find((x) => x.id === node.id);
    if (s) { s.fx = node.position.x; s.fy = node.position.y; }
    draggedRef.current = true;
    if (simRef.current) simRef.current.alphaTarget(0.2).restart();
  }, [layout]);
  const onNodeDragStop = useCallback((_, node) => {
    if (layout !== 'live') return;
    const s = simNodesRef.current.find((x) => x.id === node.id);
    if (s && s.type !== 'tierhub') { s.fx = null; s.fy = null; }
    if (simRef.current) simRef.current.alphaTarget(0);
  }, [layout]);

  const visChildren = useCallback((id) => MODEL.getChildren(id).filter(isVisible), [isVisible]);

  const remember = useCallback(() => {
    const top = histRef.current[histRef.current.length - 1];
    if (top && top.path.join() === path.join() && top.sel === (selected?.id || null)) return;
    histRef.current.push({ path, sel: selected?.id || null });
    if (histRef.current.length > 50) histRef.current.shift();
  }, [path, selected]);

  const goBack = useCallback(() => {
    const prev = histRef.current.pop();
    if (!prev) return;
    setPath(prev.path);
    setSelected(prev.sel ? MODEL.getNode(prev.sel) : null);
  }, []);

  // click: read it in the panel and, if it opens onto anything visible, drill in
  const onNodeClick = useCallback((_, node) => {
    remember();
    // the hub is the tier you are on: read it, there is nowhere further in to go
    if (node.type === 'tierhub') { setSelected(MODEL.getNode(node.id)); return; }
    setSelected(MODEL.getNode(node.id));
    if (visChildren(node.id).length > 0) setPath((p) => (p[p.length - 1] === node.id ? p : [...p, node.id]));
  }, [visChildren, remember]);

  // jump anywhere: switch the node's pattern back on if the filter hid it, stand on the tier that shows it, select it
  const navTo = useCallback((id) => {
    remember();
    const node = MODEL.getNode(id);
    if (node?.type === 'function') {
      const p = node.data.pattern;
      setPatOn((s) => (s[p] ? s : { ...s, [p]: true }));
    }
    setPath(MODEL.pathTo(id));
    setSelected(node);
  }, [remember]);

  const goCrumb = useCallback((i) => {
    remember();
    setPath((p) => p.slice(0, i + 1));
    setSelected(MODEL.getNode(path[i]));
  }, [path, remember]);

  const results = useMemo(() => (query.trim() ? MODEL.searchNodes(query, 8) : []), [query]);
  const jump = useCallback((id) => { navTo(id); setQuery(''); }, [navTo]);

  const stats = useMemo(() => {
    const fns = MODEL.allFunctions();
    return {
      total: fns.length,
      automated: fns.filter((n) => n.data.fn.current_state === 'automated').length,
      ready: fns.filter((n) => n.data.pattern === 'agent_led').length,
    };
  }, []);

  // Re-fit whenever the pane changes size: the detail panel opening or closing, or the
  // window resizing. Watching the size itself rather than the panel state, because a timer
  // after the state change fired while the pane was still at its old width.
  const wrapRef = useRef(null);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    let t;
    let last = el.clientWidth;
    const ro = new ResizeObserver(() => {
      if (el.clientWidth === last) return;
      last = el.clientWidth;
      clearTimeout(t);
      t = setTimeout(() => rf.fitView({ padding: 0.22, duration: 300 }), 80);
    });
    ro.observe(el);
    return () => { ro.disconnect(); clearTimeout(t); };
  }, [rf]);

  const styledNodes = useMemo(() => {
    let hot = null;
    // a node the filter just removed never fires mouseleave, so a hover on it is ignored
    if (hover && nodes.some((n) => n.id === hover)) {
      hot = new Set([hover, rootId]);
      for (const e of edges) {
        if (e.kind === 'flow' && (e.source === hover || e.target === hover)) { hot.add(e.source); hot.add(e.target); }
      }
    }
    return nodes.map((n) => ({
      ...n,
      className: hot ? (hot.has(n.id) ? 'rf-hot' : 'rf-dim') : undefined,
      selected: !!(selected && n.id === selected.id),
    }));
  }, [nodes, selected, hover, rootId, edges]);

  const styledEdges = useMemo(() => edges.map((e) => {
    const on = hover && (e.target === hover || e.source === hover);
    if (e.kind === 'flow') {
      return {
        ...e,
        animated: !!on,
        markerEnd: { type: MarkerType.ArrowClosed, color: on ? '#ffd28a' : '#7a6a48', width: 14, height: 14 },
        style: { stroke: on ? '#ffd28a' : '#7a6a48', strokeDasharray: '5 4', strokeOpacity: on ? 1 : 0.6, strokeWidth: on ? 2.2 : 1.3 },
      };
    }
    return { ...e, animated: !!on, style: { stroke: on ? '#dcebff' : '#2c4659', strokeOpacity: on ? 1 : 0.5, strokeWidth: on ? 2.4 : 1.4 } };
  }), [edges, hover]);

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">business<span>-mapping</span><small>process canvas</small></div>
        <div style={{ position: 'relative' }}>
          <input className="search" placeholder="Search functions, people, artifacts" value={query} onChange={(e) => setQuery(e.target.value)} />
          {results.length > 0 && (
            <div className="search-res">
              {results.map((r) => (
                <button key={r.id} className="sr" onClick={() => jump(r.id)}>
                  <span className={'sr-t sr-' + r.type}>{r.type}</span>
                  <span className="sr-l">{r.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="stat-row">
          <div><b>{stats.total}</b><span>functions</span></div>
          <div><b>{stats.automated}</b><span>automated</span></div>
          <div><b style={{ color: PATTERNS.agent_led.color }}>{stats.ready}</b><span>agent-led</span></div>
        </div>
        <div className="side-h">Verdict · click to filter</div>
        <div className="chips">
          {PATTERN_ORDER.map((k) => (
            <button key={k} className={'pill' + (patOn[k] ? '' : ' off')} style={{ '--c': PATTERNS[k].color }}
              onClick={() => setPatOn((s) => ({ ...s, [k]: !s[k] }))}><span className="pd" />{PATTERNS[k].label}</button>
          ))}
        </div>
        <div className="side-h">Done today</div>
        <div className="chips">
          {Object.entries(CURRENT_STATES).map(([k, s]) => (
            <span key={k} className="pill static" style={{ '--c': s.color }}><span className="pd" />{s.label}</span>
          ))}
        </div>
        <div className="side-h">Jump to</div>
        <div className="chips">
          <button className="pill" style={{ '--c': '#ffce6a' }} onClick={() => navTo(UNLOCKS_ID)}><span className="pd" />unlocks</button>
          <button className="pill" style={{ '--c': '#ff9a6a' }} onClick={() => navTo(FINDINGS_ID)}><span className="pd" />findings</button>
        </div>
        <div className="side-h">How to use</div>
        <div className="hint"><b>Click</b> a node to open it and read its detail. The <b>breadcrumb</b> climbs back up. <b>Drag</b> to reshape, <b>hover</b> to trace a link. Dashed arrows are artifacts one function hands another.</div>
        <div className="foot">Invented company. Verdicts are the Python tool&apos;s own output, read from a file, not recomputed here.</div>
      </aside>

      <div className={'canvas-wrap' + (selected ? ' panel-open' : '')}>
        <div className="focus-bar">
          <button className="crumb-back" onClick={goBack} title="back" aria-label="back">←</button>
          <nav className="bcrumbs">
            {path.map((id, i) => {
              const nn = MODEL.getNode(id);
              const last = i === path.length - 1;
              return (
                <React.Fragment key={id}>
                  <button className={'bcrumb' + (last ? ' cur' : '')} onClick={() => goCrumb(i)}>{nn?.label || id}</button>
                  {!last && <span className="bcrumb-sep">›</span>}
                </React.Fragment>
              );
            })}
          </nav>
          <span className="fb-sep" />
          <span>View</span>
          <button className={layout === 'live' ? 'on' : ''} onClick={() => setLayout('live')}>Live</button>
          <button className={layout === 'tree' ? 'on' : ''} onClick={() => setLayout('tree')}>Tree</button>
        </div>

        <div className="rf-pane" ref={wrapRef}>
        <ReactFlow
          nodes={styledNodes} edges={styledEdges} nodeTypes={nodeTypes}
          onNodesChange={onNodesChange} onNodeClick={onNodeClick} onPaneClick={() => setSelected(null)}
          onNodeDrag={onNodeDrag} onNodeDragStop={onNodeDragStop}
          onNodeMouseEnter={(_, n) => setHover(n.type === 'tierhub' ? null : n.id)} onNodeMouseLeave={() => setHover(null)}
          fitView minZoom={0.2} maxZoom={1.8}
          defaultEdgeOptions={{ type: layout === 'tree' ? 'smoothstep' : 'straight' }}
        >
          <Background color="#182734" gap={26} size={1} />
          <Controls showInteractive={false} />
          <MiniMap nodeColor={miniColor} nodeStrokeWidth={0} maskColor="rgba(8,14,20,.74)" pannable zoomable />
        </ReactFlow>
        </div>

        <DetailPanel node={selected} onClose={() => setSelected(null)} onNav={navTo} visChildren={visChildren} />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ReactFlowProvider>
      <Canvas />
    </ReactFlowProvider>
  );
}
