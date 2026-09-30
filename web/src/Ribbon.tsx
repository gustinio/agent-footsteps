import { CATEGORY_FILL, STATUS_LABEL } from '@/palette'
import type { Run } from '@/site'

const CELL_WIDTH = 6
const CELL_HEIGHT = 14
const GAP = 1

export function Ribbon({ run }: { run: Run }) {
  const width = run.steps.length * (CELL_WIDTH + GAP)
  return (
    <svg
      width={width}
      height={CELL_HEIGHT + 4}
      role="img"
      aria-label={`${run.n_steps} steps of run ${run.run_id}`}
    >
      {run.steps.map((step, index) => (
        <g key={index} transform={`translate(${index * (CELL_WIDTH + GAP)} 0)`}>
          <title>{`step ${index + 1}: ${step.tool_category}, ${STATUS_LABEL[step.result_status]}`}</title>
          <rect
            width={CELL_WIDTH}
            height={CELL_HEIGHT}
            rx={1}
            className={CATEGORY_FILL[step.tool_category]}
            opacity={step.result_status === 'empty' ? 0.4 : 1}
          />
          {step.result_status === 'error' && (
            <rect
              y={CELL_HEIGHT + 1}
              width={CELL_WIDTH}
              height={3}
              rx={1}
              className="fill-red-600"
            />
          )}
        </g>
      ))}
    </svg>
  )
}
