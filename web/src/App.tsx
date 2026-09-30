import { useEffect, useState } from 'react'
import siteUrl from '../../results/site.json?url'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CATEGORY_FILL } from '@/palette'
import { Ribbon } from '@/Ribbon'
import { loadSite, type Site, type ToolCategory } from '@/site'

const CATEGORIES = Object.keys(CATEGORY_FILL) as ToolCategory[]

function Legend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
      {CATEGORIES.map((category) => (
        <span key={category} className="flex items-center gap-1.5">
          <svg width="10" height="10" aria-hidden="true">
            <rect width="10" height="10" rx="1" className={CATEGORY_FILL[category]} />
          </svg>
          {category}
        </span>
      ))}
      <span className="flex items-center gap-1.5">
        <svg width="10" height="13" aria-hidden="true">
          <rect width="10" height="10" rx="1" className="fill-slate-400" />
          <rect y="10" width="10" height="3" rx="1" className="fill-red-600" />
        </svg>
        error result
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="10" height="10" aria-hidden="true">
          <rect width="10" height="10" rx="1" className="fill-slate-400" opacity={0.4} />
        </svg>
        no result
      </span>
    </div>
  )
}

export default function App() {
  const [site, setSite] = useState<Site | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadSite(siteUrl)
      .then(setSite)
      .catch((reason: Error) => setError(reason.message))
  }, [])

  if (error) {
    return <p className="p-6 text-destructive">{error}</p>
  }
  if (!site) {
    return <p className="p-6 text-muted-foreground">Loading</p>
  }

  return (
    <main className="mx-auto max-w-[1400px] space-y-4 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Agent footsteps</h1>
        <p className="text-sm text-muted-foreground">
          One row per run, one cell per step. Dataset {site.meta.dataset} at revision{' '}
          {site.meta.revision.slice(0, 8)}, a sample of its {site.meta.runs_in_dataset} runs.
        </p>
      </header>
      <Legend />
      <Card>
        <CardHeader>
          <CardTitle>Run ribbons</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 overflow-x-auto">
          {site.runs.map((run) => (
            <div key={run.run_id} className="flex items-center gap-3">
              <div className="sticky left-0 z-10 flex w-56 shrink-0 items-center gap-2 bg-card text-xs">
                <span className="font-mono">{run.run_id.slice(0, 8)}</span>
                <Badge variant="secondary">{run.n_steps} steps</Badge>
                <span className="truncate text-muted-foreground" title={run.model}>
                  {run.agent}
                </span>
              </div>
              <Ribbon run={run} />
            </div>
          ))}
        </CardContent>
      </Card>
    </main>
  )
}
