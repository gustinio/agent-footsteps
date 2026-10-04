// The contract written by the exporter. The page reads this file and computes nothing from it.
export type ToolCategory =
  | 'shell'
  | 'read'
  | 'search'
  | 'edit'
  | 'plan'
  | 'web'
  | 'finish'
  | 'other'
  | 'none'

export type ResultStatus = 'ok' | 'error' | 'empty'

export type Method = 'hmm' | 'gmm'

export interface Step {
  tool_category: ToolCategory
  result_status: ResultStatus
  hmm_state: number
  gmm_state: number
  // Display position of the step in the point cloud, from 0 to 1. Never used to group steps.
  x: number
  y: number
}

export interface Run {
  run_id: string
  task_id: string
  source: string
  agent: string
  model: string
  // Set for planted runs only.
  condition: 'none' | 'strong' | null
  n_steps: number
  // Present only once the pre-registration tag exists.
  outcome?: 'pass' | 'fail'
  steps: Step[]
}

export interface Difference {
  estimate: number
  low: number
  high: number
}

export interface StateName {
  state: number
  name: string
  labeled_steps: number
  intents: Record<string, number>
  facts: Record<string, number>
}

export interface Q1 {
  labeler: {
    kappa: number | null
    compared_steps: number
    bar: number
    passes: boolean
    labels_used: string
  }
  q1: {
    criterion: string
    held_out_steps: number
    held_out_runs: number
    nmi: Record<'hmm' | 'gmm' | 'majority', number>
    differences: Record<'hmm_minus_gmm' | 'hmm_minus_majority', Difference>
    passes: boolean
  }
  states: StateName[]
}

export interface Interval {
  estimate: number
  low: number
  high: number
}

export interface SignalEntry {
  name: string
  low: number
  high: number
  // Whether the range leaves the no-effect value.
  clear: boolean
  // Which kind of run has more of it.
  more_in: 'failing' | 'passing'
  // A profile entry has a coefficient and a move has an AUROC.
  coefficient?: number
  auroc?: number
}

export interface Q3a {
  criterion: string
  runs: number
  tasks: number
  failing_share: number
  auroc: Record<'length' | 'behaviour' | 'supervised', Interval>
  differences: Record<'behaviour_minus_length' | 'supervised_minus_behaviour', Interval>
  beats_length: boolean
  near_supervised: boolean
  passes: boolean
  signal: {
    profile: SignalEntry[]
    moves: SignalEntry[]
    moves_tested: number
  }
}

export interface Q3bEntry {
  k: number
  runs: number
  runs_dropped: number
  tasks: number
  failing_share: number
  // Run length is a reference line and not a competitor, because it uses information from the future.
  auroc: Record<'length' | 'baseline' | 'behaviour' | 'supervised', Interval>
  differences: Record<'behaviour_minus_baseline' | 'supervised_minus_behaviour', Interval>
  beats_baseline: boolean
  near_supervised: boolean
  passes: boolean
}

export interface Q3b {
  criterion: string
  natural_runs: number
  per_k: Q3bEntry[]
  passes: boolean
}

export interface Q4Stage {
  stage: string
  k?: number
  runs: number
  seen: number
  unseen: number
  drop: Interval
  passes: boolean
}

export interface Q4 {
  criterion: string
  auroc: Q4Stage[]
  auroc_passes: boolean
  // Null until the human sample is labeled.
  agreement: {
    seen_steps: number
    unseen_steps: number
    seen: number
    unseen: number
    drop: Interval
    passes: boolean
  } | null
  // Null while the agreement part cannot be judged.
  passes: boolean | null
}

export type Condition = 'none' | 'strong'

// One task's share in each condition, and whether the instruction raised it.
export interface TaskShare {
  task_id: string
  none: number
  strong: number
  rose: boolean
}

export interface Q2 {
  criterion: string
  tasks: number
  tasks_run: number
  interim: 'continue' | 'stop' | 'pending'
  manipulation: {
    table: TaskShare[]
    rises: number
    needs: number
    // Null until every task has run.
    passes: boolean | null
  }
  // Null when no discovered state is mostly repeats, which is reported as not detected.
  state: {
    // Zero-based, like the states on the ribbons.
    state: number
    repeat_share: number
    table: TaskShare[]
    rises: number
    needs: number
    passes: boolean
  } | null
  passes: boolean | null
}

export interface Site {
  meta: {
    // Absent until the human sample is labeled.
    q1?: Q1
    q2?: Q2
    q3a?: Q3a
    q3b?: Q3b
    q4?: Q4
    dataset: string
    revision: string
    runs_in_dataset: number
    planted_runs: number
    segmentation: {
      n_states: number
      natural_runs: number
      // Share of the natural steps in each state, in state order.
      state_shares: Record<Method, number[]>
    }
  }
  runs: Run[]
}

export async function loadSite(url: string): Promise<Site> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`could not load the site data (${response.status})`)
  }
  return response.json()
}
