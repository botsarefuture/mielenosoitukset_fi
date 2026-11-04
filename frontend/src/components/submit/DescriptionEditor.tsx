import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import ReactQuill from 'react-quill-new';
import 'react-quill-new/dist/quill.snow.css';
import type { DraftDelta } from './draft';

/**
 * Rich text description editor.
 *
 * Wraps Quill (via react-quill-new, the React 19 compatible fork) instead of the
 * legacy global `quill` script. The component stays uncontrolled because Quill
 * owns its own document; the parent receives HTML for the submitted field and
 * the Delta for draft storage.
 */
export type DescriptionEditorHandle = {
  /** Replace the document from HTML (Facebook import). */
  setHtml: (html: string) => void;
  /** Restore a stored draft document silently. */
  setDelta: (delta: DraftDelta | null) => void;
  /** Current editor HTML, or '' when the editor is unavailable. */
  getHtml: () => string;
  /** Current document as a bounded Delta, or null. */
  getDelta: () => DraftDelta | null;
};

type DescriptionEditorProps = {
  initialHtml: string;
  initialDelta?: DraftDelta | null;
  onChange: (html: string, delta: DraftDelta | null) => void;
  ariaLabel: string;
  describedBy?: string;
};

const TOOLBAR = [
  ['bold', 'italic'],
  ['link', 'blockquote'],
  [{ list: 'ordered' }, { list: 'bullet' }],
];

export const DescriptionEditor = forwardRef<DescriptionEditorHandle, DescriptionEditorProps>(
  function DescriptionEditor({ initialHtml, initialDelta, onChange, ariaLabel, describedBy }, ref) {
    const quillRef = useRef<ReactQuill>(null);
    const onChangeRef = useRef(onChange);
    onChangeRef.current = onChange;
    const restoredRef = useRef(false);

    const getEditor = () => quillRef.current?.getEditor();

    useImperativeHandle(ref, () => ({
      setHtml(html: string) {
        const editor = getEditor();
        if (!editor) return;
        // Quill 2 takes an object here; Quill 1 took a bare HTML string.
        const contents = editor.clipboard.convert({ html });
        editor.setContents(contents, 'silent');
        onChangeRef.current(editor.root.innerHTML, editor.getContents() as DraftDelta);
      },
      setDelta(next: DraftDelta | null) {
        const editor = getEditor();
        if (!editor || !next?.ops?.length) return;
        editor.setContents(next as never, 'silent');
        onChangeRef.current(editor.root.innerHTML, next);
      },
      getHtml() {
        return getEditor()?.root.innerHTML ?? '';
      },
      getDelta() {
        const contents = getEditor()?.getContents();
        return (contents as DraftDelta | undefined) ?? null;
      },
    }));

    // Restore a stored draft once, after Quill has mounted.
    useEffect(() => {
      if (restoredRef.current) return;
      restoredRef.current = true;
      const editor = getEditor();
      if (!editor) return;
      if (initialDelta?.ops?.length) {
        editor.setContents(initialDelta as never, 'silent');
        onChangeRef.current(editor.root.innerHTML, initialDelta);
      } else if (initialHtml) {
        editor.setContents(editor.clipboard.convert({ html: initialHtml }), 'silent');
      }
    }, [initialDelta, initialHtml]);

    return (
      <div className="editor-container" id="editor-container">
        <ReactQuill
          ref={quillRef}
          theme="snow"
          modules={{ toolbar: TOOLBAR }}
          defaultValue=""
          aria-label={ariaLabel}
          aria-describedby={describedBy}
          onChange={() => {
            const editor = getEditor();
            if (!editor) return;
            onChangeRef.current(editor.root.innerHTML, editor.getContents() as DraftDelta);
          }}
        />
      </div>
    );
  },
);
