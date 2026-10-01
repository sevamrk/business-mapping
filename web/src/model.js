// The node tree the canvas drills through, built from two inputs:
//
//   map     the function map itself (examples/*.json), exactly as the Python tool reads it
//   report  the output of `python3 main.py --json report` over that same map
//
// The canvas never works out a verdict. Patterns, readiness, risk, recoverable hours and
// gap findings all come from the report, so there is one implementation of the model and
// it is the tested Python one. This file only arranges those answers into tiers:
//
//   company -> area -> function
//   company -> unlocks -> one blocker -> the functions it holds back
//   company -> findings -> one kind of gap -> the things it names
//
// Pure: no React, no DOM, no imports of data. Everything here runs under vitest in Node.

import { mapDigest } from './digest.js';
import { GAP_CODES, PATTERNS } from './vocab.js';

export const ROOT_ID = 'root';
export const UNLOCKS_ID = 'unlocks';
export const FINDINGS_ID = 'findings';

const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
export const areaNodeId = (area) => `area:${slug(area)}`;
export const functionNodeId = (fnId) => `fn:${fnId}`;

// The patterns where something specific stands between the function and an agent.
// agent_led has nothing in the way; keep_human is a verdict, not a blocker to clear.
const UNLOCKABLE = new Set(['instrument_first', 'document_first', 'assisted', 'agent_with_approval']);

const round1 = (x) => Math.round(x * 10) / 10;

// What each gap code's `subject` is an id of, per src/gaps.py.
export const SUBJECT_KIND = {
  unowned_function: 'function',
  no_performer: 'function',
  ready_and_untouched: 'function',
  state_conflicts_with_facts: 'function',
  dependency_loop: 'function',
  unsourced_input: 'artifact',
  orphan_output: 'artifact',
  unused_artifact: 'artifact',
  single_point_of_failure: 'actor',
  idle_actor: 'actor',
};

export class ModelError extends Error {}

// A report produced from a different version of the map is the failure this guards.
// It loads without complaint and quietly shows the wrong verdicts, so refuse it.
//
// The hash is the check that covers everything: report.map_sha256 is the Python tool's
// digest of the map it read, and any edit anywhere in the map changes it. The field checks
// after it stay because they say WHAT moved, which a hash cannot.
export function checkConsistency(map, report) {
  const problems = [];
  if (!report.map_sha256) {
    problems.push('the report carries no map_sha256, so it cannot be checked against the map');
  } else if (report.map_sha256 !== mapDigest(map)) {
    problems.push('the map has changed since the report was made (its map_sha256 no longer matches)');
  }
  if (report.company !== map.company) {
    problems.push(`report is for "${report.company}", map is "${map.company}"`);
  }
  const detail = new Map((report.functions_detail || []).map((d) => [d.function, d]));
  for (const fn of map.functions) {
    const d = detail.get(fn.id);
    if (!d) {
      problems.push(`function "${fn.id}" is in the map and missing from the report`);
      continue;
    }
    const hours = round1((fn.volume_per_month * fn.minutes_per_run * 12) / 60);
    if (Math.abs(hours - d.hours_per_year) > 0.05) {
      problems.push(`function "${fn.id}": map gives ${hours} h/yr, report says ${d.hours_per_year}`);
    }
    if (!PATTERNS[d.pattern]) problems.push(`function "${fn.id}": unknown pattern "${d.pattern}"`);
  }
  const mapIds = new Set(map.functions.map((f) => f.id));
  const ids = {
    function: mapIds,
    artifact: new Set(map.artifacts.map((a) => a.id)),
    actor: new Set(map.actors.map((a) => a.id)),
  };
  for (const g of report.gaps || []) {
    const kind = SUBJECT_KIND[g.code];
    if (!kind) problems.push(`finding code "${g.code}" is not one the canvas knows`);
    else if (!ids[kind].has(g.subject)) problems.push(`finding "${g.code}" names ${kind} "${g.subject}", which the map does not have`);
  }
  for (const id of detail.keys()) {
    if (!mapIds.has(id)) problems.push(`function "${id}" is in the report and not in the map`);
  }
  return problems;
}

export function buildModel(map, report) {
  const problems = checkConsistency(map, report);
  if (problems.length) {
    throw new ModelError(
      `the report does not match the map. Regenerate it with \`make web-data\`.\n  ${problems.join('\n  ')}`,
    );
  }

  const NODES = new Map();
  const CHILDREN = new Map();

  const add = (node) => {
    if (NODES.has(node.id)) throw new ModelError(`duplicate node id "${node.id}"`);
    if (node.parentId != null && !NODES.has(node.parentId)) {
      throw new ModelError(`node "${node.id}" names a parent that does not exist: "${node.parentId}"`);
    }
    NODES.set(node.id, node);
    if (node.parentId != null) {
      if (!CHILDREN.has(node.parentId)) CHILDREN.set(node.parentId, []);
      CHILDREN.get(node.parentId).push(node.id);
    }
  };

  const actors = new Map(map.actors.map((a) => [a.id, a]));
  const artifacts = new Map(map.artifacts.map((a) => [a.id, a]));
  const functions = new Map(map.functions.map((f) => [f.id, f]));
  const verdicts = new Map(report.functions_detail.map((d) => [d.function, d]));
  const actorName = (id) => actors.get(id)?.name || id;

  const producers = new Map();
  const consumers = new Map();
  for (const fn of map.functions) {
    for (const a of fn.outputs) (producers.get(a) || producers.set(a, []).get(a)).push(fn.id);
    for (const a of fn.inputs) (consumers.get(a) || consumers.set(a, []).get(a)).push(fn.id);
  }

  // Which functions a finding is about. The report names a function, an artifact or an
  // actor as its subject; the canvas can only jump to functions, so resolve to those.
  // The kind comes from the code, never from a lookup: the three id spaces are separate
  // and the example map reuses four ids across functions and artifacts.
  const findingTargets = (f) => {
    const kind = SUBJECT_KIND[f.code];
    if (f.code === 'dependency_loop') {
      const chain = String(f.message).split(':').slice(1).join(':').split('->').map((s) => s.trim());
      const members = [...new Set(chain)].filter((id) => functions.has(id));
      return members.length ? members : [f.subject].filter((id) => functions.has(id));
    }
    if (kind === 'function') return functions.has(f.subject) ? [f.subject] : [];
    if (kind === 'artifact') {
      return [...new Set([...(producers.get(f.subject) || []), ...(consumers.get(f.subject) || [])])];
    }
    if (f.code === 'single_point_of_failure') {
      // the same rule gaps.py counts by: the functions this actor performs alone
      return map.functions
        .filter((fn) => fn.performers.length === 1 && fn.performers[0] === f.subject)
        .map((fn) => fn.id);
    }
    if (kind === 'actor') {
      return map.functions
        .filter((fn) => fn.owner === f.subject || fn.performers.includes(f.subject))
        .map((fn) => fn.id);
    }
    return [];
  };
  const findings = (report.gaps || []).map((f, i) => ({ ...f, index: i, targets: findingTargets(f) }));
  const findingsByFn = new Map();
  for (const f of findings) {
    for (const t of f.targets) (findingsByFn.get(t) || findingsByFn.set(t, []).get(t)).push(f);
  }

  // --- the company ---
  add({
    id: ROOT_ID,
    type: 'company',
    label: map.company,
    parentId: null,
    data: {
      kind: 'company',
      description: map.description,
      summary: {
        functions: report.functions,
        actors: report.actors,
        artifacts: report.artifacts,
        areas: report.areas,
        hours: report.hours_per_year,
        automated: report.hours_already_automated,
        recoverable: report.recoverable_hours,
        recoverableFte: report.recoverable_fte,
        hoursPerFte: report.hours_per_fte_year,
      },
      byArea: report.by_area,
      byPattern: report.by_pattern,
    },
  });

  // --- areas, in the order the map first mentions them, and their functions ---
  const areas = [];
  for (const fn of map.functions) if (!areas.includes(fn.area)) areas.push(fn.area);
  for (const area of areas) {
    const stats = report.by_area[area] || { functions: 0, hours: 0, recoverable: 0, unowned: 0 };
    const fns = map.functions.filter((f) => f.area === area);
    add({
      id: areaNodeId(area),
      type: 'area',
      label: area,
      parentId: ROOT_ID,
      data: {
        kind: 'area',
        ...stats,
        owners: [...new Set(fns.map((f) => f.owner).filter(Boolean))].map(actorName),
        byPattern: countBy(fns, (f) => verdicts.get(f.id).pattern),
      },
    });
    for (const fn of fns) {
      const v = verdicts.get(fn.id);
      add({
        id: functionNodeId(fn.id),
        type: 'function',
        label: fn.name,
        parentId: areaNodeId(area),
        data: {
          kind: 'function',
          fn,
          verdict: v,
          pattern: v.pattern,
          ownerName: fn.owner ? actorName(fn.owner) : null,
          performerNames: fn.performers.map(actorName),
          findings: findingsByFn.get(fn.id) || [],
        },
      });
    }
  }

  // --- unlocks: the blockers, largest amount of work behind them first ---
  add({ id: UNLOCKS_ID, type: 'lens', label: 'Unlocks', parentId: ROOT_ID, data: { kind: 'unlocks' } });
  const clusters = new Map();
  for (const fn of map.functions) {
    const v = verdicts.get(fn.id);
    if (!UNLOCKABLE.has(v.pattern)) continue;
    const key = `${v.pattern}|${v.reason}`;
    if (!clusters.has(key)) {
      clusters.set(key, {
        pattern: v.pattern, reason: v.reason, nextStep: v.next_step, fnIds: [], hours: 0, recoverable: 0,
      });
    }
    const c = clusters.get(key);
    c.fnIds.push(fn.id);
    c.hours += v.hours_per_year;
    c.recoverable += v.recoverable_hours;
  }
  const ranked = [...clusters.values()].sort(
    (a, b) => b.hours - a.hours || b.fnIds.length - a.fnIds.length || a.reason.localeCompare(b.reason),
  );
  for (const c of ranked) {
    add({
      id: `unlock:${slug(c.pattern)}:${slug(c.reason)}`,
      type: 'unlock',
      label: c.nextStep,
      parentId: UNLOCKS_ID,
      data: {
        kind: 'unlock',
        pattern: c.pattern,
        reason: c.reason,
        nextStep: c.nextStep,
        count: c.fnIds.length,
        hours: round1(c.hours),
        recoverable: round1(c.recoverable),
        fnIds: [...c.fnIds].sort((a, b) => verdicts.get(b).hours_per_year - verdicts.get(a).hours_per_year),
      },
    });
  }

  // --- findings, grouped by kind, most severe kind first ---
  add({
    id: FINDINGS_ID, type: 'lens', label: 'Findings', parentId: ROOT_ID,
    data: { kind: 'findings', count: findings.length },
  });
  const sevRank = { high: 0, medium: 1, low: 2 };
  const byCode = new Map();
  for (const f of findings) (byCode.get(f.code) || byCode.set(f.code, []).get(f.code)).push(f);
  const codes = [...byCode.keys()].sort((a, b) => {
    const sa = Math.min(...byCode.get(a).map((f) => sevRank[f.severity] ?? 3));
    const sb = Math.min(...byCode.get(b).map((f) => sevRank[f.severity] ?? 3));
    return sa - sb || a.localeCompare(b);
  });
  for (const code of codes) {
    const items = byCode.get(code);
    add({
      id: `finding:${code}`,
      type: 'finding',
      label: GAP_CODES[code] || code.replace(/_/g, ' '),
      parentId: FINDINGS_ID,
      data: {
        kind: 'finding',
        code,
        severity: items.reduce((s, f) => ((sevRank[f.severity] ?? 3) < (sevRank[s] ?? 3) ? f.severity : s), 'low'),
        items,
      },
    });
  }

  // --- accessors ---
  const getNode = (id) => NODES.get(id) || null;
  const getChildren = (id) => (CHILDREN.get(id) || []).map((c) => NODES.get(c));
  const hasChildren = (id) => (CHILDREN.get(id) || []).length > 0;
  const getAncestors = (id) => {
    const chain = [];
    let n = NODES.get(id);
    while (n && n.parentId != null) {
      n = NODES.get(n.parentId);
      if (n) chain.unshift(n);
    }
    return chain;
  };

  // Artifact flow between two functions drawn on the same tier. The Python graph is
  // artifact-shaped; on a tier of functions it collapses to "A makes something B uses".
  const flowEdges = (fnNodeIds) => {
    const onTier = new Set(fnNodeIds);
    const pairs = new Map();
    for (const nodeId of fnNodeIds) {
      const fn = NODES.get(nodeId)?.data.fn;
      if (!fn) continue;
      for (const art of fn.outputs) {
        for (const c of consumers.get(art) || []) {
          const target = functionNodeId(c);
          if (target === nodeId || !onTier.has(target)) continue;
          const key = `${nodeId}>${target}`;
          if (!pairs.has(key)) pairs.set(key, { source: nodeId, target, artifacts: [] });
          pairs.get(key).artifacts.push(artifacts.get(art)?.name || art);
        }
      }
    }
    return [...pairs.values()].map((p) => ({ id: `flow:${p.source}>${p.target}`, kind: 'flow', ...p }));
  };

  // One tier as a graph: the current node as a hub, each visible child around it, and
  // artifact flow between any functions that share the tier.
  const buildTierGraph = (rootId, isVisible = () => true) => {
    const root = NODES.get(rootId) || NODES.get(ROOT_ID);
    const kids = getChildren(root.id).filter(isVisible);
    const nodes = [{
      id: root.id, type: 'tierhub', position: { x: 0, y: 0 },
      data: { ...root.data, label: root.label, nodeType: root.type },
    }];
    const edges = [];
    for (const k of kids) {
      const visibleKids = getChildren(k.id).filter(isVisible).length;
      nodes.push({
        id: k.id, type: k.type, position: { x: 0, y: 0 },
        data: { ...k.data, label: k.label, drillable: visibleKids > 0, childCount: visibleKids },
      });
      edges.push({ id: `e:${root.id}>${k.id}`, source: root.id, target: k.id, kind: 'tree' });
    }
    edges.push(...flowEdges(kids.filter((k) => k.type === 'function').map((k) => k.id)));
    return { root, nodes, edges };
  };

  const searchNodes = (q, limit = 8) => {
    const s = q.trim().toLowerCase();
    if (!s) return [];
    const hits = [];
    for (const n of NODES.values()) {
      if (n.id === ROOT_ID) continue;
      const d = n.data || {};
      const parts = [n.label, d.reason, d.nextStep];
      if (d.fn) {
        parts.push(d.fn.description, d.fn.notes, d.fn.area, d.ownerName, ...d.performerNames);
        parts.push(PATTERNS[d.pattern]?.label, d.verdict.reason);
        parts.push(...[...d.fn.inputs, ...d.fn.outputs].map((a) => artifacts.get(a)?.name));
      }
      if (d.owners) parts.push(...d.owners);
      if (parts.filter(Boolean).join(' ').toLowerCase().includes(s)) hits.push(n);
      if (hits.length >= limit) break;
    }
    return hits;
  };

  const artifact = (id) => {
    const a = artifacts.get(id);
    return {
      id,
      name: a?.name || id,
      form: a?.form,
      boundary: a?.boundary,
      producers: (producers.get(id) || []).map(functionNodeId),
      consumers: (consumers.get(id) || []).map(functionNodeId),
    };
  };

  const allFunctions = () => [...NODES.values()].filter((n) => n.type === 'function');

  // Where the canvas should stand to show a node: inside it if it opens onto anything,
  // otherwise on its parent's tier so the node itself is on screen.
  const pathTo = (id) => {
    if (!NODES.has(id)) return [ROOT_ID];
    const anc = getAncestors(id).map((a) => a.id);
    if (hasChildren(id)) return [...anc, id];
    return anc.length ? anc : [ROOT_ID];
  };

  return {
    getNode, getChildren, hasChildren, getAncestors, buildTierGraph, searchNodes, artifact,
    allFunctions, pathTo, findings, size: NODES.size,
  };
}

// The pattern filter: functions hide when their pattern is switched off, nothing else does.
export const patternFilter = (on) => (node) => node.type !== 'function' || !!on[node.data.pattern];

function countBy(items, key) {
  const out = {};
  for (const it of items) {
    const k = key(it);
    out[k] = (out[k] || 0) + 1;
  }
  return out;
}
