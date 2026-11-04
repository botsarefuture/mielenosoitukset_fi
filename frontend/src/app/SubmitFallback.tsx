import type { SubmitPageProps } from '../components/submit/types';

/** React-owned no-JavaScript form, using the same Go POST contract. */
export function SubmitFallback(props: SubmitPageProps) {
  const text = props.messages;
  const fields = [
    ['title', text.titleLabel, 'text'], ['tags', text.tagsLabel, 'text'],
    ['date', text.dateLabel, 'date'], ['start_time', text.startTimeLabel, 'time'],
    ['address', text.addressLabel, 'text'], ['submitter_role', text.roleLabel, 'text'],
    ['submitter_name', text.nameLabel, 'text'], ['submitter_email', text.emailLabel, 'email'],
  ];
  return <article className="submit-page"><nav aria-label="Sivun navigaatio"><a href={props.homeUrl}>Etusivu</a> / <a href={props.guidesUrl}>Ohjeet</a></nav>
    <h1>{text.introTitle}</h1><p>{text.introLead}</p>
    <form method="post" action={props.action} encType="multipart/form-data" className="user-form">
      <input type="hidden" name="submission_token" value={props.token} />
      <input type="hidden" name="default_language" value={props.defaultLanguage} />
      <div className="form-container">{fields.map(([name, label, type]) => <div className="form-group" key={name}>
        <label htmlFor={`plain-${name}`}>{label} *</label><input id={`plain-${name}`} name={name} type={type} required /></div>)}
        <div className="form-group"><label htmlFor="plain-type">{text.typeLabel}</label><select name="type" id="plain-type" required>
          {Object.entries(text.typeOption).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></div>
        <div className="form-group"><label htmlFor="plain-city">{text.cityLabel}</label><select name="city" id="plain-city" required>
          {props.cities.map(city => <option key={city}>{city}</option>)}</select></div>
        <div className="form-group"><label htmlFor="plain-description">{text.descriptionLabel}</label><textarea name="description" id="plain-description" /></div>
        <div className="form-group"><label htmlFor="plain-organizer">{text.organizerLabel}</label><input name="organizer_name_1" id="plain-organizer" /></div>
        <div className="checkbox-group"><input id="plain-terms" type="checkbox" name="accept_terms" value="1" required />
          <label htmlFor="plain-terms">{text.acceptTermsPrefix} <a href={props.termsUrl}>{text.termsLink}</a> {text.acceptTermsAnd} <a href={props.privacyUrl}>{text.privacyLink}</a>.</label></div>
        <button type="submit" className="btn btn-success">{text.submit}</button>
      </div>
    </form>
  </article>;
}
