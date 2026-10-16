"use client";

import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type UIEvent } from "react";
import { ApiError, getChannels, getVideos, lookupChannel } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { isChannelLink, isVideoId, parseVideoInput } from "@/lib/youtube";
import { Badge } from "./parts";
import type { Side, View } from "./state";

export const DEBOUNCE_MS = 300;
/** Suggestions per request; more load as the list scrolls near its end. */
export const PAGE = 20;
const MAX_QUERY = 100;
/** Load the next page when the list is scrolled to within this many px of its end. */
const LOAD_AHEAD_PX = 120;
const LINK_OPTION = "link";

type Option = { id: string; name: string; detail: string };
type Page = { items: Option[]; total: number };

const TEXT = {
  videos: {
    label: "Video name or YouTube link",
    placeholder: "Title, channel, or link…",
    hint: "Search our dataset, or paste a link to check any video.",
    noMatch: (q: string) => `No videos in our dataset match “${q}”. Paste a YouTube link to check any video.`,
  },
  channels: {
    label: "Channel name or YouTube link",
    placeholder: "Channel name, or link…",
    hint: "Search our dataset, or paste a channel or video link.",
    noMatch: (q: string) => `No channels in our dataset match “${q}”. You can also paste a channel or video link.`,
  },
};

const LOOKUP = {
  busy: "Looking up this channel…",
  notInDataset: (name: string | null) =>
    `${name ?? "This channel"} isn’t in our dataset yet. Checking a whole channel is coming soon. For now, pick a channel from our dataset.`,
  notFound: "We couldn’t find a YouTube channel for that link.",
  limit:
    "You’ve looked up or checked several new videos and channels in the last hour. Please try again later, or pick a channel from our dataset.",
  failed: "We couldn’t look up that link. Please try again in a moment.",
  taken: "That channel is already in the other slot.",
};

/** Text that is meant as a link rather than a name. */
const looksLikeLink = (text: string) => /^https?:\/\/|youtu\.?be|youtube\./i.test(text);

async function search(view: View, q: string, offset: number): Promise<Page> {
  const params = { sort: "score", order: "desc" as const, q, offset, limit: PAGE };
  if (view === "videos") {
    const { items, total } = await getVideos(params);
    return { total, items: items.map((v) => ({ id: v.id, name: v.title, detail: v.channel })) };
  }
  const { items, total } = await getChannels({ ...params, minVideos: 1 });
  return {
    total,
    items: items.map((c) => ({
      id: c.id,
      name: c.name,
      detail: c.videoCount === 1 ? "1 video" : `${c.videoCount.toLocaleString("en-US")} videos`,
    })),
  };
}

/**
 * An empty slot's field (see STYLE.md, Compare picker): typing a name suggests videos or
 * channels from the dataset, in a list that scrolls and loads more as it nears its end. A
 * pasted YouTube link is offered as is: a video link is checked live if it isn't in the
 * dataset; for channels, a channel or video link is looked up, and only a channel we have can
 * be picked. An ARIA combobox with a listbox; `otherId` (the other slot's item) is never offered.
 */
export default function Picker({
  side,
  view,
  otherId,
  onPick,
  autoFocus = false,
}: {
  side: Side;
  view: View;
  otherId: string;
  onPick: (id: string) => void;
  autoFocus?: boolean;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const text = TEXT[view];
  const [value, setValue] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  // Pages after the first, for the query they were loaded for.
  const [more, setMore] = useState<{ query: string; items: Option[]; loading: boolean }>({
    query: "",
    items: [],
    loading: false,
  });
  // The channel link being looked up (channels only).
  const [linkToFind, setLinkToFind] = useState<string | null>(null);

  useEffect(() => {
    if (autoFocus) input.current?.focus();
  }, [autoFocus]);

  const trimmed = value.trim();
  const parsed = parseVideoInput(trimmed);
  const isLink = looksLikeLink(trimmed);
  const channelLink = isChannelLink(trimmed);
  // A link isn't searched for; a bare video ID is both offered and searched.
  const searchable = trimmed !== "" && !isLink;

  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchable ? trimmed.slice(0, MAX_QUERY) : ""), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [trimmed, searchable]);

  // While a new search runs, the last results stay (dimmed); an older response never wins.
  const load = useCallback(
    () => (query ? search(view, query, 0) : Promise.resolve<Page>({ items: [], total: 0 })),
    [view, query],
  );
  const first = useApi(load);
  const current = first.status !== "loading" && !first.stale;
  const loaded = [
    ...(first.status === "success" ? first.data.items : []),
    ...(more.query === query ? more.items : []),
  ];
  const total = first.status === "success" ? first.data.total : 0;
  const hasMore = current && first.status === "success" && loaded.length < total;

  const loadMore = () => {
    if (!hasMore || (more.query === query && more.loading)) return;
    const offset = loaded.length;
    const forQuery = query;
    const kept = more.query === query ? more.items : [];
    setMore({ query: forQuery, items: kept, loading: true });
    search(view, forQuery, offset).then(
      (page) =>
        setMore((old) => (old.query === forQuery ? { query: forQuery, items: [...kept, ...page.items], loading: false } : old)),
      () => setMore((old) => (old.query === forQuery ? { ...old, loading: false } : old)),
    );
  };

  const linkOption: Option | null =
    view === "videos"
      ? parsed.ok && parsed.id !== otherId
        ? { id: parsed.id, name: `Use this video: ${parsed.id}`, detail: "" }
        : null
      : (parsed.ok && !isVideoId(trimmed)) || channelLink
        ? { id: LINK_OPTION, name: "Use this channel’s link", detail: "" }
        : null;
  const options = [
    ...(linkOption ? [linkOption] : []),
    ...(searchable ? loaded.filter((o) => o.id !== otherId && o.id !== linkOption?.id) : []),
  ];

  let message: string | null = null;
  if (options.length === 0 && trimmed) {
    if (view === "videos" && channelLink) message = "That’s a channel link. Switch to Channels to compare channels.";
    else if (isLink && !parsed.ok) message = "That doesn’t look like a YouTube link or video ID.";
    else if (parsed.ok && parsed.id === otherId) message = "That video is already in the other slot.";
    else if (current && first.status === "error") message = "We couldn’t search right now. Please try again in a moment.";
    else if (current && first.status === "success" && query && query === trimmed.slice(0, MAX_QUERY)) message = text.noMatch(query);
  }
  const expanded = open && options.length > 0;
  const showPopup = open && (options.length > 0 || message !== null);

  // A pasted channel link, looked up; a new value drops it, so an old answer never applies.
  const loadChannel = useCallback(
    () => (linkToFind ? lookupChannel(linkToFind) : Promise.resolve(null)),
    [linkToFind],
  );
  const found = useApi(loadChannel);
  const foundNow = linkToFind !== null && found.status !== "loading" && !found.stale;
  const picked =
    foundNow && found.status === "success" && found.data?.inDataset && found.data.channelId !== otherId
      ? found.data.channelId
      : null;
  let lookup: string | null = null;
  if (linkToFind !== null) {
    if (!foundNow || picked) lookup = LOOKUP.busy;
    else if (found.status === "error") {
      const status = found.error instanceof ApiError ? found.error.status : null;
      lookup = status === 404 || status === 422 ? LOOKUP.notFound : status === 429 ? LOOKUP.limit : LOOKUP.failed;
    } else if (found.status === "success" && found.data) {
      lookup = found.data.inDataset ? LOOKUP.taken : LOOKUP.notInDataset(found.data.name);
    }
  }
  // A channel we have: fill the slot with it, once (`onPick` may be a new function each render).
  const pickedOnce = useRef<string | null>(null);
  useEffect(() => {
    if (picked && pickedOnce.current !== picked) {
      pickedOnce.current = picked;
      onPick(picked);
    }
  }, [picked, onPick]);

  const choose = (option: Option) => {
    setOpen(false);
    setActive(-1);
    if (option.id === LINK_OPTION) {
      if (linkToFind === trimmed) found.retry();
      else setLinkToFind(trimmed);
      return;
    }
    setValue("");
    onPick(option.id);
  };

  // Keeps the active option in view as the arrow keys move through the list.
  useEffect(() => {
    if (active >= 0) document.getElementById(`${id}-option-${active}`)?.scrollIntoView?.({ block: "nearest" });
  }, [active, id]);

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      setOpen(true);
      const n = options.length;
      if (n === 0) return;
      if (e.key === "ArrowDown" && active >= n - 2) loadMore();
      setActive((i) => (e.key === "ArrowDown" ? Math.min(i + 1, n - 1) : i <= 0 ? n - 1 : i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const option = options[active] ?? options[0];
      if (option) choose(option);
      else setOpen(true);
    } else if (e.key === "Escape") {
      if (open) e.preventDefault();
      setOpen(false);
      setActive(-1);
    }
  };

  const onScroll = (e: UIEvent<HTMLUListElement>) => {
    const list = e.currentTarget;
    if (list.scrollTop + list.clientHeight >= list.scrollHeight - LOAD_AHEAD_PX) loadMore();
  };

  const optionId = (i: number) => `${id}-option-${i}`;
  return (
    <div>
      <label htmlFor={`${id}-input`} className="flex items-center gap-2 font-semibold text-navy">
        <Badge side={side} decorative large />
        {text.label}
      </label>
      <div className="relative mt-2">
        <svg
          aria-hidden="true"
          viewBox="0 0 20 20"
          className="pointer-events-none absolute top-1/2 left-5 size-4 -translate-y-1/2 fill-none stroke-navy stroke-2"
        >
          <circle cx="8.5" cy="8.5" r="6" />
          <path d="m13 13 5 5" strokeLinecap="round" />
        </svg>
        <input
          ref={input}
          id={`${id}-input`}
          type="text"
          role="combobox"
          aria-expanded={expanded}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={expanded && active >= 0 ? optionId(active) : undefined}
          aria-describedby={`${id}-hint`}
          autoComplete="off"
          spellCheck={false}
          maxLength={500}
          placeholder={text.placeholder}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setOpen(true);
            setActive(-1);
            setLinkToFind(null);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className="h-12 w-full min-w-0 rounded-full border-2 border-navy bg-white pr-5 pl-12 text-navy placeholder:text-ink/70 focus:shadow-[0_0_0_5px_var(--color-sunny)] focus:outline-none"
        />
        <div
          hidden={!showPopup}
          className="absolute inset-x-0 top-full z-20 mt-2 rounded-2xl border border-navy/15 bg-white p-2 shadow-[0_4px_16px_rgb(15_46_138/0.08)]"
        >
          <ul
            id={`${id}-list`}
            role="listbox"
            aria-label={view === "videos" ? "Suggested videos" : "Suggested channels"}
            onScroll={onScroll}
            // About six options in view; the rest scroll, and more load near the end.
            className={`max-h-[21rem] overflow-y-auto overscroll-contain ${current ? "" : "opacity-60"}`}
          >
            {expanded &&
              options.map((option, i) => (
                <li
                  key={option.id}
                  id={optionId(i)}
                  role="option"
                  aria-selected={i === active}
                  // Keeps focus in the field, so the click lands before it closes the list.
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => choose(option)}
                  className="flex min-h-11 cursor-pointer flex-col justify-center rounded-xl px-3 py-1.5 hover:bg-sky aria-selected:bg-sky"
                >
                  <span className="truncate text-sm font-semibold text-navy">{option.name}</span>
                  {option.detail && <span className="truncate text-sm text-ink">{option.detail}</span>}
                </li>
              ))}
            {expanded && more.query === query && more.loading && (
              <li role="presentation" className="px-3 py-2 text-sm text-ink/80">
                Loading more…
              </li>
            )}
          </ul>
          {!expanded && message && <p className="px-3 py-2 text-sm text-ink">{message}</p>}
        </div>
      </div>
      <p id={`${id}-hint`} aria-live="polite" className={`mt-2 text-sm ${lookup ? "font-semibold text-navy" : "text-ink"}`}>
        {lookup ?? text.hint}
      </p>
      <p aria-live="polite" className="sr-only">
        {open && trimmed ? (expanded ? `${options.length} suggestions${hasMore ? `, more as you scroll` : ""}` : message ?? "") : ""}
      </p>
    </div>
  );
}
