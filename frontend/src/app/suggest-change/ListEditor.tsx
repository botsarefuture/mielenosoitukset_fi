import { useEffect, useState } from 'react';

export default function ListEditor({ name, label, initial, help, placeholder }: {
  name: 'tags' | 'route' | 'organizers'; label: string; initial: string; help: string; placeholder: string;
}) {
  const [enhanced, setEnhanced] = useState(false);
  const [value, setValue] = useState(initial);
  const [draft, setDraft] = useState('');
  useEffect(() => setEnhanced(true), []);
  const separator = name === 'organizers' ? '\n' : ', ';
  const split = (text: string) => text.split(name === 'organizers' ? /\r?\n+/ : /[,\n]+/)
    .map(item => name === 'tags' ? item.trim().replace(/^#+/, '').trim() : item.trim()).filter(Boolean);
  const [items, setItems] = useState(() => split(initial));
  const combined = draft.trim() ? [...items, ...split(draft)] : items;
  const add = () => {
    const next = name === 'route' ? combined : [...new Set(combined)];
    setItems(next);
    setDraft('');
  };
  return <div className="suggest-change-field">
    <label htmlFor={enhanced ? `${name}-draft` : name}>{label}</label>
    <textarea id={name} name={name} rows={name === 'organizers' ? 4 : 2} hidden={enhanced}
      value={enhanced ? combined.join(separator) : value} onChange={event => setValue(event.target.value)} aria-describedby={`${name}-help`} />
    {enhanced && <>
      <div className="suggest-change-add">
        <input id={`${name}-draft`} value={draft} placeholder={placeholder} aria-describedby={`${name}-help`}
          onChange={event => setDraft(event.target.value)} onKeyDown={event => {
            if (event.key === 'Enter') { event.preventDefault(); add(); }
          }} />
        <button className="detail-button" type="button" onClick={add}>Lisää</button>
      </div>
      <ul className="suggest-change-items" aria-label={label}>
        {items.map((item, index) => <li key={index}>
          <input value={item} aria-label={`${label}: ${index + 1}`} onChange={event => {
            const next = [...items]; next[index] = event.target.value; setItems(next);
          }} />
          <button className="detail-button detail-button--quiet" type="button" aria-label={`Poista ${item}`}
            onClick={() => setItems(items.filter((_, itemIndex) => itemIndex !== index))}>Poista</button>
        </li>)}
      </ul>
    </>}
    <p id={`${name}-help`} className="suggest-change-help">{help}</p>
  </div>;
}
