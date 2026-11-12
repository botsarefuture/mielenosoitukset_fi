export type HeaderLink = { href: string; label: string; icon: string };
export type HeaderMessages = {
  skip: string; home: string; navigation: string; languages: string; changeLanguage: string;
  menu: string; openMenu: string; closeMenu: string; close: string; userMenu: string;
  theme: string; lightTheme: string; darkTheme: string; adminWarning: string;
  notifications: string; markRead: string; all: string; empty: string; loading: string;
  loadError: string; markError: string;
};
export type HeaderProps = {
  brand: string; home: string; path: string; role: string; links: HeaderLink[];
  languages: { code: string; name: string; href: string; active: boolean }[];
  fundraising: string | null;
  account: { name: string; picture: string | null; links: HeaderLink[]; globalAdmin: boolean } | null;
  notifications: { list: string; markRead: string; all: string; unread: number };
  messages: HeaderMessages;
};
