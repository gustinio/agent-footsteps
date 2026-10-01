import { CATEGORY_FILL, STATE_FILL, STATUS_LABEL } from '@/palette'
import type { Method, Run } from '@/site'
import type { StepRef } from '@/selection'

const CELL_WIDTH = 6
const CELL_HEIGHT = 14
const GAP = 1

interface RibbonProps {
  run: Run
  // The state method to color by, or null to color by tool.
  colorBy: Method | null
  selected: StepRef | null
  hovered: StepRef | null
  onSelect: (step: StepRef) => void
  onHover: (step: StepRef | null) => void
}

export function Ribbon({ run, colorBy, selected, hovered, onSelect, onHover }: RibbonProps) {
  const width = run.steps.length * (CELL_WIDTH + GAP)
  const marked = (ref: StepRef | null, index: number) =>
    ref !== null && ref.runId === run.run_id && ref.step === index
  return (
    <svg
      width={width}
      height={CELL_HEIGHT + 6}
      role="img"
      aria-label={`${run.n_steps} steps of run ${run.run_id}`}
    >
      {run.steps.map((step, index) => {
        const ref = { runId: run.run_id, step: index }
        const state = colorBy === 'hmm' ? step.hmm_state : step.gmm_state
        return (
          <g
            key={index}
            transform={`translate(${index * (CELL_WIDTH + GAP)} 0)`}
            className="cursor-pointer"
            onClick={() => onSelect(ref)}
            onMouseEnter={() => onHover(ref)}
            onMouseLeave={() => onHover(null)}
          >
            <title>{`step ${index + 1}: ${step.tool_category}, ${STATUS_LABEL[step.result_status]}, state ${state + 1}`}</title>
            <rect
              width={CELL_WIDTH}
              height={CELL_HEIGHT}
              rx={1}
              className={colorBy ? STATE_FILL[state] : CATEGORY_FILL[step.tool_category]}
              opacity={!colorBy && step.result_status === 'empty' ? 0.4 : 1}
            />
            {step.result_status === 'error' && (
              <rect y={CELL_HEIGHT + 1} width={CELL_WIDTH} height={3} rx={1} className="fill-red-600" />
            )}
            {(marked(selected, index) || marked(hovered, index)) && (
              <rect
                x={-1}
                y={-1}
                width={CELL_WIDTH + 2}
                height={CELL_HEIGHT + 2}
                rx={2}
                fill="none"
                strokeWidth={2}
                className="stroke-foreground"
              />
            )}
          </g>
        )
      })}
    </svg>
  )
}
