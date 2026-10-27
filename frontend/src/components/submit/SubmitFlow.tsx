import { useSyncExternalStore } from 'react';

/** The existing form controller retains fields, validation, imports and POSTs. */
type FormWindow = Window & typeof globalThis & {
  nextPage?: () => void;
  previousPage?: () => void;
  chooseImport?: () => void;
  chooseManual?: () => void;
};
export type SubmitFlowProps = {
  steps: string[];
  previous: string;
  next: string;
  importTitle: string;
  importDescription: string;
  manualTitle: string;
  manualDescription: string;
};
const controller = () => window as FormWindow;
function subscribe(listener: () => void) {
  window.addEventListener('submit:stepchange', listener);
  return () => window.removeEventListener('submit:stepchange', listener);
}
function currentStep() {
  const number = Number(document.querySelector('.submit-page .form-page.active')?.id.replace('page-', ''));
  return number >= 1 && number <= 6 ? number : 1;
}

export function SubmitProgress({ steps }: SubmitFlowProps) {
  // Read the active page on mount too: a saved draft may restore before React loads.
  const step = useSyncExternalStore(subscribe, currentStep, () => 1);
  return <>
    <p className="submit-step-status" aria-live="polite" aria-atomic="true">
      <strong>{steps[step - 1]}</strong><span>{step} / {steps.length}</span>
    </p>
    <ol className="progress-steps">
      {steps.map((label, index) => <li key={label} data-page={index + 1}
        className={`progress-step${index + 1 === step ? ' active' : index + 1 < step ? ' completed' : ''}`}
        aria-current={index + 1 === step ? 'step' : undefined} aria-label={label}>
        <span className="step-circle" aria-hidden="true">{index + 1 < step ? <i className="fa-solid fa-check" /> : index + 1}</span>
        <span className="step-label">{label}</span>
      </li>)}
    </ol>
  </>;
}
function StepButton({ direction, label }: { direction: 'previous' | 'next'; label: string }) {
  const previous = direction === 'previous';
  return <button type="button" className={`btn ${previous ? 'btn-secondary' : 'btn-primary'}`}
    onClick={() => previous ? controller().previousPage?.() : controller().nextPage?.()}>
    {previous && <i className="fa-solid fa-arrow-left" aria-hidden="true" />}
    {label}
    {!previous && <i className="fa-solid fa-arrow-right" aria-hidden="true" />}
  </button>;
}
export function SubmitNavigation({ previous, next }: SubmitFlowProps) {
  return <><StepButton direction="previous" label={previous} /><StepButton direction="next" label={next} /></>;
}
export function SubmitBack({ previous }: SubmitFlowProps) {
  return <StepButton direction="previous" label={previous} />;
}
export function SubmitChoices(props: SubmitFlowProps) {
  return <>
    <button type="button" className="import-choice-card" onClick={() => controller().chooseImport?.()}>
      <i className="import-choice-icon fa-brands fa-facebook" aria-hidden="true" />
      <span className="import-choice-title">{props.importTitle}</span>
      <span className="import-choice-desc">{props.importDescription}</span>
    </button>
    <button type="button" className="import-choice-card" onClick={() => controller().chooseManual?.()}>
      <i className="import-choice-icon fa-solid fa-pen" aria-hidden="true" />
      <span className="import-choice-title">{props.manualTitle}</span>
      <span className="import-choice-desc">{props.manualDescription}</span>
    </button>
  </>;
}
