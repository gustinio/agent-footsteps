import { useEffect, useState } from 'react'
import siteUrl from '../../results/site.json?url'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CATEGORY_FILL, STATE_FILL, STATUS_LABEL } from '@/palette'
import { PointCloud } from '@/PointCloud'
import { Q1Panel } from '@/Q1Panel'
import { Ribbon } from '@/Ribbon'
import type { StepRef } from '@/selection'
import { loadSite, type Method, type Site, type ToolCategory } from '@/site'

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

const METHOD_NAME: Record<Method, string> = { hmm: 'Sticky HMM', gmm: 'GMM' }

function StateLegend({ site, method }: { site: Site; method: Method }) {
  const shares = site.meta.segmentation.state_shares[method]
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
      {shares.map((share, state) => (
        <span key={state} className="flex items-center gap-1.5">
          <svg width="10" height="10" aria-hidden="true">
            <rect width="10" height="10" rx="1" className={STATE_FILL[state]} />
          </svg>
          state {state + 1} ({(share * 100).toFixed(0)}%)
        </span>
      ))}
    </div>
  )
}

export default function App() {
  const [site, setSite] = useState<Site | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showOutcome, setShowOutcome] = useState(false)
  const [method, setMethod] = useState<Method>('hmm')
  const [colorByState, setColorByState] = useState(true)
  const [selected, setSelected] = useState<StepRef | null>(null)
  const [hovered, setHovered] = useState<StepRef | null>(null)

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

  const hasOutcome = site.runs.some((run) => run.outcome !== undefined)
  const selectedRun = site.runs.find((run) => run.run_id === selected?.runId)
  const selectedStep = selectedRun && selected ? selectedRun.steps[selected.step] : undefined

  return (
    <main className="mx-auto max-w-[1400px] space-y-4 p-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Agent footsteps</h1>
        <p className="text-sm text-muted-foreground">
          One row per run, one cell per step. The {site.meta.planted_runs} planted runs come first, then a
          sample of the {site.meta.segmentation.natural_runs} natural runs (of {site.meta.runs_in_dataset} in{' '}
          {site.meta.dataset} at revision {site.meta.revision.slice(0, 8)}). States are fit on the natural
          runs only; the planted runs are placed on them.
        </p>
      </header>
      <div className="flex flex-wrap items-center gap-2">
        {(Object.keys(METHOD_NAME) as Method[]).map((name) => (
          <Button
            key={name}
            variant={method === name ? 'default' : 'outline'}
            size="sm"
            aria-pressed={method === name}
            onClick={() => setMethod(name)}
          >
            {METHOD_NAME[name]}
          </Button>
        ))}
        <Button
          variant="outline"
          size="sm"
          aria-pressed={colorByState}
          onClick={() => setColorByState(!colorByState)}
        >
          Ribbons colored by {colorByState ? 'state' : 'tool'}
        </Button>
        {hasOutcome && (
          <Button
            variant={showOutcome ? 'default' : 'outline'}
            size="sm"
            aria-pressed={showOutcome}
            onClick={() => setShowOutcome(!showOutcome)}
          >
            Show pass or fail
          </Button>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-[minmax(0,460px)_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Step point cloud</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <PointCloud
              runs={site.runs}
              method={method}
              selected={selected}
              hovered={hovered}
              onSelect={setSelected}
              onHover={setHovered}
            />
            <p className="text-xs text-muted-foreground">
              Position is a two-dimensional view of the step features, with a small repeatable offset so
              identical steps do not stack. The states were not found from this view.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Selected step</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {selectedRun && selectedStep && selected ? (
              <dl className="grid grid-cols-[8rem_1fr] gap-y-1">
                <dt className="text-muted-foreground">Run</dt>
                <dd className="font-mono">{selectedRun.task_id}</dd>
                <dt className="text-muted-foreground">Step</dt>
                <dd>
                  {selected.step + 1} of {selectedRun.n_steps}
                </dd>
                <dt className="text-muted-foreground">Tool</dt>
                <dd>{selectedStep.tool_category}</dd>
                <dt className="text-muted-foreground">Result</dt>
                <dd>{STATUS_LABEL[selectedStep.result_status]}</dd>
                <dt className="text-muted-foreground">{METHOD_NAME[method]} state</dt>
                <dd>{(method === 'hmm' ? selectedStep.hmm_state : selectedStep.gmm_state) + 1}</dd>
                {showOutcome && selectedRun.outcome && (
                  <>
                    <dt className="text-muted-foreground">Outcome</dt>
                    <dd>{selectedRun.outcome}</dd>
                  </>
                )}
              </dl>
            ) : (
              <p className="text-muted-foreground">Click a point or a ribbon cell to select a step.</p>
            )}
            <StateLegend site={site} method={method} />
            <Legend />
          </CardContent>
        </Card>
      </div>
      {site.meta.q1 && <Q1Panel q1={site.meta.q1} />}
      <Card>
        <CardHeader>
          <CardTitle>Run ribbons</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 overflow-x-auto">
          {site.runs.map((run) => (
            <div key={run.run_id} className="flex items-center gap-3">
              <div className="sticky left-0 z-10 flex w-56 shrink-0 items-center gap-2 bg-card text-xs">
                <span className="font-mono" title={run.run_id}>
                  {run.source === 'planted' ? run.task_id : run.run_id.slice(0, 8)}
                </span>
                {run.condition && <Badge variant="outline">{run.condition}</Badge>}
                <Badge variant="secondary">{run.n_steps} steps</Badge>
                {showOutcome && run.outcome && (
                  <Badge variant={run.outcome === 'pass' ? 'default' : 'destructive'}>
                    {run.outcome}
                  </Badge>
                )}
                <span className="truncate text-muted-foreground" title={run.model}>
                  {run.agent}
                </span>
              </div>
              <Ribbon
                run={run}
                colorBy={colorByState ? method : null}
                selected={selected}
                hovered={hovered}
                onSelect={setSelected}
                onHover={setHovered}
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </main>
  )
}
