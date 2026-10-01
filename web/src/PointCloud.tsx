import { STATE_FILL } from '@/palette'
import { sameStep, type StepRef } from '@/selection'
import type { Method, Run } from '@/site'

const SIZE = 460
const PAD = 12

interface PointCloudProps {
  runs: Run[]
  method: Method
  selected: StepRef | null
  hovered: StepRef | null
  onSelect: (step: StepRef) => void
  onHover: (step: StepRef | null) => void
}

export function PointCloud({ runs, method, selected, hovered, onSelect, onHover }: PointCloudProps) {
  const at = (value: number) => PAD + value * (SIZE - 2 * PAD)
  const focus = selected?.runId ?? hovered?.runId ?? null
  const points = runs.flatMap((run) =>
    run.steps.map((step, index) => ({ run, step, ref: { runId: run.run_id, step: index } })),
  )
  const emphasised = (ref: StepRef) => sameStep(ref, selected) || sameStep(ref, hovered)
  return (
    <svg
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      className="h-auto w-full max-w-[460px] rounded-md border bg-card"
      role="img"
      aria-label="Steps placed by their features, colored by behaviour state"
    >
      {points.map(({ run, step, ref }) => {
        const state = method === 'hmm' ? step.hmm_state : step.gmm_state
        const inFocus = focus === null || focus === run.run_id
        return (
          <circle
            key={`${run.run_id}:${ref.step}`}
            cx={at(step.x)}
            cy={SIZE - at(step.y)}
            r={emphasised(ref) ? 6 : 3}
            className={`${STATE_FILL[state]} cursor-pointer ${emphasised(ref) ? 'stroke-foreground' : ''}`}
            strokeWidth={2}
            opacity={inFocus ? 0.9 : 0.12}
            onClick={() => onSelect(ref)}
            onMouseEnter={() => onHover(ref)}
            onMouseLeave={() => onHover(null)}
          >
            <title>{`${run.task_id}, step ${ref.step + 1}: state ${state + 1}`}</title>
          </circle>
        )
      })}
    </svg>
  )
}
