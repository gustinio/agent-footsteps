import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Condition, Q2, TaskShare } from '@/site'

const WIDTH = 460
const ROW = 22
const PAD = { left: 130, right: 16, top: 8, bottom: 22 }

const DOT: Record<Condition, string> = { none: 'fill-slate-500', strong: 'fill-blue-600' }
const NAME: Record<Condition, string> = { none: 'no instruction', strong: 'repeat instruction' }

// Every task is its own row, with its share without the instruction and with it joined by a line.
function Dots({ table, label, condition }: { table: TaskShare[]; label: string; condition: Condition | 'all' }) {
  const height = PAD.top + ROW * table.length + PAD.bottom
  const x = (share: number) => PAD.left + share * (WIDTH - PAD.left - PAD.right)
  const shown = (['none', 'strong'] as const).filter((c) => condition === 'all' || condition === c)
  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={label} className="w-full max-w-[460px]">
      {[0, 0.5, 1].map((tick) => (
        <g key={tick}>
          <line x1={x(tick)} x2={x(tick)} y1={PAD.top} y2={height - PAD.bottom} className="stroke-border" />
          <text x={x(tick)} y={height - 6} textAnchor="middle" className="fill-muted-foreground text-[10px]">
            {(tick * 100).toFixed(0)}%
          </text>
        </g>
      ))}
      {table.map((row, index) => {
        const y = PAD.top + ROW * index + ROW / 2
        return (
          <g key={row.task_id}>
            <text x={PAD.left - 8} y={y + 3} textAnchor="end" className="fill-foreground text-[10px]">
              {row.task_id}
            </text>
            {condition === 'all' && (
              <line
                x1={x(row.none)}
                x2={x(row.strong)}
                y1={y}
                y2={y}
                className={row.rose ? 'stroke-blue-600' : 'stroke-red-600'}
              />
            )}
            {shown.map((c) => (
              <circle key={c} cx={x(row[c])} cy={y} r={4} className={DOT[c]}>
                <title>{`${row.task_id}, ${NAME[c]}: ${(row[c] * 100).toFixed(0)}%`}</title>
              </circle>
            ))}
          </g>
        )
      })}
    </svg>
  )
}

function verdictOf(passes: boolean | null) {
  return passes === null ? 'not judged' : passes ? 'met' : 'not met'
}

export function Q2Panel({ q2, condition }: { q2: Q2; condition: Condition | 'all' }) {
  const { manipulation, state } = q2
  return (
    <Card>
      <CardHeader>
        <CardTitle>Planted behaviour and Q2</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1">
          <p className="text-muted-foreground">Criterion: {q2.criterion}</p>
          <p className="flex flex-wrap items-center gap-2">
            <Badge variant={q2.passes === null ? 'secondary' : q2.passes ? 'default' : 'destructive'}>
              {verdictOf(q2.passes)}
            </Badge>
            <span>
              {q2.tasks_run} of {q2.tasks} tasks have run. Each task has two runs per condition, so one
              point rests on four runs, and this is an existence check and not an estimate. Blue lines
              mark a task where the instruction raised the share, red where it did not.
            </span>
          </p>
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="space-y-2">
            <h3 className="font-medium">
              Manipulation check: shell steps that repeat an earlier command{' '}
              <Badge variant="outline">{verdictOf(manipulation.passes)}</Badge>
            </h3>
            <Dots table={manipulation.table} label="Repeat share per task" condition={condition} />
            <p className="text-muted-foreground">
              Rose on {manipulation.rises} of {q2.tasks_run} tasks, needs {manipulation.needs}.
            </p>
          </div>
          <div className="space-y-2">
            <h3 className="font-medium">
              Repeating state: share of steps in it{' '}
              <Badge variant="outline">{verdictOf(state ? state.passes : false)}</Badge>
            </h3>
            {state ? (
              <>
                <Dots table={state.table} label="Repeating state share per task" condition={condition} />
                <p className="text-muted-foreground">
                  State {state.state + 1}, where {(state.repeat_share * 100).toFixed(0)}% of the natural
                  steps repeat a command. Rose on {state.rises} of {state.table.length} tasks, needs{' '}
                  {state.needs}.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">
                No discovered state is mostly repeats, so the planted behaviour is not detected.
              </p>
            )}
          </div>
        </div>
        <p className="flex flex-wrap items-center gap-x-4 text-muted-foreground">
          {(['none', 'strong'] as const).map((c) => (
            <span key={c} className="flex items-center gap-1.5">
              <svg width="10" height="10" aria-hidden="true">
                <circle cx="5" cy="5" r="4" className={DOT[c]} />
              </svg>
              {NAME[c]}
            </span>
          ))}
        </p>
      </CardContent>
    </Card>
  )
}
