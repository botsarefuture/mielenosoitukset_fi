import { Fragment, type ReactNode } from 'react';

function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^\s)]+\)|https?:\/\/[^\s<>]+|\n)/g).map((part, index) => {
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part);
    if (link) return <a key={index} href={link[2]} target="_blank" rel="noopener noreferrer">{link[1]}</a>;
    if (/^https?:\/\//.test(part)) return <a key={index} href={part} target="_blank" rel="noopener noreferrer">{part}</a>;
    if (part.startsWith('**')) return <strong key={index}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('*')) return <em key={index}>{part.slice(1, -1)}</em>;
    if (part.startsWith('`')) return <code key={index}>{part.slice(1, -1)}</code>;
    return part === '\n' ? <br key={index} /> : <Fragment key={index}>{part}</Fragment>;
  });
}

export default function MarkdownPreview({ value }: { value: string }) {
  const lines = value.trim().split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index].trim();
    if (!line) { index++; continue; }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const Heading = `h${heading[1].length}` as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
      blocks.push(<Heading key={index}>{inline(heading[2])}</Heading>);
      index++;
      continue;
    }
    const marker = /^>\s+/.test(line) ? /^>\s+/ : /^-\s+/.test(line) ? /^-\s+/ : /^\d+\.\s+/.test(line) ? /^\d+\.\s+/ : null;
    if (marker) {
      const start = index;
      const items: string[] = [];
      while (index < lines.length && marker.test(lines[index].trim())) items.push(lines[index++].trim().replace(marker, ''));
      if (line.startsWith('>')) blocks.push(<blockquote key={start}>{inline(items.join('\n'))}</blockquote>);
      else {
        const List = line.startsWith('-') ? 'ul' : 'ol';
        blocks.push(<List key={start}>{items.map((item, itemIndex) => <li key={itemIndex}>{inline(item)}</li>)}</List>);
      }
      continue;
    }
    const start = index;
    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim() && !/^(#{1,6}\s+|>\s+|-\s+|\d+\.\s+)/.test(lines[index].trim())) paragraph.push(lines[index++]);
    blocks.push(<p key={start}>{inline(paragraph.join('\n'))}</p>);
  }
  return <section className="suggest-change-preview" aria-label="Esikatselu">
    <h3>Esikatselu</h3>{value.trim() ? blocks : <p>Kirjoita kuvaus, niin näet sen tässä.</p>}
  </section>;
}
