import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Interval, Q4 } from '@/site'

function range({ estimate, low, high }: Interval) {
  return `${estimate.toFixed(2)} (${low.toFixed(2)} to ${high.toFixed(2)})`
}

export function Q4Panel({ q4 }: { q4: Q4 }) {
  const verdict = q4.passes === null ? 'not judged' : q4.passes ? 'met' : 'not met'
  return (
    <Card>
      <CardHeader>
        <CardTitle>Unseen tasks and Q4</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="space-y-1">
          <p className="text-muted-foreground">Criterion: {q4.criterion}</p>
          <p className="flex flex-wrap items-center gap-2">
            <Badge variant={q4.passes === null ? 'secondary' : q4.passes ? 'default' : 'destructive'}>
              {verdict}
            </Badge>
            <span>
              A negative drop means unseen tasks scored higher. A drop that is small because both scores sit
              near 0.5 shows that nothing was lost, not that something was learned.
            </span>
          </p>
        </div>
        <table className="w-full text-left">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 pr-3 font-normal">Measure</th>
              <th className="py-1 pr-3 font-normal">Seen tasks</th>
              <th className="py-1 pr-3 font-normal">Unseen tasks</th>
              <th className="py-1 pr-3 font-normal">Drop (seen minus unseen)</th>
              <th className="py-1 font-normal">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {q4.auroc.map((stage) => (
              <tr key={stage.stage} className="border-t">
                <td className="py-1 pr-3">AUROC, behaviour view, {stage.stage}</td>
                <td className="py-1 pr-3">{stage.seen.toFixed(2)}</td>
                <td className="py-1 pr-3">{stage.unseen.toFixed(2)}</td>
                <td className="py-1 pr-3">{range(stage.drop)}</td>
                <td className="py-1">{stage.passes ? 'met' : 'not met'}</td>
              </tr>
            ))}
            {q4.agreement ? (
              <tr className="border-t">
                <td className="py-1 pr-3">NMI of the states with the step labels</td>
                <td className="py-1 pr-3">{q4.agreement.seen.toFixed(2)}</td>
                <td className="py-1 pr-3">{q4.agreement.unseen.toFixed(2)}</td>
                <td className="py-1 pr-3">{range(q4.agreement.drop)}</td>
                <td className="py-1">{q4.agreement.passes ? 'met' : 'not met'}</td>
              </tr>
            ) : (
              <tr className="border-t text-muted-foreground">
                <td className="py-1" colSpan={5}>
                  Agreement is not measured until the human sample is labeled.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
