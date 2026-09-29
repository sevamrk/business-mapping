// Display vocabulary only: labels and colours for values the Python tool defines.
// The values themselves live in ../../src/vocab.py and nowhere else. A test checks
// that the patterns, current states, risk bands and gap codes named here are exactly the
// ones the Python side defines, so a level added there shows up as a red suite rather
// than a grey node.

export const PATTERNS = {
  agent_led: { label: 'agent led', color: '#46d896' },
  agent_with_approval: { label: 'agent + approval', color: '#39c2e6' },
  assisted: { label: 'assisted', color: '#a884f0' },
  instrument_first: { label: 'instrument first', color: '#f0a23f' },
  document_first: { label: 'document first', color: '#ff7a5c' },
  keep_human: { label: 'keep human', color: '#6b8298' },
};

export const PATTERN_ORDER = Object.keys(PATTERNS);

export const CURRENT_STATES = {
  manual: { label: 'manual', color: '#90a4b5' },
  assisted: { label: 'assisted', color: '#39c2e6' },
  automated: { label: 'automated', color: '#46d896' },
};

export const RISK_BANDS = {
  low: '#46d896',
  moderate: '#39c2e6',
  high: '#f0a23f',
  critical: '#ff6b6b',
};

export const SEVERITY = {
  high: '#ff7a5c',
  medium: '#f0b23f',
  low: '#90a4b5',
};

// Human wording for the gap codes `main.py gaps` emits.
export const GAP_CODES = {
  unowned_function: 'Nobody owns it',
  no_performer: 'Nobody does it',
  unsourced_input: 'Used, never produced',
  orphan_output: 'Produced, never read',
  ready_and_untouched: 'Ready and still manual',
  single_point_of_failure: 'One person, many jobs',
  dependency_loop: 'Dependency loops',
  idle_actor: 'Declared, does nothing',
  unused_artifact: 'Declared, never used',
  state_conflicts_with_facts: 'State disagrees with the facts',
};

export const CAPABILITY_FACTS = ['decision_type', 'input_form', 'interface', 'change_rate'];
