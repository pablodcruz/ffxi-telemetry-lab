from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data import load_dashboard_snapshot

INK = "#18212B"
BLUE = "#2563EB"
BLUE_LIGHT = "#93C5FD"
GOLD = "#D4A72C"
ORANGE = "#E87932"
MUTED = "#64748B"
GRID = "#E2E8F0"

st.set_page_config(
    page_title="FFXI Telemetry",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1480px; padding-top: 1.5rem;}
      [data-testid="stMetric"] {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 14px;
        padding: 14px 16px;
      }
      [data-testid="stSidebar"] {background: #F8FAFC;}
      h1, h2, h3 {letter-spacing: -0.02em;}
      .coverage-note {
        color: #475569;
        font-size: 0.9rem;
        border-left: 3px solid #D4A72C;
        padding-left: 0.75rem;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60)
def snapshot():
    return load_dashboard_snapshot()


def frame(name: str) -> pd.DataFrame:
    return pd.DataFrame(snapshot()["datasets"].get(name, []))


def date_filter(dataframe: pd.DataFrame) -> pd.DataFrame:
    if dataframe.empty or "event_date" not in dataframe:
        return dataframe
    values = pd.to_datetime(dataframe["event_date"]).dt.date
    dataframe = dataframe.assign(event_date=values)
    return dataframe[
        (dataframe["event_date"] >= start_date) & (dataframe["event_date"] <= end_date)
    ]


def line_chart(
    dataframe: pd.DataFrame,
    y: str,
    title: str,
    subtitle: str,
    color: str = BLUE,
):
    figure = px.line(dataframe, x="event_date", y=y, markers=True)
    figure.update_traces(line_color=color, marker_color=color, line_width=3)
    figure.update_layout(
        title={"text": f"{title}<br><sup>{subtitle}</sup>"},
        height=340,
        margin=dict(l=10, r=10, t=75, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font_color=INK,
        showlegend=False,
        xaxis=dict(title=None, gridcolor=GRID),
        yaxis=dict(title=None, gridcolor=GRID, rangemode="tozero"),
    )
    return figure


try:
    current = snapshot()
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.info(
        "Local setup: run backfill, prepare-warehouse, dbt build, then export-public. "
        "The gameplay project is unaffected when this dashboard is offline."
    )
    st.stop()

quality = frame("data_quality")
coverage = current.get("coverage", {})
coverage_start = pd.to_datetime(coverage.get("earliest_event_time")).date()
coverage_end = pd.to_datetime(coverage.get("latest_event_time")).date()

with st.sidebar:
    st.markdown("### FFXI Telemetry")
    st.caption("Independent, read-only analytics")
    selected_range = st.date_input(
        "Event date range",
        value=(coverage_start, coverage_end),
        min_value=coverage_start,
        max_value=coverage_end,
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start_date, end_date = selected_range
    else:
        start_date = end_date = selected_range
    st.divider()
    st.caption(f"Snapshot: {current['generated_at'][:19].replace('T', ' ')} UTC")
    st.caption(
        "Published aggregate snapshot"
        if current["mode"] == "published_aggregate_snapshot"
        else "Local Gold models"
    )
    st.caption("Historical Git SHAs are inferred from commit timestamps.")

st.title("FFXI Agent Lab telemetry")
st.markdown(
    '<p class="coverage-note">A public, aggregate view of autonomous progression, '
    "combat reliability, navigation, and MCP operations. Raw telemetry, agent IDs, "
    "and lease IDs are excluded.</p>",
    unsafe_allow_html=True,
)

progress = date_filter(frame("progress_daily"))
combat = date_filter(frame("combat_daily"))
navigation = date_filter(frame("navigation_daily"))
mcp = frame("mcp_operations")

total_fights = int(progress["completed_fights"].sum()) if not progress.empty else 0
total_actions = int(mcp["operation_count"].sum()) if not mcp.empty else 0
action_success = (
    float(mcp["successful_operations"].sum() / mcp["operation_count"].sum())
    if not mcp.empty and mcp["operation_count"].sum()
    else 0.0
)
total_probes = int(navigation["collision_probes"].sum()) if not navigation.empty else 0
malformed = int(quality["latest_session_malformed_rows"].sum()) if not quality.empty else 0

headline = st.columns(5)
headline[0].metric("Completed fights", f"{total_fights:,}")
headline[1].metric("MCP operations", f"{total_actions:,}")
headline[2].metric("MCP success", f"{action_success:.2%}")
headline[3].metric("Collision probes", f"{total_probes:,}")
headline[4].metric("Malformed rows", f"{malformed:,}")

progress_tab, combat_tab, navigation_tab, operations_tab, quality_tab = st.tabs(
    ["Progression", "Combat", "Navigation", "MCP operations", "Data quality"]
)

with progress_tab:
    st.subheader("Autonomous progression")
    left, right = st.columns(2)
    if not progress.empty:
        left.plotly_chart(
            line_chart(
                progress,
                "completed_fights",
                "Completed fights by day",
                "Authoritative fight_complete event count",
            ),
            use_container_width=True,
        )
        milestone = progress.assign(
            milestones=progress["target_levels_reached"].fillna(0)
            + progress["objective_milestones"].fillna(0)
        )
        right.plotly_chart(
            line_chart(
                milestone,
                "milestones",
                "Level and objective milestones by day",
                "target_level_reached plus quest_item_obtained events",
                GOLD,
            ),
            use_container_width=True,
        )
        state_covered = progress["exp_metric_quality"].eq("state_observer_counter").any()
        if state_covered:
            observed_exp = progress["exp_earned"].dropna().sum()
            st.metric("EXP earned during observer coverage", f"{int(observed_exp):,}")
        else:
            st.info(
                "EXP earned is unavailable for the historical backfill. "
                "It appears only after the read-only state observer starts."
            )
    st.caption("Job breakdown is unavailable in the current event and state contracts.")

with combat_tab:
    st.subheader("Combat reliability")
    if not combat.empty:
        cards = st.columns(4)
        issued = combat["attack_issued"].sum()
        rejected = combat["attack_rejections"].sum()
        rejection_rate = rejected / (issued + rejected) if issued + rejected else 0
        cards[0].metric("Attack rejection rate", f"{rejection_rate:.2%}")
        cards[1].metric("Proactive engagements", f"{int(combat['proactive_engagements'].sum()):,}")
        cards[2].metric("Reactive engagements", f"{int(combat['reactive_engagements'].sum()):,}")
        cards[3].metric("Target-cycle errors", f"{int(combat['target_cycle_errors'].sum()):,}")
        engagement = combat.melt(
            id_vars=["event_date"],
            value_vars=["proactive_engagements", "reactive_engagements"],
            var_name="engagement_mode",
            value_name="engagements",
        )
        figure = px.bar(
            engagement,
            x="event_date",
            y="engagements",
            color="engagement_mode",
            barmode="stack",
            color_discrete_map={
                "proactive_engagements": BLUE,
                "reactive_engagements": GOLD,
            },
            title="Engagement mix by day",
        )
        figure.update_layout(
            height=360,
            paper_bgcolor="white",
            plot_bgcolor="white",
            font_color=INK,
            xaxis_title=None,
            yaxis_title=None,
            yaxis_gridcolor=GRID,
            legend_title_text=None,
        )
        st.plotly_chart(figure, use_container_width=True)
        st.caption(
            "Deaths and recoveries are observer counters; they remain unavailable "
            "outside state-snapshot coverage."
        )

with navigation_tab:
    st.subheader("Navigation performance")
    if not navigation.empty:
        cards = st.columns(4)
        probes = navigation["collision_probes"].sum()
        successful = navigation["successful_collision_probes"].sum()
        cards[0].metric("Probe success", f"{successful / probes:.1%}" if probes else "—")
        cards[1].metric("Camp relocations", f"{int(navigation['camp_relocations'].sum()):,}")
        cards[2].metric("Zone transitions", f"{int(navigation['zone_transitions'].sum()):,}")
        cards[3].metric(
            "Line-of-sight nudges",
            f"{int(navigation['line_of_sight_nudges'].sum()):,}",
        )
        chart_data = navigation.melt(
            id_vars=["event_date"],
            value_vars=[
                "camp_relocations",
                "zone_transitions",
                "line_of_sight_nudges",
                "navigation_failures",
                "navigation_retries",
            ],
            var_name="event",
            value_name="count",
        )
        figure = px.bar(
            chart_data,
            x="event_date",
            y="count",
            color="event",
            barmode="group",
            color_discrete_sequence=[BLUE, GOLD, ORANGE, "#8B5CF6", MUTED],
            title="Navigation signals by day",
        )
        figure.update_layout(
            height=390,
            paper_bgcolor="white",
            plot_bgcolor="white",
            font_color=INK,
            xaxis_title=None,
            yaxis_title=None,
            yaxis_gridcolor=GRID,
            legend_title_text=None,
        )
        st.plotly_chart(figure, use_container_width=True)
        st.caption(
            "Service-teleport operations are a dependency proxy only; the events "
            "do not establish navigation causality."
        )

with operations_tab:
    st.subheader("MCP operation reliability")
    if not mcp.empty:
        top = mcp.head(12).sort_values("operation_count")
        figure = px.bar(
            top,
            x="operation_count",
            y="operation",
            orientation="h",
            color_discrete_sequence=[BLUE],
            title="Top MCP operations by volume",
        )
        figure.update_layout(
            height=480,
            paper_bgcolor="white",
            plot_bgcolor="white",
            font_color=INK,
            xaxis_title=None,
            yaxis_title=None,
            xaxis_gridcolor=GRID,
        )
        st.plotly_chart(figure, use_container_width=True)
        display = mcp[
            [
                "operation",
                "operation_count",
                "success_rate",
                "duration_p95_ms",
                "duration_max_ms",
            ]
        ].copy()
        display["success_rate"] = display["success_rate"].map(lambda value: f"{value:.2%}")
        st.dataframe(display, width="stretch", hide_index=True)

with quality_tab:
    st.subheader("Data quality and coverage")
    if not quality.empty:
        display = quality[
            [
                "source",
                "bronze_rows",
                "distinct_event_ids",
                "null_event_times",
                "duplicate_event_ids",
                "latest_session_malformed_rows",
                "latest_session_reconciled",
            ]
        ]
        st.dataframe(display, width="stretch", hide_index=True)
        if bool(quality["latest_session_reconciled"].all()):
            st.success("Every latest source session reconciles: lines = valid JSON + malformed.")
        else:
            st.error("At least one source session failed row-count reconciliation.")
        st.caption(
            "Bronze rows are local/private. This page exposes counts and freshness only."
        )
