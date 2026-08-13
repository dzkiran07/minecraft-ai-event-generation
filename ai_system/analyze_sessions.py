import pandas as pd
import matplotlib.pyplot as plt

MODES = ["static", "rules", "ml"]
COLORS = {"static": "#2a78d6", "rules": "#eb6834", "ml": "#1baf7a"}

df = pd.read_csv("session_log.csv").sort_values("timestamp").reset_index(drop=True)


def find_session(df, mode):
    sub = df[df.engine_mode == mode].reset_index(drop=True)
    ends = sub[sub.decision == "session_end"]
    last_end_ts = ends.iloc[-1]["timestamp"]
    prior_ends = ends.iloc[:-1]
    start_ts = prior_ends.iloc[-1]["timestamp"] if len(prior_ends) else -1
    return sub[(sub.timestamp > start_ts) & (sub.timestamp <= last_end_ts)].reset_index(drop=True)


def analyze_session(session):
    end_row = session[session.decision == "session_end"].iloc[-1]
    session_length = end_row.session_length
    action_count = end_row.action_count
    n_decisions = len(session[~session.decision.isin(["none", "session_end"])])

    if len(session) <= 1:
        return dict(session_length=session_length, action_count=action_count,
                     n_decisions=n_decisions, idle_time=None, active_time=None, activity_rate=None)

    session = session.copy()
    session["dt"] = session["timestamp"].diff().fillna(0)
    is_idle_tick = session["action_count"] == session["action_count"].shift(1)
    is_idle_tick.iloc[0] = False
    idle_time = round(session.loc[is_idle_tick, "dt"].sum(), 1)
    active_time = round(session_length - idle_time, 1)
    activity_rate = round(action_count / active_time, 3) if active_time > 0 else None
    return dict(session_length=session_length, action_count=action_count, n_decisions=n_decisions,
                idle_time=idle_time, active_time=active_time, activity_rate=activity_rate)


results = {}
for mode in MODES:
    session = find_session(df, mode)
    results[mode] = analyze_session(session)

summary = pd.DataFrame(results).T
summary.index.name = "engine_mode"
print(summary.fillna("N/A").to_string())

fig1, ax1 = plt.subplots(figsize=(5, 4), facecolor="#fcfcfb")
ax1.set_facecolor("#fcfcfb")
lengths = [results[m]["session_length"] for m in MODES]
bars1 = ax1.bar(MODES, lengths, color=[COLORS[m] for m in MODES], width=0.5)
ax1.bar_label(bars1, fmt="%.0fs", color="#0b0b0b", padding=3)
ax1.set_title("Session Length by Engine Mode", color="#0b0b0b")
ax1.set_ylabel("Session length (s)", color="#52514e")
ax1.spines[["top", "right"]].set_visible(False)
ax1.tick_params(colors="#52514e")
ax1.grid(axis="y", color="#e1e0d9", linewidth=0.8, zorder=0)
ax1.set_axisbelow(True)
fig1.tight_layout()
fig1.savefig("session_length_comparison.png", dpi=150)

fig2, ax2 = plt.subplots(figsize=(5, 4), facecolor="#fcfcfb")
ax2.set_facecolor("#fcfcfb")
decisions = [results[m]["n_decisions"] for m in MODES]
bars2 = ax2.bar(MODES, decisions, color=[COLORS[m] for m in MODES], width=0.5)
ax2.bar_label(bars2, color="#0b0b0b", padding=3)
ax2.set_title("Real Decisions Dispatched by Engine Mode", color="#0b0b0b")
ax2.set_ylabel("Decision count", color="#52514e")
ax2.spines[["top", "right"]].set_visible(False)
ax2.tick_params(colors="#52514e")
ax2.grid(axis="y", color="#e1e0d9", linewidth=0.8, zorder=0)
ax2.set_axisbelow(True)
fig2.tight_layout()
fig2.savefig("decisions_comparison.png", dpi=150)

print("\nSaved session_length_comparison.png and decisions_comparison.png")
