import React, { useRef, useCallback, useEffect } from 'react';
import { TextB, TextItalic, Link as LinkIcon, Image, ListBullets } from '@phosphor-icons/react';

export default function RichTextEditor({ value, onChange, placeholder }) {
  const editorRef = useRef(null);
  const isInternalUpdateRef = useRef(false);

  // Sync external value → DOM only when the change did NOT originate from the user typing.
  // This prevents React from re-setting innerHTML on every keystroke, which would reset the
  // caret to position 0 and make typed characters appear in reverse order.
  useEffect(() => {
    if (!editorRef.current) return;
    if (isInternalUpdateRef.current) {
      isInternalUpdateRef.current = false;
      return;
    }
    const next = value || '';
    if (editorRef.current.innerHTML !== next) {
      editorRef.current.innerHTML = next;
    }
  }, [value]);

  const emitChange = useCallback(() => {
    if (editorRef.current) {
      isInternalUpdateRef.current = true;
      onChange(editorRef.current.innerHTML);
    }
  }, [onChange]);

  const execCmd = useCallback((command, val = null) => {
    editorRef.current?.focus();
    document.execCommand(command, false, val);
    emitChange();
  }, [emitChange]);

  const handleBold = () => execCmd('bold');
  const handleItalic = () => execCmd('italic');

  const handleLink = () => {
    const url = prompt('Enter URL:');
    if (url) execCmd('createLink', url);
  };

  const handleImage = () => {
    const url = prompt('Enter image URL:');
    if (url) execCmd('insertImage', url);
  };

  const handleList = () => execCmd('insertUnorderedList');

  return (
    <div className="border border-white/10 rounded-md overflow-hidden" data-testid="rich-text-editor">
      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 bg-[#1A1A24] border-b border-white/10">
        <button type="button" onClick={handleBold} className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors" title="Bold">
          <TextB className="w-4 h-4" />
        </button>
        <button type="button" onClick={handleItalic} className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors" title="Italic">
          <TextItalic className="w-4 h-4" />
        </button>
        <button type="button" onClick={handleLink} className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors" title="Insert Link">
          <LinkIcon className="w-4 h-4" />
        </button>
        <button type="button" onClick={handleImage} className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors" title="Insert Image">
          <Image className="w-4 h-4" />
        </button>
        <button type="button" onClick={handleList} className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors" title="Bullet List">
          <ListBullets className="w-4 h-4" />
        </button>
      </div>

      {/* Editor — no dangerouslySetInnerHTML; content is managed imperatively in useEffect */}
      <div
        ref={editorRef}
        contentEditable
        onInput={emitChange}
        suppressContentEditableWarning
        className="min-h-[100px] max-h-[200px] overflow-y-auto p-3 bg-[#1A1A24] text-white text-sm focus:outline-none [&_a]:text-[#00E5FF] [&_a]:underline [&_img]:max-w-full [&_img]:rounded [&_img]:my-2"
        data-placeholder={placeholder || 'Write your stream description...'}
        style={{ minHeight: '100px' }}
        data-testid="rich-text-content"
      />
    </div>
  );
}
