"use client";

import Image from "next/image";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
} from "react";
import catalog from "../public/data/nm_catalog.json";
import { PUBLIC_TELEMETRY_SNAPSHOT_URL } from "./live-config";

type NmStatus =
  | "spawned"
  | "primed"
  | "cooldown_blocked"
  | "lottery_open"
  | "unknown";

type NmCatalogRow = {
  nm_key: string;
  display_name: string;
  zone: string;
  placeholder: string;
  rule_kind: "lottery" | "hq_lottery";
  script_default_chance_percent: number;
  script_default_cooldown_seconds: number;
  image_url: string;
  image_width: number;
  image_height: number;
  profile_url: string;
  rule_source_url: string;
};

export type NmStatusRow = NmCatalogRow & {
  status: NmStatus;
  last_observed_status: NmStatus | null;
  observed_at: string | null;
  cooldown_opens_at: string | null;
  cooldown_remaining_seconds: number | null;
  is_spawned: boolean | null;
  is_primed: boolean | null;
  placeholder_status: string;
  recorded_defeat_count: number;
  last_observed_kill_at: string | null;
  next_lottery_opportunity_at: string | null;
  effective_chance_percent: number | null;
  effective_cooldown_seconds: number | null;
  data_quality: string;
};

export type NmObserverRow = {
  observer_status: "fresh" | "stale" | "not_configured";
  observed_at: string | null;
  map_started_at: string | null;
  ruleset_git_sha: string | null;
  tracked_nm_count: number;
  observed_nm_count: number;
  refresh_cadence: "hourly";
};

export type NmSnapshot = {
  generated_at: string;
  datasets: {
    nm_status?: NmStatusRow[];
    nm_observer?: NmObserverRow[];
  };
};

const REFRESH_INTERVAL_MS = 10 * 60 * 1000;
const catalogRows = catalog.nms as NmCatalogRow[];

const statusLabels: Record<NmStatus, string> = {
  spawned: "Spawned",
  primed: "Primed to spawn",
  cooldown_blocked: "Cooldown active",
  lottery_open: "Lottery open",
  unknown: "Unknown",
};

function fallbackRows(): NmStatusRow[] {
  return catalogRows.map((row) => ({
    ...row,
    status: "unknown",
    last_observed_status: null,
    observed_at: null,
    cooldown_opens_at: null,
    cooldown_remaining_seconds: null,
    is_spawned: null,
    is_primed: null,
    placeholder_status: "unknown",
    recorded_defeat_count: 0,
    last_observed_kill_at: null,
    next_lottery_opportunity_at: null,
    effective_chance_percent: null,
    effective_cooldown_seconds: null,
    data_quality: "not_observed",
  }));
}

function parseDate(value: string | null) {
  if (!value) return null;
  const date = new Date(value.replace(" ", "T"));
  return Number.isNaN(date.getTime()) ? null : date;
}

function timeLabel(value: string | null) {
  const date = parseDate(value);
  if (!date) return "Not observed";
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/New_York",
    timeZoneName: "short",
  });
}

function relativeAge(value: string | null, now: number) {
  const date = parseDate(value);
  if (!date) return "Observer not connected";
  const minutes = Math.max(0, Math.round((now - date.getTime()) / 60000));
  if (minutes < 1) return "Checked just now";
  if (minutes < 60) return `Checked ${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `Checked ${hours}h ${minutes % 60}m ago`;
}

function durationLabel(seconds: number) {
  if (seconds <= 1) return "Immediate";
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const hours = seconds / 3600;
  return Number.isInteger(hours) ? `${hours}h` : `${hours.toFixed(1)}h`;
}

function opportunityLabel(row: NmStatusRow) {
  if (row.status === "lottery_open") return "Next placeholder defeat";
  if (row.status === "spawned") return "NM currently active";
  if (row.status === "primed") return "Pending respawn timer";
  if (row.cooldown_opens_at) return timeLabel(row.cooldown_opens_at);
  return "Awaiting map observer";
}

function recordedDefeatLabel(row: NmStatusRow) {
  if (row.recorded_defeat_count > 0) {
    const noun = row.recorded_defeat_count === 1 ? "defeat" : "defeats";
    return `${row.recorded_defeat_count} ${noun} · latest ${timeLabel(row.last_observed_kill_at)}`;
  }
  if (row.last_observed_kill_at) {
    return `Direct observer · ${timeLabel(row.last_observed_kill_at)}`;
  }
  return "None in supervisor logs";
}

function observerFallback(): NmObserverRow {
  return {
    observer_status: "not_configured",
    observed_at: null,
    map_started_at: null,
    ruleset_git_sha: null,
    tracked_nm_count: catalogRows.length,
    observed_nm_count: 0,
    refresh_cadence: "hourly",
  };
}

function cardStep(track: HTMLDivElement) {
  const firstCard = track.querySelector<HTMLElement>(".nm-card");
  const gap = Number.parseFloat(window.getComputedStyle(track).columnGap) || 0;
  return (firstCard?.getBoundingClientRect().width ?? 332) + gap;
}

function NmCard({ row, index }: { row: NmStatusRow; index: number }) {
  const chance =
    row.effective_chance_percent ?? row.script_default_chance_percent;
  const cooldown =
    row.effective_cooldown_seconds ?? row.script_default_cooldown_seconds;
  const ruleBasis =
    row.effective_chance_percent === null ? "Script default" : "Observed effective rule";

  return (
    <article className={`nm-card nm-status-${row.status}`}>
      <div className="nm-image-frame">
        <Image
          src={row.image_url}
          alt={`${row.display_name} in Final Fantasy XI`}
          fill
          sizes="(max-width: 680px) 82vw, 330px"
          className="nm-image"
        />
        <div className="nm-image-scrim" aria-hidden="true" />
        <span className="nm-card-number">{String(index + 1).padStart(2, "0")}</span>
        <span className={`nm-status-chip status-${row.status}`}>
          <i aria-hidden="true" />
          {statusLabels[row.status]}
        </span>
      </div>

      <div className="nm-card-body">
        <span className="nm-zone">{row.zone}</span>
        <h3>{row.display_name}</h3>
        <p className="nm-placeholder">Placeholder · {row.placeholder}</p>

        <dl className="nm-data-grid">
          <div>
            <dt>Lottery</dt>
            <dd>{chance}%</dd>
          </div>
          <div>
            <dt>Cooldown</dt>
            <dd>{durationLabel(cooldown)}</dd>
          </div>
          <div className="nm-data-wide">
            <dt>Next opportunity</dt>
            <dd>{opportunityLabel(row)}</dd>
          </div>
          <div className="nm-data-wide">
            <dt>Recorded defeats</dt>
            <dd>{recordedDefeatLabel(row)}</dd>
          </div>
        </dl>

        <div className="nm-card-meta">
          <span>{ruleBasis}</span>
          <span>{row.data_quality.replaceAll("_", " ")}</span>
        </div>
        <div className="nm-source-links">
          <a href={row.profile_url} target="_blank" rel="noreferrer">
            Image / profile <span aria-hidden="true">↗</span>
          </a>
          <a href={row.rule_source_url} target="_blank" rel="noreferrer">
            Rule source <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
    </article>
  );
}

export function NmCarousel({ initialSnapshot }: { initialSnapshot: NmSnapshot }) {
  const [snapshot, setSnapshot] = useState(initialSnapshot);
  const [now, setNow] = useState(() => Date.now());
  const [activeIndex, setActiveIndex] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startScrollLeft: number;
    moved: boolean;
  } | null>(null);
  const suppressClickRef = useRef(false);

  const rows = useMemo(() => {
    const liveRows = snapshot.datasets.nm_status;
    return liveRows?.length === 20 ? liveRows : fallbackRows();
  }, [snapshot]);
  const observer = snapshot.datasets.nm_observer?.[0] ?? observerFallback();

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(PUBLIC_TELEMETRY_SNAPSHOT_URL, {
        cache: "no-store",
      });
      if (!response.ok) return;
      const next = (await response.json()) as NmSnapshot;
      if (next.datasets?.nm_status?.length === 20) setSnapshot(next);
    } catch {
      // Keep the last reviewed aggregate snapshot when the network is unavailable.
    }
    setNow(Date.now());
  }, []);

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => void refresh(), 0);
    const interval = window.setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => {
      window.clearTimeout(initialRefresh);
      window.clearInterval(interval);
    };
  }, [refresh]);

  const move = useCallback((direction: -1 | 1) => {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({
      left: direction * cardStep(track),
      behavior: "smooth",
    });
  }, []);

  const onScroll = useCallback(() => {
    const track = trackRef.current;
    if (!track) return;
    setActiveIndex(
      Math.min(
        rows.length - 1,
        Math.max(0, Math.round(track.scrollLeft / cardStep(track))),
      ),
    );
  }, [rows.length]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      move(1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      move(-1);
    }
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "touch" || event.button !== 0) return;
    const track = trackRef.current;
    if (!track) return;
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startScrollLeft: track.scrollLeft,
      moved: false,
    };
    track.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const track = trackRef.current;
    const drag = dragRef.current;
    if (!track || !drag || drag.pointerId !== event.pointerId) return;

    const distance = event.clientX - drag.startX;
    if (!drag.moved && Math.abs(distance) < 5) return;
    if (!drag.moved) {
      drag.moved = true;
      setIsDragging(true);
    }
    event.preventDefault();
    track.scrollLeft = drag.startScrollLeft - distance;
  };

  const finishPointerDrag = (event: PointerEvent<HTMLDivElement>) => {
    const track = trackRef.current;
    const drag = dragRef.current;
    if (!track || !drag || drag.pointerId !== event.pointerId) return;

    dragRef.current = null;
    if (track.hasPointerCapture(event.pointerId)) {
      track.releasePointerCapture(event.pointerId);
    }
    setIsDragging(false);

    if (!drag.moved) return;
    suppressClickRef.current = true;
    window.setTimeout(() => {
      suppressClickRef.current = false;
    }, 0);

    const step = cardStep(track);
    track.scrollTo({
      left: Math.round(track.scrollLeft / step) * step,
      behavior: "smooth",
    });
  };

  const onClickCapture = (event: MouseEvent<HTMLDivElement>) => {
    if (!suppressClickRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    suppressClickRef.current = false;
  };

  const freshnessClass = observer.observer_status === "fresh" ? "is-fresh" : "is-stale";
  const freshnessTitle =
    observer.observer_status === "fresh"
      ? "Direct map observation"
      : observer.observer_status === "stale"
        ? "Map observation is stale"
        : "Map observer pending";

  return (
    <section className="panel nm-panel" id="notorious-monsters">
      <div className="nm-heading">
        <div>
          <span className="kicker">NM / Notorious monster watch</span>
          <h2>Twenty legends.<br />One hourly watchlist.</h2>
          <p>
            Direct map state when available. Unknown stays unknown—eligibility is
            never manufactured from uptime alone.
          </p>
        </div>
        <div className={`nm-freshness ${freshnessClass}`}>
          <i aria-hidden="true" />
          <span>{freshnessTitle}</span>
          <strong>{relativeAge(observer.observed_at, now)}</strong>
          <small>Hourly · :05 ET</small>
        </div>
      </div>

      <div className="nm-carousel-toolbar">
        <div>
          <strong>{String(activeIndex + 1).padStart(2, "0")}</strong>
          <span>/ {rows.length}</span>
          <small>Drag, swipe, scroll, or use arrow keys</small>
        </div>
        <div className="nm-carousel-buttons">
          <button type="button" onClick={() => move(-1)} aria-label="Previous notorious monster">
            ←
          </button>
          <button type="button" onClick={() => move(1)} aria-label="Next notorious monster">
            →
          </button>
        </div>
      </div>

      <div className="nm-carousel-shell">
        <div
          className={`nm-carousel-track${isDragging ? " is-dragging" : ""}`}
          ref={trackRef}
          onScroll={onScroll}
          onKeyDown={onKeyDown}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={finishPointerDrag}
          onPointerCancel={finishPointerDrag}
          onClickCapture={onClickCapture}
          onDragStart={(event) => event.preventDefault()}
          tabIndex={0}
          aria-label="Twenty notorious monsters"
        >
          {rows.map((row, index) => (
            <NmCard row={row} index={index} key={row.nm_key} />
          ))}
        </div>
      </div>

      <div className="nm-legend" aria-label="Notorious monster status legend">
        <span className="legend-open"><i /> Lottery open</span>
        <span className="legend-spawned"><i /> Spawned</span>
        <span className="legend-primed"><i /> Primed</span>
        <span className="legend-cooldown"><i /> Cooldown</span>
        <span className="legend-unknown"><i /> Unknown / stale</span>
      </div>
    </section>
  );
}
