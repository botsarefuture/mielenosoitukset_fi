import { createRoot } from 'react-dom/client';
import type { ComponentType } from 'react';

/** Mount only the named island. Other page content remains owned by Jinja/legacy JS. */
export function mountIsland<Props extends object>(name: string, Component: ComponentType<Props>) {
  document.querySelectorAll<HTMLElement>(`[data-react-island="${name}"]`).forEach((element) => {
    const config = document.getElementById(element.dataset.propsId ?? '');
    if (!config || element.dataset.reactMounted) return;

    // Keep a disabled server fallback if props or rendering fails. It cannot submit.
    const fallback = Array.from(element.childNodes, (node) => node.cloneNode(true));
    try {
      const props = JSON.parse(config.textContent ?? '') as Props;
      const root = createRoot(element, {
        onUncaughtError(error) {
          console.error(`Could not render React island: ${name}`, error);
          element.replaceChildren(...fallback);
          delete element.dataset.reactMounted;
        },
      });
      element.dataset.reactMounted = 'true';
      root.render(<Component {...props} />);
    } catch (error) {
      console.error(`Could not mount React island: ${name}`, error);
    }
  });
}
