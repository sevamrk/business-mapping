// The canvas's view rules that do not need React, pulled out of App.jsx so they run
// under vitest in Node like the rest of the model. Pure: no DOM, no React Flow.

// An edge is only ever handed to React Flow in the same commit as both of its ends.
// Both layouts set nodes and edges together; this makes that an invariant rather than a
// matter of timing, so an async layout (ELK) can never draw an edge to a node it has
// not placed yet.
export function edgesWithEnds(nodes, edges) {
  const ids = new Set(nodes.map((n) => n.id));
  return edges.filter((e) => ids.has(e.source) && ids.has(e.target));
}

// A hover belongs to a node on the tier. A node the filter removes never fires
// mouseleave, so the hover has to be dropped when its node goes, not merely ignored:
// ignored, it comes back when the node does and dims the tier with no pointer on it.
export const hoverStillOn = (hover, tierNodes) =>
  (hover && tierNodes.some((n) => n.id === hover) ? hover : null);

// Which nodes light up and which dim while something is hovered: the node, the hub, and
// anything it hands an artifact to or takes one from. null when nothing is hovered.
export function hoverClasses(nodes, edges, hover, rootId) {
  if (!hover || !nodes.some((n) => n.id === hover)) return null;
  const hot = new Set([hover, rootId]);
  for (const e of edges) {
    if (e.kind === 'flow' && (e.source === hover || e.target === hover)) { hot.add(e.source); hot.add(e.target); }
  }
  return new Map(nodes.map((n) => [n.id, hot.has(n.id) ? 'rf-hot' : 'rf-dim']));
}

// The camera fits itself to a tier when it is drawn and when it settles, until the user
// moves a node on it. After that every automatic fit on that tier is skipped: a drag
// restarts the simulation, and the camera must stay on what they just arranged. One
// guard for every scheduled fit, because a fit the guard does not cover is a zoom reset.
export function createAutoFit(fit) {
  let held = false;
  return {
    fit: (opts) => { if (!held) fit(opts); },
    hold: () => { held = true; },
  };
}
