// The shipped example, loaded the way the canvas loads it. The expected numbers are
// written out by hand from `python3 main.py report` so a change to the map or the
// model shows up here as a diff someone has to accept, not as a silent re-render.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { FINDINGS_ID, ROOT_ID, SUBJECT_KIND, UNLOCKS_ID, buildModel } from '../src/model.js';
import { CURRENT_STATES, GAP_CODES, PATTERN_ORDER, RISK_BANDS } from '../src/vocab.js';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');
const readJson = (p) => JSON.parse(readFileSync(resolve(repo, p), 'utf8'));

const map = readJson('examples/harbourgate-coffee.json');
const report = readJson('web/src/data/report.json');
const model = buildModel(map, report);

describe('the example company', () => {
  it('loads, and the committed report matches the map', () => {
    expect(model.getNode(ROOT_ID).label).toBe('Harbourgate Coffee Roasters');
  });

  it('has the counts the README states', () => {
    expect(model.allFunctions()).toHaveLength(50);
    expect(model.getChildren(ROOT_ID).filter((n) => n.type === 'area')).toHaveLength(8);
    expect(model.findings).toHaveLength(19);
  });

  it('ranks the blockers by hours behind them', () => {
    expect(model.getChildren(UNLOCKS_ID).map((n) => [n.data.pattern, n.data.count, n.data.hours])).toEqual([
      ['instrument_first', 4, 3736],
      ['instrument_first', 12, 1980],
      ['assisted', 4, 1432],
      ['agent_with_approval', 8, 824],
      ['document_first', 1, 180],
    ]);
  });

  it('resolves the unsourced packaging stock level to the job that reads it', () => {
    const f = model.findings.find((x) => x.code === 'unsourced_input');
    expect(f.subject).toBe('packaging-stock-level');
    expect(f.targets).toEqual(['packaging-reorder']);
  });

  it('resolves the bookkeeper finding to the five jobs the message counts', () => {
    const f = model.findings.find((x) => x.code === 'single_point_of_failure' && x.subject === 'bookkeeper');
    expect(f.message).toMatch(/on 5 functions/);
    expect(f.targets).toHaveLength(5);
  });

  it('gives every finding something to jump to except an idle actor, which does nothing by definition', () => {
    const empty = model.findings.filter((f) => f.targets.length === 0).map((f) => f.code);
    expect(empty).toEqual(['idle_actor']);
  });

  it('draws the finance flow the trace command shows', () => {
    const flow = model.buildTierGraph('area:finance').edges.filter((e) => e.kind === 'flow').map((e) => e.id);
    expect(flow).toContain('flow:fn:invoice-issue>fn:payment-matching');
    expect(flow).toContain('flow:fn:monthly-close>fn:vat-return');
    expect(flow).toHaveLength(8);
  });

  it('opens the findings lens onto one node per kind', () => {
    expect(model.getChildren(FINDINGS_ID)).toHaveLength(new Set(report.gaps.map((g) => g.code)).size);
  });
});

// The canvas carries labels and colours for vocabularies that Python defines. These
// read the Python source as text, so a level added there and not here goes red.
describe('in step with the Python tool', () => {
  const vocabPy = readFileSync(resolve(repo, 'src/vocab.py'), 'utf8');
  const gapsPy = readFileSync(resolve(repo, 'src/gaps.py'), 'utf8');

  it('knows every pattern, in the same order', () => {
    const block = vocabPy.match(/PATTERNS = \(([\s\S]*?)\)/)[1];
    const py = [...block.matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
    expect(py).toHaveLength(6);
    expect(PATTERN_ORDER).toEqual(py);
  });

  it('knows every current state and risk band', () => {
    const states = [...vocabPy.match(/CURRENT_STATES = \{([^}]*)\}/)[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
    const bands = [...vocabPy.match(/RISK_BANDS = \(([^)]*)\)/)[1].matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);
    expect(states).toEqual(['manual', 'assisted', 'automated']);
    expect(Object.keys(CURRENT_STATES)).toEqual(states);
    expect(bands).toEqual(['low', 'moderate', 'high', 'critical']);
    expect(Object.keys(RISK_BANDS)).toEqual(bands);
  });

  it('reads each gap subject as the kind of id gaps.py puts there', () => {
    // written out from reading src/gaps.py, not derived, so a wrong kind cannot agree with itself
    expect(SUBJECT_KIND).toEqual({
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
    });
  });

  it('has a label and a subject kind for every gap code gaps.py can emit', () => {
    const py = [...gapsPy.matchAll(/Finding\(\s*"([a-z_]+)"/g)].map((m) => m[1]);
    const codes = [...new Set(py)].sort();
    expect(codes.length).toBeGreaterThanOrEqual(10);
    expect(Object.keys(GAP_CODES).sort()).toEqual(codes);
    expect(Object.keys(SUBJECT_KIND).sort()).toEqual(codes);
  });
});
