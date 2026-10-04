import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Interval, Q3a, SignalEntry, StateName } from '@/site'

function range({ estimate, low, high }: Interval) {
  return `${estimate.toFixed(2)} (${low.toFixed(2)} to ${high.toFixed(2)})`
}

const VIEWS = [
  ['length', 'Run length alone'],
  ['behaviour', 'Behaviour profile'],
  ['supervised', 'Supervised predictor'],
] as const

// A signal name holds 1-based state numbers, such as "state 3 share, last third" or "1 to 6".
// The state names from Q1, when there are any, are added next to the numbers.
function withNames(name: string, names?: StateName[]) {
  if (!names) return name
  const label = (n: string) => names[Number(n) - 1]?.name
  const move = name.match(/^(\d+) to (\d+)$/)
  if (move) return `${name} (${label(move[1])} to ${label(move[2])})`
  const share = name.match(/^state (\d+) /)
  return share ? `${name} (${label(share[1])})` : name
}

function SignalTable({
  title,
  entries,
  names,
}: {
  title: string
  entries: SignalEntry[]
  names?: StateName[]
}) {
  return (
    <div className="space-y-1">
      <p className="font-medium">{title}</p>
      <table className="w-full text-left">
        <tbody>
          {entries.map((entry) => {
            const effect = entry.coefficient ?? entry.auroc ?? 0
            return (
              <tr key={entry.name} className="border-t">
                <td className="py-1 pr-3">{withNames(entry.name, names)}</td>
                <td className="py-1 pr-3">
                  {effect.toFixed(2)} ({entry.low.toFixed(2)} to {entry.high.toFixed(2)})
                </td>
                <td className="py-1 text-muted-foreground">
                  {entry.clear ? `more in ${entry.more_in} runs` : 'range includes no effect'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function Q3aPanel({ q3a, names }: { q3a: Q3a; names?: StateName[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Whole-run behaviour profile and Q3a</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1">
          <p className="text-muted-foreground">Criterion: {q3a.criterion}</p>
          <p className="flex flex-wrap items-center gap-2">
            <Badge variant={q3a.passes ? 'default' : 'destructive'}>
              {q3a.passes ? 'met' : 'not met'}
            </Badge>
            <span>
              {q3a.runs} runs from {q3a.tasks} tasks, {(q3a.failing_share * 100).toFixed(0)}% failing. Ranges are 95%
              bootstrap over tasks.
            </span>
          </p>
        </div>
        <table className="w-full text-left">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-normal">Predictor</th>
              <th className="py-1 font-normal">AUROC</th>
            </tr>
          </thead>
          <tbody>
            {VIEWS.map(([key, title]) => (
              <tr key={key} className="border-t">
                <td className="py-1 pr-3">{title}</td>
                <td className="py-1">{range(q3a.auroc[key])}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p>
          Profile minus run length {range(q3a.differences.behaviour_minus_length)}
          {q3a.beats_length ? ', larger than its range.' : ', not larger than its range.'} Supervised minus profile{' '}
          {range(q3a.differences.supervised_minus_behaviour)}
          {q3a.near_supervised ? ', within 0.05.' : ', more than 0.05 apart.'}
        </p>
        <SignalTable
          title="Profile entries most tied to failure (standardized coefficient)"
          entries={q3a.signal.profile}
          names={names}
        />
        <SignalTable
          title={`State-to-state moves most tied to failure (AUROC of the move rate alone, ${q3a.signal.moves_tested} tested)`}
          entries={q3a.signal.moves}
          names={names}
        />
      </CardContent>
    </Card>
  )
}
