import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { STATE_FILL } from '@/palette'
import type { Difference, Q1 } from '@/site'

function range({ estimate, low, high }: Difference) {
  return `${estimate.toFixed(2)} (${low.toFixed(2)} to ${high.toFixed(2)})`
}

function share(value: number) {
  return `${(value * 100).toFixed(0)}%`
}

export function Q1Panel({ q1 }: { q1: Q1 }) {
  const { labeler, q1: result, states } = q1
  return (
    <Card>
      <CardHeader>
        <CardTitle>Behaviour names and Q1</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1">
          <p className="text-muted-foreground">Criterion: {result.criterion}</p>
          <p className="flex flex-wrap items-center gap-2">
            <Badge variant={result.passes ? 'default' : 'destructive'}>
              {result.passes ? 'met' : 'not met'}
            </Badge>
            <span>
              NMI on {result.held_out_steps} held-out steps from {result.held_out_runs} runs: HMM{' '}
              {result.nmi.hmm.toFixed(2)}, GMM {result.nmi.gmm.toFixed(2)}, majority label{' '}
              {result.nmi.majority.toFixed(2)}.
            </span>
          </p>
          <p>
            HMM minus GMM {range(result.differences.hmm_minus_gmm)}; HMM minus majority{' '}
            {range(result.differences.hmm_minus_majority)}. Ranges are 95% bootstrap over runs.
          </p>
          <p className="text-muted-foreground">
            Labeler agreement with the human sample: kappa{' '}
            {labeler.kappa === null ? 'not measured' : labeler.kappa.toFixed(2)} on {labeler.compared_steps}{' '}
            steps, bar {labeler.bar}. Labels used: {labeler.labels_used}.
          </p>
        </div>
        <table className="w-full text-left">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-normal">State</th>
              <th className="py-1 pr-3 font-normal">Name</th>
              <th className="py-1 pr-3 font-normal">Labeled steps</th>
              <th className="py-1 font-normal">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {states.map((state) => (
              <tr key={state.state} className="border-t">
                <td className="py-1 pr-3">
                  <span className="flex items-center gap-1.5">
                    <svg width="10" height="10" aria-hidden="true">
                      <rect width="10" height="10" rx="1" className={STATE_FILL[state.state]} />
                    </svg>
                    {state.state + 1}
                  </span>
                </td>
                <td className="py-1 pr-3 font-medium">{state.name}</td>
                <td className="py-1 pr-3">{state.labeled_steps}</td>
                <td className="py-1 text-muted-foreground">
                  {Object.entries(state.intents)
                    .map(([intent, value]) => `${intent} ${share(value)}`)
                    .join(', ')}
                  {'; '}
                  {Object.entries(state.facts)
                    .map(([fact, value]) => `${fact.replace('_', ' ')} ${share(value)}`)
                    .join(', ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
