import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Interval, Q3b } from '@/site'

function range({ estimate, low, high }: Interval) {
  return `${estimate.toFixed(2)} (${low.toFixed(2)} to ${high.toFixed(2)})`
}

const LINES = [
  ['baseline', 'Counts so far (baseline)', 'stroke-slate-500'],
  ['behaviour', 'Behaviour view', 'stroke-blue-600'],
  ['supervised', 'Supervised predictor', 'stroke-amber-600'],
] as const

const WIDTH = 460
const HEIGHT = 220
const PAD = { left: 40, right: 12, top: 12, bottom: 28 }
// A fixed axis so that the chart stays comparable between exports. AUROC 0.5 is a coin flip.
const Y_MIN = 0.3
const Y_MAX = 0.8

function Chart({ q3b }: { q3b: Q3b }) {
  const ks = q3b.per_k
  const x = (index: number) =>
    PAD.left + ((WIDTH - PAD.left - PAD.right) * (index + 0.5)) / ks.length
  const y = (value: number) =>
    PAD.top + ((Y_MAX - Math.min(Math.max(value, Y_MIN), Y_MAX)) / (Y_MAX - Y_MIN)) * (HEIGHT - PAD.top - PAD.bottom)
  return (
    <svg
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full max-w-[520px]"
      role="img"
      aria-label="AUROC of each predictor from the first k steps"
    >
      {[0.3, 0.4, 0.5, 0.6, 0.7, 0.8].map((tick) => (
        <g key={tick}>
          <line
            x1={PAD.left}
            x2={WIDTH - PAD.right}
            y1={y(tick)}
            y2={y(tick)}
            className={tick === 0.5 ? 'stroke-slate-400' : 'stroke-slate-200'}
          />
          <text x={PAD.left - 6} y={y(tick) + 3} textAnchor="end" className="fill-slate-500 text-[10px]">
            {tick.toFixed(1)}
          </text>
        </g>
      ))}
      {ks.map((entry, index) => (
        <text key={entry.k} x={x(index)} y={HEIGHT - 8} textAnchor="middle" className="fill-slate-500 text-[10px]">
          first {entry.k} steps
        </text>
      ))}
      <polyline
        fill="none"
        strokeDasharray="4 3"
        className="stroke-slate-400"
        points={ks.map((entry, index) => `${x(index)},${y(entry.auroc.length.estimate)}`).join(' ')}
      />
      <text
        x={WIDTH - PAD.right}
        y={y(ks[ks.length - 1].auroc.length.estimate) - 5}
        textAnchor="end"
        className="fill-slate-500 text-[10px]"
      >
        whole-run length (unfair: uses the future)
      </text>
      {LINES.map(([key, , color], line) => (
        <g key={key}>
          <polyline
            fill="none"
            className={color}
            strokeWidth={1.5}
            points={ks.map((entry, index) => `${x(index) + (line - 1) * 8},${y(entry.auroc[key].estimate)}`).join(' ')}
          />
          {ks.map((entry, index) => (
            <g key={entry.k} className={color}>
              <line
                x1={x(index) + (line - 1) * 8}
                x2={x(index) + (line - 1) * 8}
                y1={y(entry.auroc[key].low)}
                y2={y(entry.auroc[key].high)}
              />
              <circle cx={x(index) + (line - 1) * 8} cy={y(entry.auroc[key].estimate)} r={2.5} className="fill-current" />
            </g>
          ))}
        </g>
      ))}
    </svg>
  )
}

export function Q3bPanel({ q3b }: { q3b: Q3b }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Early check on the first k steps and Q3b</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1">
          <p className="text-muted-foreground">Criterion: {q3b.criterion}</p>
          <p className="flex flex-wrap items-center gap-2">
            <Badge variant={q3b.passes ? 'default' : 'destructive'}>{q3b.passes ? 'met' : 'not met'}</Badge>
            <span>
              Of {q3b.natural_runs} natural runs, only those with at least k steps are used. AUROC with 95%
              bootstrap ranges over tasks.
            </span>
          </p>
        </div>
        <Chart q3b={q3b} />
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
          {LINES.map(([key, title, color]) => (
            <span key={key} className="flex items-center gap-1.5">
              <svg width="14" height="6" aria-hidden="true">
                <line x1="0" x2="14" y1="3" y2="3" strokeWidth={2} className={color} />
              </svg>
              {title}
            </span>
          ))}
        </div>
        <table className="w-full text-left">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-normal">First k steps</th>
              <th className="py-1 pr-3 font-normal">Runs (dropped)</th>
              <th className="py-1 pr-3 font-normal">Behaviour minus baseline</th>
              <th className="py-1 pr-3 font-normal">Supervised minus behaviour</th>
              <th className="py-1 font-normal">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {q3b.per_k.map((entry) => (
              <tr key={entry.k} className="border-t">
                <td className="py-1 pr-3">{entry.k}</td>
                <td className="py-1 pr-3">
                  {entry.runs} ({entry.runs_dropped}) from {entry.tasks} tasks
                </td>
                <td className="py-1 pr-3">
                  {range(entry.differences.behaviour_minus_baseline)}
                  {entry.beats_baseline ? '' : ', range includes no gain'}
                </td>
                <td className="py-1 pr-3">
                  {range(entry.differences.supervised_minus_behaviour)}
                  {entry.near_supervised ? '' : ', more than 0.05 apart'}
                </td>
                <td className="py-1">{entry.passes ? 'met' : 'not met'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
