import React, { useRef, useCallback } from 'react';
import { TextB, TextItalic, Link as LinkIcon, Image, ListBullets } from '@phosphor-icons/react';

export default function RichTextEditor({ value, onChange, placeholder }) {
  const editorRef = useRef(null);

  const execCmd = useCallback((command, val = null) => {
    editorRef.current?.focus();
    document.execCommand(command, false, val);
    // Trigger onChange
    if (editorRef.current) {
      onChange(editorRef.current.innerHTML);
    }
  }, [onChange]);

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

  const handleInput = () => {
    if (editorRef.current) {
      onChange(editorRef.current.innerHTML);
    }
  };

  return (
    <div className="border border-white/10 rounded-md overflow-hidden" data-testid="rich-text-editor">
      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 bg-[#1A1A24] border-b border-white/10">
        <button
          type="button"
          onClick={handleBold}
          className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors"
          title="Bold"
        >
          <TextB className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleItalic}
          className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors"
          title="Italic"
        >
          <TextItalic className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleLink}
          className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors"
          title="Insert Link"
        >
          <LinkIcon className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleImage}
          className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors"
          title="Insert Image"
        >
          <Image className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleList}
          className="p-1.5 rounded hover:bg-white/10 text-[#A0A0AB] hover:text-white transition-colors"
          title="Bullet List"
        >
          <ListBullets className="w-4 h-4" />
        </button>
      </div>

      {/* Editor */}
      <div
        ref={editorRef}
        contentEditable
        onInput={handleInput}
        dangerouslySetInnerHTML={{ __html: value || '' }}
        className="min-h-[100px] max-h-[200px] overflow-y-auto p-3 bg-[#1A1A24] text-white text-sm focus:outline-none [&_a]:text-[#00E5FF] [&_a]:underline [&_img]:max-w-full [&_img]:rounded [&_img]:my-2"
        data-placeholder={placeholder || "Write your stream description..."}
        style={{ minHeight: '100px' }}
        data-testid="rich-text-content"
      />
    </div>
  );
}
