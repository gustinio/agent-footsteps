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

export interface Site {
  meta: {
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
