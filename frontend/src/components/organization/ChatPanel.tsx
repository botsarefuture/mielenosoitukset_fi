import { useEffect, useRef, useState } from 'react';

type Friend = { _id: string; username: string; displayname: string; profile_picture?: string };
type Message = { _id: string; sender_id: string; recipient_id: string; type: string; content?: string; read: boolean; extra?: { media_url?: string; demo_id?: string; demo_title?: string } };
type Events = { connect: undefined; connect_error: unknown; disconnect: unknown; error: unknown; friends_list: { friends: Friend[] }; chat_history: { messages: Message[] }; new_message: { message: Message }; message_read: { message_id: string } };
type Socket = { on<K extends keyof Events>(event: K, callback: (data: Events[K]) => void): void; emit(event: string, data?: unknown): void; disconnect(): void };
type SocketOptions = { withCredentials: boolean; reconnectionDelay?: number; reconnectionDelayMax?: number; randomizationFactor?: number };
type SocketWindow = Window & { io?: (options: SocketOptions) => Socket };

let client: Promise<NonNullable<SocketWindow['io']>> | undefined;
function loadClient() {
  const ready = (window as SocketWindow).io;
  if (ready) return Promise.resolve(ready);
  if (!client) client = new Promise<NonNullable<SocketWindow['io']>>((resolve, reject) => {
    const script = document.createElement('script');
    const fail = () => { clearTimeout(timer); script.remove(); client = undefined; reject(new Error('Socket.IO unavailable')); };
    const timer = window.setTimeout(fail, 10000);
    script.src = 'https://cdn.socket.io/4.7.2/socket.io.min.js';
    script.async = true;
    script.onerror = fail;
    script.onload = () => { const io = (window as SocketWindow).io; if (!io) return fail(); clearTimeout(timer); resolve(io); };
    document.head.append(script);
  });
  return client;
}

function safeMedia(value?: string) {
  if (!value || /[\u0000-\u0020\\]/.test(value)) return undefined;
  try { const url = new URL(value, window.location.origin); return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined; } catch { return undefined; }
}

function Invitation({ message }: { message: Message }) {
  const [state, setState] = useState<'idle' | 'pending' | 'done' | 'error'>('idle');
  const active = useRef<AbortController | null>(null);
  useEffect(() => () => { active.current?.abort(); active.current = null; }, []);
  const accept = async () => {
    const id = message.extra?.demo_id;
    if (!id || active.current) return;
    const controller = new AbortController(); active.current = controller; setState('pending');
    const timer = window.setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(`/api/demonstrations/${encodeURIComponent(id)}/attending`, { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ attending: true }), signal: controller.signal });
      const data = await response.json() as { attending?: boolean };
      if (!response.ok || response.redirected || !data.attending) throw new Error('Invitation failed');
      setState('done');
    } catch { if (active.current === controller) setState('error'); }
    finally { clearTimeout(timer); if (active.current === controller) active.current = null; }
  };
  return <div className="chat-invitation">kutsui sinut mielenosoitukseen ”{message.extra?.demo_title}”<br /><button type="button" disabled={!message.extra?.demo_id || state === 'pending' || state === 'done'} onClick={() => void accept()}>{state === 'done' ? 'Hyväksytty ✅' : state === 'pending' ? 'Hyväksytään…' : 'Hyväksy kutsu'}</button>{state === 'error' && <span role="alert">Kutsun hyväksyminen epäonnistui. Yritä uudelleen.</span>}</div>;
}

export default function ChatPanel({ onClose }: { onClose: () => void }) {
  const [friends, setFriends] = useState<Friend[]>([]);
  const [selected, setSelected] = useState('');
  const [messages, setMessages] = useState<Record<string, Message[]>>({});
  const [draft, setDraft] = useState('');
  const [error, setError] = useState('');
  const [status, setStatus] = useState<'connecting' | 'ready' | 'loading' | 'sending' | 'error'>('connecting');
  const [attempt, setAttempt] = useState(0);
  const socket = useRef<Socket | null>(null);
  const friendMap = useRef<Friend[]>([]);
  const selectedRef = useRef('');
  const pending = useRef('');
  const timer = useRef<number | undefined>(undefined);
  const sendTimer = useRef<number | undefined>(undefined);
  const pendingSend = useRef<{ recipient: string; content: string } | null>(null);
  const close = useRef<HTMLButtonElement>(null);
  const history = useRef<HTMLDivElement>(null);
  const requestHistory = (username: string) => {
    if (!socket.current || pending.current) return;
    pending.current = username; setStatus('loading');
    timer.current = window.setTimeout(() => { socket.current?.disconnect(); setError('Viestien lataaminen epäonnistui. Yritä uudelleen.'); setStatus('error'); }, 10000);
    socket.current.emit('load_messages', { friend_username: username });
  };
  useEffect(() => {
    close.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);
  useEffect(() => {
    let stopped = false;
    setError(''); setStatus('connecting'); pending.current = ''; pendingSend.current = null;
    const failure = () => { if (!stopped) { clearTimeout(timer.current); clearTimeout(sendTimer.current); setError('Viestiyhteys ei toimi. Yritä uudelleen.'); setStatus('error'); } };
    timer.current = window.setTimeout(failure, 12000);
    void loadClient().then(io => {
      if (stopped) return;
      // Gentle, jittered reconnects: after a server restart every open tab would
      // otherwise reconnect at once and trip Apache's mod_evasive limits (#640).
      const connection = io({ withCredentials: true, reconnectionDelay: 2000, reconnectionDelayMax: 60000, randomizationFactor: 0.5 }); socket.current = connection;
      connection.on('connect', () => { connection.emit('get_friends'); });
      connection.on('connect_error', failure);
      connection.on('disconnect', failure);
      connection.on('error', failure);
      connection.on('friends_list', ({ friends: list }) => {
        clearTimeout(timer.current); friendMap.current = list; setFriends(list); setError(''); setStatus('ready');
        if (selectedRef.current && list.some(friend => friend.username === selectedRef.current)) requestHistory(selectedRef.current);
      });
      connection.on('chat_history', ({ messages: list }) => {
        const username = pending.current;
        if (!username) return;
        clearTimeout(timer.current); pending.current = '';
        setMessages(previous => ({ ...previous, [username]: list }));
        if (username === selectedRef.current) list.filter(message => !message.read && friendMap.current.some(friend => friend._id === message.sender_id)).forEach(message => connection.emit('mark_read', { message_id: message._id }));
        setStatus('ready');
        if (selectedRef.current !== username) requestHistory(selectedRef.current);
      });
      connection.on('new_message', ({ message }) => {
        const friend = friendMap.current.find(item => item._id === message.sender_id || item._id === message.recipient_id);
        if (!friend) return;
        const incoming = friend._id === message.sender_id;
        setMessages(previous => { const list = previous[friend.username] || []; return { ...previous, [friend.username]: list.some(item => item._id === message._id) ? list : [...list, message] }; });
        if (incoming && friend.username === selectedRef.current) connection.emit('mark_read', { message_id: message._id });
        const sent = pendingSend.current;
        if (!incoming && sent?.recipient === friend.username && sent.content === message.content) { clearTimeout(sendTimer.current); pendingSend.current = null; setDraft(value => value.trim() === sent.content ? '' : value); setStatus(pending.current ? 'loading' : 'ready'); }
      });
      connection.on('message_read', ({ message_id }) => setMessages(previous => Object.fromEntries(Object.entries(previous).map(([username, list]) => [username, list.map(message => message._id === message_id ? { ...message, read: true } : message)]))));
    }).catch(failure);
    return () => { stopped = true; clearTimeout(timer.current); clearTimeout(sendTimer.current); socket.current?.disconnect(); socket.current = null; pending.current = ''; };
  }, [attempt]);
  useEffect(() => { if (history.current) history.current.scrollTop = history.current.scrollHeight; }, [messages, selected]);
  const select = (username: string) => { selectedRef.current = username; setSelected(username); setDraft(''); requestHistory(username); };
  const send = () => {
    if (!draft.trim() || !selected || status !== 'ready') return;
    pendingSend.current = { recipient: selected, content: draft.trim() };
    setStatus('sending'); socket.current?.emit('send_message', pendingSend.current);
    sendTimer.current = window.setTimeout(() => { setError('Viestin lähetys jäi vahvistamatta. Tarkista keskustelu ennen uutta lähetystä.'); setStatus('error'); }, 10000);
  };
  return <section id="chat-widget" role="dialog" aria-labelledby="organization-chat-title">
    <header><span id="organization-chat-title">Viestit</span><button ref={close} id="chat-close" type="button" onClick={onClose} aria-label="Sulje viestit">✕</button></header>
    {error && <div className="chat-error" role="alert">{error} <button type="button" onClick={() => setAttempt(value => value + 1)}>Yritä uudelleen</button></div>}
    {status === 'connecting' && <p role="status">Yhdistetään…</p>}
    <div className="chat-body"><nav id="friends-list" aria-label="Ystävät">{friends.map(friend => <button type="button" key={friend._id} aria-pressed={selected === friend.username} disabled={status === 'connecting' || status === 'error' || status === 'sending'} onClick={() => select(friend.username)}>{safeMedia(friend.profile_picture) && <img src={safeMedia(friend.profile_picture)} alt="" loading="lazy" referrerPolicy="no-referrer" />}{friend.displayname || friend.username}{messages[friend.username]?.filter(message => !message.read && message.sender_id === friend._id && selected !== friend.username).length ? ' ●' : ''}</button>)}{status === 'ready' && !friends.length && <p>Ei ystäviä.</p>}</nav>
      <div className="chat-conversation"><div id="chat-messages" ref={history} role="log" aria-label="Keskustelu" aria-live="polite">{!selected && <p>Valitse ensin ystävä.</p>}{selected && status === 'loading' && <p role="status">Ladataan viestejä…</p>}{(messages[selected] || []).map(message => <div key={message._id} className="chat-message"><strong>{friends.find(friend => friend._id === message.sender_id)?.displayname || 'Minä'}: </strong>{message.type === 'invitation' ? <Invitation message={message} /> : message.type === 'media' ? safeMedia(message.extra?.media_url) ? <a href={safeMedia(message.extra?.media_url)} target="_blank" rel="noopener noreferrer"><img src={safeMedia(message.extra?.media_url)} alt="Liite" loading="lazy" referrerPolicy="no-referrer" /></a> : <span>Liite ei ole saatavilla.</span> : message.content}</div>)}</div>
        <form onSubmit={event => { event.preventDefault(); send(); }}><label className="chat-input-label" htmlFor="chat-input">Viesti</label><textarea id="chat-input" rows={2} placeholder="Kirjoita viesti…" value={draft} disabled={!selected || status !== 'ready'} onChange={event => setDraft(event.target.value)} /><button id="chat-send" type="submit" disabled={!selected || !draft.trim() || status !== 'ready'}>{status === 'sending' ? 'Lähetetään…' : 'Lähetä'}</button></form>
      </div></div>
  </section>;
}
