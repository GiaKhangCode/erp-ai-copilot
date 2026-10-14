"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, ExternalLink } from "lucide-react";

interface MarkdownRendererProps {
  content: string;
  onViewDocument?: (filename: string) => void;
}

export function MarkdownRenderer({ content, onViewDocument }: MarkdownRendererProps) {
  // Regex to detect inline citation patterns like:
  // [Nguồn: filename.docx, Trang: 1, Đoạn: 0] or [Nguồn: filename.pdf]
  const renderTextWithCitations = (text: string) => {
    const citationRegex = /\[Nguồn:\s*([^,\]]+)(?:,\s*Trang:\s*(\d+))?(?:,\s*Đoạn:\s*(\d+))?\]/g;
    
    // Check if there are any matches
    if (!citationRegex.test(text)) {
      return text;
    }

    // Reset regex index
    citationRegex.lastIndex = 0;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = citationRegex.exec(text)) !== null) {
      const matchStart = match.index;
      const matchEnd = citationRegex.lastIndex;

      // Add text before the match
      if (matchStart > lastIndex) {
        parts.push(text.substring(lastIndex, matchStart));
      }

      const filename = match[1].trim();
      const page = match[2];
      const chunk = match[3];

      parts.push(
        <button
          key={`cite-${matchStart}`}
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (onViewDocument) {
              onViewDocument(filename);
            }
          }}
          className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md bg-blue-50 hover:bg-blue-100 text-blue-700 hover:text-blue-800 border border-blue-200/90 text-[11px] font-semibold transition-all shadow-2xs group cursor-pointer align-baseline"
          title={`Bấm để mở xem tài liệu: ${filename}`}
        >
          <FileText className="w-3 h-3 text-blue-600 group-hover:scale-110 transition-transform shrink-0" />
          <span className="truncate max-w-[180px]">{filename}</span>
          {page && <span className="text-[10px] text-blue-500 font-normal">P.{page}</span>}
          {chunk && !page && <span className="text-[10px] text-blue-500 font-normal">§{chunk}</span>}
          <ExternalLink className="w-2.5 h-2.5 text-blue-400 group-hover:text-blue-600 shrink-0" />
        </button>
      );

      lastIndex = matchEnd;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }

    return parts;
  };

  return (
    <div className="markdown-body text-[13px] leading-relaxed text-slate-800 space-y-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headers
          h1: ({ children }) => (
            <h1 className="text-base font-bold text-slate-900 border-b border-slate-200 pb-1.5 mt-3 mb-2 flex items-center gap-1.5">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-[14px] font-bold text-slate-900 border-b border-slate-100 pb-1 mt-2.5 mb-1.5 flex items-center gap-1.5">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[13px] font-bold text-slate-900 mt-2.5 mb-1 flex items-center gap-1.5">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-[12.5px] font-semibold text-slate-800 mt-2 mb-1">
              {children}
            </h4>
          ),

          // Paragraphs
          p: ({ children }) => {
            return (
              <p className="text-[13px] leading-relaxed text-slate-700 my-1.5">
                {React.Children.map(children, (child) => {
                  if (typeof child === "string") {
                    return renderTextWithCitations(child);
                  }
                  return child;
                })}
              </p>
            );
          },

          // Strong & Em
          strong: ({ children }) => (
            <strong className="font-bold text-slate-900">{children}</strong>
          ),
          em: ({ children }) => <em className="italic text-slate-600">{children}</em>,

          // Lists
          ul: ({ children }) => (
            <ul className="list-disc pl-5 my-2 space-y-1 text-[13px] text-slate-700 marker:text-blue-500">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 my-2 space-y-1 text-[13px] text-slate-700 marker:font-semibold marker:text-blue-600">
              {children}
            </ol>
          ),
          li: ({ children }) => {
            return (
              <li className="leading-relaxed">
                {React.Children.map(children, (child) => {
                  if (typeof child === "string") {
                    return renderTextWithCitations(child);
                  }
                  return child;
                })}
              </li>
            );
          },

          // Tables (GFM)
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-slate-200/90 shadow-2xs bg-white">
              <table className="w-full text-left text-xs border-collapse">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-bold text-[11.5px] uppercase tracking-wider">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-blue-50/40 transition-colors">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-3.5 py-2.5 font-bold text-slate-800 border-r border-slate-200/60 last:border-r-0">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3.5 py-2.5 text-slate-700 border-r border-slate-100 last:border-r-0">
              {React.Children.map(children, (child) => {
                if (typeof child === "string") {
                  return renderTextWithCitations(child);
                }
                return child;
              })}
            </td>
          ),

          // Code blocks & inline code
          code: ({ className, children, ...props }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-slate-100 text-blue-700 font-mono text-[11.5px] border border-slate-200/80 font-semibold"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            return (
              <pre className="p-3 my-2 rounded-xl bg-slate-900 text-slate-100 font-mono text-[11.5px] overflow-x-auto shadow-inner">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            );
          },

          // Blockquote
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-3 border-blue-500 bg-blue-50/50 pl-3 py-1 rounded-r-lg text-slate-700 italic text-[12.5px]">
              {children}
            </blockquote>
          ),

          // Horizontal rule
          hr: () => <hr className="my-3 border-t border-slate-200/80" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
