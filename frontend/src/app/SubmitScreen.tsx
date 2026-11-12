import { SubmitPage } from '../pages/SubmitPage';
import { submitProps } from './submit';
import type { SubmitBootstrap } from './submit';
import type { AppConfig } from './config';

export default function SubmitScreen({ config, submission }: { config: AppConfig; submission: SubmitBootstrap }) {
  const props = submitProps(config, submission);
  if (submission.sent) return <section className="submit-page"><h1>{props.messages.successTitle}</h1>
    <p>{props.messages.successBody}</p><a href="/">{props.messages.backHome}</a></section>;
  return <>{submission.conflict && <p role="alert">{props.messages.conflictTitle}. {props.messages.errorConflictCancelled}</p>}<SubmitPage {...props} /></>;
}
