// A step is addressed by its run and its position, and both views read the same reference.
export interface StepRef {
  runId: string
  step: number
}

export const sameStep = (a: StepRef | null, b: StepRef | null) =>
  a !== null && b !== null && a.runId === b.runId && a.step === b.step
