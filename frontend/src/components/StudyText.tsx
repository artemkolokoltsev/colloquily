import Markdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

/** Source HTML stays disabled; all math and fonts are rendered locally. */
export function StudyText({ children }: { children?: string | null }) {
  return (
    <div className="study-text">
      <Markdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeKatex, { strict: false, trust: false }]]}
        components={{
          img: () => null,
          a: ({ children }) => <span>{children}</span>,
        }}
      >
        {children || ""}
      </Markdown>
    </div>
  );
}
