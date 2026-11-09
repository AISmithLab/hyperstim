import fs from "node:fs";
import path from "node:path";
import type { Element, ElementContent, Root as HastRoot } from "hast";
import type { Parent as MdastParent, PhrasingContent, Root as MdastRoot, RootContent } from "mdast";
import type { Options as MarkdownOptions } from "react-markdown";
import { PostError } from "./posts";

// How a post's markdown becomes HTML (plan 018): remark-gfm (tables, footnotes) and
// remark-directive (the figure, video and youtube blocks), then the two plugins here. They
// fail the build on a broken post and number the captions; PostBody maps the result to the
// site's elements.

/** The blocks a post can hold besides standard markdown, and the attributes each needs. */
const BLOCKS = {
  figure: ["src", "alt"],
  video: ["src", "poster"],
  youtube: ["id"],
} as const;
type Block = keyof typeof BLOCKS;

/** A YouTube video ID. */
const YOUTUBE_ID = /^[\w-]{11}$/;
/** A citation whose footnote is never defined: remark-gfm leaves it as text. */
const UNDEFINED_CITATION = /\[\^([^\]\s]+)\]/;

type Directive = MdastParent & {
  type: "textDirective" | "leafDirective" | "containerDirective";
  name: string;
  attributes?: Record<string, string | null | undefined> | null;
  data?: { hName?: string; hProperties?: Record<string, unknown> };
};

/** What the checks need to know about the post. */
export type PostContext = { slug: string; file: string; mediaDir: string };

function children(node: unknown): RootContent[] | undefined {
  return (node as Partial<MdastParent>).children;
}

/**
 * Checks the body and prepares the blocks: each `::figure`, `::video` and `::youtube` becomes
 * a `figure` element with its number (figures and videos counted apart; YouTube embeds are
 * videos) and the caption as its children.
 */
export function remarkPost(context: PostContext) {
  const fail = (problem: string): never => {
    throw new PostError(context.file, problem);
  };
  return (tree: MdastRoot) => {
    const counts = { figure: 0, video: 0 };
    const cited = new Set<string>();
    const defined = new Set<string>();

    const visit = (parent: MdastParent) => {
      parent.children.forEach((node, i) => {
        switch (node.type) {
          case "heading":
            if (node.depth === 1 || node.depth > 3) {
              fail(`use ## and ### for headings ("${"#".repeat(node.depth)}" found); the title is the page's only top heading.`);
            }
            break;
          case "image":
          case "imageReference":
            fail("put images in a ::figure block, with alt text and a caption.");
            break;
          case "footnoteReference":
            cited.add(node.identifier);
            break;
          case "footnoteDefinition":
            defined.add(node.identifier);
            break;
          case "text": {
            const undefinedCitation = UNDEFINED_CITATION.exec(node.value);
            if (undefinedCitation) fail(`the reference [^${undefinedCitation[1]}] is cited but never defined.`);
            break;
          }
          case "textDirective": {
            // Not a block: text like "Note:this" that only looks like one. Put it back.
            const restored: PhrasingContent[] = [{ type: "text", value: `:${(node as Directive).name}` }];
            const label = children(node) as PhrasingContent[] | undefined;
            if (label?.length) restored.push({ type: "text", value: "[" }, ...label, { type: "text", value: "]" });
            parent.children.splice(i, 1, ...(restored as RootContent[]));
            break;
          }
          case "leafDirective":
          case "containerDirective":
            prepareBlock(node as Directive);
            break;
        }
        const inner = children(node);
        if (inner) visit(node as MdastParent);
      });
    };

    const prepareBlock = (node: Directive) => {
      const usage = "::figure[Caption]{src=… alt=…}, ::video[Caption]{src=… poster=…} or ::youtube[Caption]{id=…}";
      if (node.type === "containerDirective" || !(node.name in BLOCKS)) {
        fail(`unknown block "${node.type === "containerDirective" ? ":::" : "::"}${node.name}"; blocks are ${usage}.`);
      }
      const name = node.name as Block;
      const attributes = node.attributes ?? {};
      for (const attribute of BLOCKS[name]) {
        if (!attributes[attribute]?.trim()) fail(`::${name} needs ${attribute}="…".`);
      }
      for (const attribute of ["src", "poster"] as const) {
        const file = attributes[attribute];
        if (!file || !(BLOCKS[name] as readonly string[]).includes(attribute)) continue;
        if (file !== path.basename(file)) fail(`write media by file name only ("${file}").`);
        if (!fs.existsSync(path.join(context.mediaDir, context.slug, file))) {
          fail(`the file "${file}" is missing from public/blog-media/${context.slug}/.`);
        }
      }
      if (name === "youtube" && !YOUTUBE_ID.test(attributes.id!)) fail(`"${attributes.id}" is not a YouTube video ID.`);
      const kind = name === "figure" ? "figure" : "video";
      counts[kind] += 1;
      node.data = {
        hName: "figure",
        hProperties: {
          dataBlock: name,
          dataNumber: counts[kind],
          dataSrc: attributes.src ?? undefined,
          dataAlt: attributes.alt ?? undefined,
          dataPoster: attributes.poster ?? undefined,
          dataId: attributes.id ?? undefined,
        },
      };
    };

    visit(tree);
    for (const key of defined) if (!cited.has(key)) fail(`the reference [^${key}] is defined but never cited.`);
  };
}

/** The references' heading and back links (remark-rehype writes the footnotes section). */
export const remarkRehypeOptions: NonNullable<MarkdownOptions["remarkRehypeOptions"]> = {
  footnoteLabel: "References",
  footnoteLabelTagName: "h2",
  // Visible, as a post's H2; the default is a screen-reader-only label.
  footnoteLabelProperties: { className: [] },
  // "↩" for each citation of a source, without the default's number after the second: its
  // label says which one, and a visible number that the label lacks fails axe.
  footnoteBackContent: "↩",
  footnoteBackLabel: (referenceIndex, rereferenceIndex) =>
    `Back to citation ${referenceIndex + 1} in the text${rereferenceIndex > 1 ? ` (${rereferenceIndex})` : ""}`,
};

/** Class lists, as hast holds them. */
const classes = (list: string) => list.split(" ");
const REFERENCES = classes("mt-10 border-t border-navy/10 pt-2");
const REFERENCES_HEADING = classes("mt-[0.8em] mb-[0.5em] font-hand text-2xl leading-snug font-semibold text-navy sm:text-3xl");
const REFERENCE_LIST = classes("text-[0.9375rem] leading-relaxed");
const REFERENCE_ITEM = classes("grid scroll-mt-4 grid-cols-[2.25rem_1fr] rounded-xl py-1.5 target:bg-butter");
const REFERENCE_NUMBER = classes("pr-2 text-right text-ink");
const REFERENCE_TEXT = classes("min-w-0 [&>p]:m-0");
const CITATION = classes(
  "rounded-sm px-px text-[0.85em] font-bold text-navy no-underline hover:underline hover:decoration-2 hover:underline-offset-4",
);
const BACK_LINK = classes("ml-1.5 font-bold text-navy no-underline hover:underline");

function text(node: ElementContent): string {
  if (node.type === "text") return node.value;
  return node.type === "element" ? node.children.map(text).join("") : "";
}

/**
 * Shows citations as an inline "[1]" link (not superscript) and the references as a list
 * numbered "[1]", each with its ↩ link back to the text.
 */
export function rehypeReferences() {
  return (tree: HastRoot) => {
    const visit = (parent: HastRoot | Element) => {
      parent.children.forEach((node, i) => {
        if (node.type !== "element") return;
        const ref = node.tagName === "sup" && node.children.find((c) => c.type === "element" && c.properties.dataFootnoteRef);
        if (ref && ref.type === "element") {
          const number = text(ref);
          ref.children = [{ type: "text", value: `[${number}]` }];
          ref.properties.className = CITATION;
          ref.properties.ariaLabel = `Reference ${number}`;
          delete ref.properties.ariaDescribedBy;
          parent.children[i] = ref;
          return;
        }
        if (node.tagName === "section" && node.properties.dataFootnotes !== undefined) {
          node.properties.className = REFERENCES;
          node.properties.ariaLabelledBy = ["footnote-label"];
          for (const child of node.children) {
            if (child.type === "element" && child.tagName === "ol") numberReferences(child);
          }
        }
        if (node.tagName === "h2" && node.properties.id === "footnote-label") {
          node.properties.className = REFERENCES_HEADING;
        }
        if (node.tagName === "a" && node.properties.dataFootnoteBackref !== undefined) {
          node.properties.className = BACK_LINK;
        }
        visit(node);
      });
    };
    visit(tree);
  };
}

function numberReferences(list: Element) {
  list.properties.className = REFERENCE_LIST;
  let n = 0;
  for (const item of list.children) {
    if (item.type !== "element" || item.tagName !== "li") continue;
    n += 1;
    item.properties.className = REFERENCE_ITEM;
    item.children = [
      { type: "element", tagName: "span", properties: { className: REFERENCE_NUMBER }, children: [{ type: "text", value: `[${n}]` }] },
      { type: "element", tagName: "div", properties: { className: REFERENCE_TEXT }, children: item.children },
    ];
  }
}
