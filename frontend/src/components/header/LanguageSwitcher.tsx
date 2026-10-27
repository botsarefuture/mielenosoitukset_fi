import type { HeaderProps } from './types';
import { Icon } from './NavigationLink';

export function LanguageSwitcher({ languages, messages }: Pick<HeaderProps, 'languages' | 'messages'>) {
  if (languages.length < 2) return null;
  return <nav className="language-buttons" aria-label={messages.languages}>
    <Icon name="fa-globe" />
    {languages.map(language => <a key={language.code}
      className={`language-button${language.active ? ' active' : ''}`}
      href={language.href} title={language.name}
      aria-label={`${messages.changeLanguage} ${language.name}`}
      aria-current={language.active ? 'page' : undefined}>{language.code.toUpperCase()}</a>)}
  </nav>;
}
