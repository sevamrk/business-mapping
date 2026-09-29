import { describe, expect, it } from 'vitest';
import {
  FINDINGS_ID, ModelError, ROOT_ID, UNLOCKS_ID, buildModel, checkConsistency, patternFilter,
} from '../src/model.js';
import { PARTLY, SCREEN, fixtureMap, fixtureReport } from './fixture.js';

const model = () => buildModel(fixtureMap(), fixtureReport());

describe('checkConsistency: a report from a different map is refused, not rendered', () => {
  it('passes the matching pair', () => {
    expect(checkConsistency(fixtureMap(), fixtureReport())).toEqual([]);
  });

  it('catches a function missing from the report', () => {
    const r = fixtureReport();
    r.functions_detail = r.functions_detail.filter((d) => d.function !== 'step-c');
    expect(checkConsistency(fixtureMap(), r)).toEqual([
      'function "step-c" is in the map and missing from the report',
    ]);
  });

  it('catches a function the map no longer has', () => {
    const m = fixtureMap();
    m.functions = m.functions.filter((f) => f.id !== 'step-e');
    expect(checkConsistency(m, fixtureReport())).toEqual([
      'function "step-e" is in the report and not in the map',
    ]);
  });

  it('catches a volume edited after the report was made', () => {
    const m = fixtureMap();
    m.functions[0].volume_per_month = 20; // 24 h/yr now, the report still says 12
    expect(checkConsistency(m, fixtureReport())).toEqual([
      'function "step-a": map gives 24 h/yr, report says 12',
    ]);
  });

  it('catches a pattern the canvas has no colour for', () => {
    const r = fixtureReport();
    r.functions_detail[0].pattern = 'robot_overlord';
    expect(checkConsistency(fixtureMap(), r)).toEqual(['function "step-a": unknown pattern "robot_overlord"']);
  });

  it('catches a report for another company', () => {
    const r = fixtureReport();
    r.company = 'Other';
    expect(checkConsistency(fixtureMap(), r)).toEqual(['report is for "Other", map is "Fixture"']);
  });

  it('catches a finding about something the map no longer has', () => {
    const r = fixtureReport();
    r.gaps[0].subject = 'step-z';
    expect(checkConsistency(fixtureMap(), r)).toEqual([
      'finding "unowned_function" names function "step-z", which the map does not have',
    ]);
  });

  it('checks a finding subject against the right id space', () => {
    // "mid" is an artifact, so a function-kind finding naming it is stale
    const r = fixtureReport();
    r.gaps[0].subject = 'mid';
    expect(checkConsistency(fixtureMap(), r)).toHaveLength(1);
  });

  it('catches a finding code the canvas has no label for', () => {
    const r = fixtureReport();
    r.gaps[0].code = 'new_kind_of_gap';
    expect(checkConsistency(fixtureMap(), r)).toEqual(['finding code "new_kind_of_gap" is not one the canvas knows']);
  });

  it('makes buildModel throw with the fix in the message', () => {
    const r = fixtureReport();
    r.functions_detail.pop();
    expect(() => buildModel(fixtureMap(), r)).toThrow(ModelError);
    expect(() => buildModel(fixtureMap(), r)).toThrow(/make web-data/);
  });
});

describe('the tree', () => {
  it('puts areas and the two lenses under the company, in map order', () => {
    const m = model();
    expect(m.getChildren(ROOT_ID).map((n) => n.id)).toEqual(['area:alpha', 'area:beta', UNLOCKS_ID, FINDINGS_ID]);
  });

  it('puts each function under its own area', () => {
    const m = model();
    expect(m.getChildren('area:alpha').map((n) => n.id)).toEqual(['fn:step-a', 'fn:step-b']);
    expect(m.getChildren('area:beta').map((n) => n.id)).toEqual(['fn:step-c', 'fn:step-d', 'fn:step-e']);
  });

  it('carries names, not ids, for owners and performers', () => {
    const d = model().getNode('fn:step-d').data;
    expect(d.ownerName).toBe('Team Lead');
    expect(d.performerNames).toEqual(['Team Lead', 'Records Clerk']);
    expect(model().getNode('fn:step-c').data.ownerName).toBeNull();
  });

  it('counts verdicts per area', () => {
    expect(model().getNode('area:beta').data.byPattern).toEqual({ instrument_first: 1, keep_human: 1, assisted: 1 });
  });

  it('walks ancestors from the top', () => {
    expect(model().getAncestors('fn:step-c').map((n) => n.id)).toEqual([ROOT_ID, 'area:beta']);
  });
});

describe('unlocks', () => {
  it('groups by the blocker and ranks by the hours behind it', () => {
    const kids = model().getChildren(UNLOCKS_ID);
    expect(kids.map((k) => [k.data.reason, k.data.count, k.data.hours])).toEqual([
      [SCREEN, 2, 72],
      [PARTLY, 1, 24],
    ]);
  });

  it('leaves out agent_led and keep_human, which have nothing to clear', () => {
    const inUnlocks = model().getChildren(UNLOCKS_ID).flatMap((k) => k.data.fnIds);
    expect(inUnlocks.sort()).toEqual(['step-b', 'step-c', 'step-e']);
  });

  it('lists the biggest function first inside a blocker', () => {
    expect(model().getChildren(UNLOCKS_ID)[0].data.fnIds).toEqual(['step-c', 'step-b']);
  });
});

describe('findings resolve to the functions they are about', () => {
  const targets = (code) => model().findings.find((f) => f.code === code).targets;

  it('a function subject is that function', () => {
    expect(targets('unowned_function')).toEqual(['step-c']);
  });

  it('an artifact subject is whatever makes or reads it, even when a function shares the id', () => {
    // a lookup that tried functions first would answer ['step-b'] here
    expect(targets('orphan_output')).toEqual(['step-b', 'step-c']);
  });

  it('an unsourced artifact resolves to its readers', () => {
    expect(targets('unsourced_input')).toEqual(['step-b']);
  });

  it('a single point of failure is the functions that actor does alone, as gaps.py counts them', () => {
    // step-d has the clerk too, but not alone
    expect(targets('single_point_of_failure')).toEqual(['step-a', 'step-b']);
  });

  it('a loop is every function in it', () => {
    expect(targets('dependency_loop')).toEqual(['step-a', 'step-b']);
  });

  it('shows on the function node', () => {
    expect(model().getNode('fn:step-b').data.findings.map((f) => f.code)).toEqual([
      'unsourced_input', 'orphan_output', 'single_point_of_failure', 'dependency_loop',
    ]);
  });

  it('groups by kind, most severe first', () => {
    expect(model().getChildren(FINDINGS_ID).map((n) => n.data.code)).toEqual([
      'unowned_function', 'unsourced_input', 'orphan_output', 'single_point_of_failure', 'dependency_loop',
    ]);
  });
});

describe('buildTierGraph', () => {
  it('draws the current node as a hub with an edge to each child', () => {
    const g = model().buildTierGraph('area:alpha');
    expect(g.nodes.map((n) => [n.id, n.type])).toEqual([
      ['area:alpha', 'tierhub'], ['fn:step-a', 'function'], ['fn:step-b', 'function'],
    ]);
    expect(g.edges.filter((e) => e.kind === 'tree').map((e) => e.id)).toEqual([
      'e:area:alpha>fn:step-a', 'e:area:alpha>fn:step-b',
    ]);
  });

  it('draws artifact flow between functions on the same tier, naming the artifact', () => {
    const flow = model().buildTierGraph('area:alpha').edges.filter((e) => e.kind === 'flow');
    expect(flow).toEqual([
      { id: 'flow:fn:step-a>fn:step-b', kind: 'flow', source: 'fn:step-a', target: 'fn:step-b', artifacts: ['Middle record'] },
    ]);
  });

  it('does not draw flow to a function on another tier', () => {
    // step-b feeds step-c, but step-c is in beta
    expect(model().buildTierGraph('area:beta').edges.filter((e) => e.kind === 'flow')).toEqual([]);
  });

  it('falls back to the company for an unknown id', () => {
    expect(model().buildTierGraph('nope').root.id).toBe(ROOT_ID);
  });
});

describe('the pattern filter', () => {
  it('hides functions whose pattern is off and nothing else', () => {
    const only = patternFilter({ instrument_first: true });
    const g = model().buildTierGraph('area:beta', only);
    expect(g.nodes.map((n) => n.id)).toEqual(['area:beta', 'fn:step-c']);
  });

  it('recounts an area, and an area with nothing left stops being drillable', () => {
    const only = patternFilter({ keep_human: true });
    const areas = Object.fromEntries(model().buildTierGraph(ROOT_ID, only).nodes.map((n) => [n.id, n.data]));
    expect(areas['area:beta'].childCount).toBe(1);
    expect(areas['area:alpha'].childCount).toBe(0);
    expect(areas['area:alpha'].drillable).toBe(false);
  });
});

describe('pathTo', () => {
  it('stands inside anything that opens', () => {
    expect(model().pathTo('area:beta')).toEqual([ROOT_ID, 'area:beta']);
  });

  it('stands on the parent tier for a leaf, so the leaf is on screen', () => {
    expect(model().pathTo('fn:step-c')).toEqual([ROOT_ID, 'area:beta']);
  });

  it('goes home for an id it does not know', () => {
    expect(model().pathTo('fn:nope')).toEqual([ROOT_ID]);
  });
});

describe('searchNodes', () => {
  it('matches on a person, not only the label', () => {
    expect(model().searchNodes('records clerk').map((n) => n.id)).toContain('fn:step-a');
  });

  it('matches on the name of an artifact a function uses', () => {
    expect(model().searchNodes('loose sheet').map((n) => n.id)).toEqual(['fn:step-b']);
  });

  it('ignores case and surrounding space, never returns the company, and respects the limit', () => {
    const m = model();
    expect(m.searchNodes('  DO STEP  ').map((n) => n.id)).toHaveLength(5);
    expect(m.searchNodes('fixture').map((n) => n.id)).not.toContain(ROOT_ID);
    expect(m.searchNodes('do step', 2)).toHaveLength(2);
    expect(m.searchNodes('   ')).toEqual([]);
  });
});

describe('artifact', () => {
  it('lists producers and consumers as node ids', () => {
    expect(model().artifact('mid')).toMatchObject({ name: 'Middle record', producers: ['fn:step-a'], consumers: ['fn:step-b'] });
  });
});
