// A deliberately tiny, synthetic map and a hand-written report to go with it, so the
// tests below can assert exact values instead of values read back out of the thing
// under test. Not a company; the example company lives in examples/.

const verdict = (fnId, pattern, reason, hours, recoverable, extra = {}) => ({
  function: fnId,
  readiness: 0.5,
  axis_scores: { decision_type: 1, input_form: 1, interface: 0.3, change_rate: 1 },
  limiting_fact: 'interface',
  risk_level: 1,
  risk_band: 'moderate',
  pattern,
  reason,
  next_step: `next step for ${reason}`,
  hours_per_year: hours,
  recoverable_hours: recoverable,
  ...extra,
});

const fn = (id, area, inputs, outputs, volume, minutes, extra = {}) => ({
  id,
  name: `Do ${id}`,
  area,
  description: `Synthetic function ${id}.`,
  owner: 'lead',
  performers: ['clerk'],
  trigger: 'schedule',
  inputs,
  outputs,
  volume_per_month: volume,
  minutes_per_run: minutes,
  current_state: 'manual',
  automation: {
    decision_type: 'deterministic', input_form: 'structured', interface: 'ui_only', change_rate: 'stable',
    error_cost: 'low', reversibility: 'reversible', oversight: 'sampled',
  },
  ...extra,
});

export const SCREEN = 'the only way in is a screen a person clicks';
export const PARTLY = 'parts of it are machine-readable and parts are not';

export function fixtureMap() {
  return {
    company: 'Fixture',
    description: 'Synthetic.',
    actors: [
      { id: 'lead', name: 'Team Lead', kind: 'role' },
      { id: 'clerk', name: 'Records Clerk', kind: 'role' },
    ],
    artifacts: [
      { id: 'in-doc', name: 'Incoming document', form: 'semi_structured', boundary: 'inbound' },
      { id: 'mid', name: 'Middle record', form: 'structured', boundary: 'internal' },
      { id: 'loose', name: 'Loose sheet', form: 'unstructured', boundary: 'internal' },
      // same id as a function on purpose: the id spaces are separate in the schema
      { id: 'step-b', name: 'Step B output', form: 'structured', boundary: 'internal' },
      { id: 'out', name: 'Outgoing file', form: 'structured', boundary: 'outbound' },
    ],
    functions: [
      fn('step-a', 'alpha', ['in-doc'], ['mid'], 10, 6),
      fn('step-b', 'alpha', ['mid', 'loose'], ['step-b'], 20, 3),
      fn('step-c', 'beta', ['step-b'], ['out'], 5, 60, { owner: null, performers: [] }),
      fn('step-d', 'beta', ['in-doc'], ['out'], 1, 120, { performers: ['lead', 'clerk'] }),
      fn('step-e', 'beta', ['in-doc'], ['out'], 10, 12, { performers: ['lead'] }),
    ],
  };
}

export function fixtureReport() {
  return {
    company: 'Fixture',
    functions: 5,
    actors: 2,
    artifacts: 5,
    areas: 2,
    hours_per_year: 132,
    hours_already_automated: 0,
    recoverable_hours: 60,
    recoverable_fte: 0.04,
    hours_per_fte_year: 1600,
    by_pattern: {},
    by_area: {
      alpha: { functions: 2, hours: 24, recoverable: 20, unowned: 0 },
      beta: { functions: 3, hours: 108, recoverable: 40, unowned: 1 },
    },
    gaps: [
      { code: 'unowned_function', severity: 'high', subject: 'step-c', message: 'step-c has no owner' },
      { code: 'unsourced_input', severity: 'high', subject: 'loose', message: 'loose is never produced' },
      { code: 'orphan_output', severity: 'medium', subject: 'step-b', message: 'artifact step-b, read by step-c' },
      { code: 'single_point_of_failure', severity: 'medium', subject: 'clerk', message: 'clerk alone on two' },
      { code: 'dependency_loop', severity: 'low', subject: 'step-a', message: 'these functions feed each other: step-a -> step-b -> step-a' },
    ],
    functions_detail: [
      verdict('step-a', 'agent_led', 'machine-readable input, a written rule, and a way in', 12, 10),
      verdict('step-b', 'instrument_first', SCREEN, 12, 10),
      verdict('step-c', 'instrument_first', SCREEN, 60, 20),
      verdict('step-d', 'keep_human', 'a person is required to sign each case', 24, 0),
      verdict('step-e', 'assisted', PARTLY, 24, 20),
    ],
  };
}
