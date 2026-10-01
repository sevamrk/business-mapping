import { describe, expect, it } from 'vitest';
import { buildModel, patternFilter, areaNodeId } from '../src/model.js';
import { createAutoFit, edgesWithEnds, hoverClasses, hoverStillOn } from '../src/view.js';
import { fixtureMap, fixtureReport } from './fixture.js';

const model = buildModel(fixtureMap(), fixtureReport());
const ALL = { agent_led: true, instrument_first: true, assisted: true, keep_human: true };

describe('edges never arrive ahead of their nodes', () => {
  it('drops an edge whose end is not in the same commit', () => {
    const nodes = [{ id: 'a' }, { id: 'b' }];
    const edges = [
      { id: 'ab', source: 'a', target: 'b' },
      { id: 'ac', source: 'a', target: 'c' }, // c belongs to a layout that has not landed
      { id: 'ca', source: 'c', target: 'a' },
    ];
    expect(edgesWithEnds(nodes, edges).map((e) => e.id)).toEqual(['ab']);
  });

  it('keeps every edge of a whole tier', () => {
    const t = model.buildTierGraph(areaNodeId('alpha'));
    expect(edgesWithEnds(t.nodes, t.edges)).toEqual(t.edges);
  });

  it('drops the old tier\'s edges against the new tier\'s nodes', () => {
    const before = model.buildTierGraph(areaNodeId('alpha'));
    const after = model.buildTierGraph(areaNodeId('beta'));
    expect(edgesWithEnds(after.nodes, before.edges)).toEqual([]);
  });
});

describe('hiding a hovered node clears the hover', () => {
  const root = areaNodeId('beta');
  const tier = (on) => model.buildTierGraph(root, patternFilter(on));

  it('a hover on a visible node dims the rest of the tier', () => {
    const t = tier(ALL);
    const cls = hoverClasses(t.nodes, t.edges, 'fn:step-c', root);
    expect(cls.get('fn:step-c')).toBe('rf-hot');
    expect([...cls.values()]).toContain('rf-dim');
  });

  it('hide it, show it again: the tier is not dimmed, because nobody is hovering', () => {
    let hover = 'fn:step-c'; // instrument_first, pointer on it
    const hidden = tier({ ...ALL, instrument_first: false });
    hover = hoverStillOn(hover, hidden.nodes); // what the canvas does when the tier changes
    expect(hover).toBeNull();
    // the pointer moved off while the node was gone, so no mouseleave ever fired
    const shown = tier(ALL);
    expect(hoverClasses(shown.nodes, shown.edges, hover, root)).toBeNull();
  });

  it('a hover on a node that stays visible survives a filter change', () => {
    const t = tier({ ...ALL, keep_human: false });
    expect(hoverStillOn('fn:step-e', t.nodes)).toBe('fn:step-e');
  });
});

describe('a drag holds the camera', () => {
  it('fits until the user moves something, and never after', () => {
    const calls = [];
    const cam = createAutoFit((o) => calls.push(o));
    cam.fit({ why: 'first draw' });
    cam.hold(); // a node was dragged
    cam.fit({ why: 'the 500 ms timer' });
    cam.fit({ why: 'the simulation settled' });
    expect(calls).toEqual([{ why: 'first draw' }]);
  });

  it('a new tier gets a new camera, which fits again', () => {
    const calls = [];
    const old = createAutoFit(() => calls.push('old'));
    old.hold();
    createAutoFit(() => calls.push('new')).fit();
    expect(calls).toEqual(['new']);
  });
});
