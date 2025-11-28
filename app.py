import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np
import pandas as pd

fastf1.Cache.enable_cache("fastf1_cache")
st.set_page_config(page_title="Lap Telemetry · Session: Race", layout="wide")

st.title("Formula 1 - Driver Telemetry Comparison")

colA, colB, colC = st.columns([1, 2, 1])

with colA:
    years = list(range(2021, 2026))
    selected_year = st.selectbox("Select Year", years, index=years.index(2025))

with colB:
    schedule = fastf1.get_event_schedule(selected_year, include_testing=False)
    gp_list = list(schedule["EventName"])
    selected_gp = st.selectbox("Select Grand Prix", gp_list)

with colC:
    session_type_map = {
        "Race": "R",
        "Qualification": "Q"
    }
    selected_session_label = st.selectbox("Select Session", list(session_type_map.keys()))
    session_type = session_type_map[selected_session_label]

if st.button("Load Session", use_container_width=True, key="load_btn"):
    session = fastf1.get_session(selected_year, selected_gp, session_type)
    session.load()
    st.session_state["session_loaded"] = True
    st.session_state["session_obj"] = session
    st.session_state["selected_session_label"] = selected_session_label
    st.success(f"READY: {selected_gp} - {selected_year}, Session: {selected_session_label}")

if st.session_state.get("session_loaded", False):

    session = st.session_state["session_obj"]
    session_label = st.session_state["selected_session_label"]
    drivers = session.drivers
    driver_codes = [session.get_driver(d)["Abbreviation"] for d in drivers]

    laps_all = session.laps

    race_mode = session_label == "Race"
    quali_mode = session_label == "Qualification"

    if race_mode:
        valid_laps = laps_all[
            (laps_all.LapNumber > 1)
            & (laps_all.LapNumber < laps_all.LapNumber.max())
            & (laps_all.PitInTime.isna())
            & (laps_all.PitOutTime.isna())
            & (laps_all.LapTime.notna())
        ]

        if not valid_laps.empty:
            fastest_lap = valid_laps.LapTime.min()
            threshold = fastest_lap + pd.Timedelta(seconds=5)
            valid_laps = valid_laps[valid_laps.LapTime < threshold]

    else:
        valid_laps = laps_all

    col1, col2, col3 = st.columns(3)

    with col1:
        driver1 = st.selectbox("Driver 1", driver_codes, key="driver1_widget")

    with col2:
        driver2 = st.selectbox("Driver 2", driver_codes, key="driver2_widget")

    if race_mode:
        with col3:
            lap_number = st.number_input("Lap Number", min_value=1, max_value=200, value=10, step=1, key="lap_widget")
    else:
        with col3:
            st.write("")
            lap_number = None

    overall_mode = False

    if st.button("Single Lap Comparison", use_container_width=True, key="view_btn"):
        st.session_state["driver1"] = driver1
        st.session_state["driver2"] = driver2
        st.session_state["lap_number"] = lap_number
        st.session_state["overall_mode"] = overall_mode
        st.session_state["telemetry_ready"] = True

    if race_mode and st.button("Overall Race Pace Profile", use_container_width=True, key="overall_btn", type="primary"):
        st.session_state["driver1"] = driver1
        st.session_state["driver2"] = driver2
        st.session_state["overall_mode"] = True
        st.session_state["telemetry_ready"] = True

if st.session_state.get("telemetry_ready", False):

    session = st.session_state["session_obj"]
    session_label = st.session_state["selected_session_label"]
    driver1 = st.session_state["driver1"]
    driver2 = st.session_state["driver2"]
    overall_mode = st.session_state.get("overall_mode", False)

    race_mode = session_label == "Race"
    quali_mode = session_label == "Qualification"

    if race_mode and not overall_mode:
        lap_selection = st.session_state["lap_number"]

    event_name = session.event.EventName.upper()
    year = session.event.year

    pastel_blue = "#6A8EAE"
    pastel_orange = "#F4A261"
    pastel_green = "#6ECB63"
    pastel_red = "#E76F51"

    layout_style = dict(
        width=1100,
        height=600,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Roboto Mono, Arial", size=16, color="black"),
        xaxis=dict(showgrid=True, gridcolor="lightgray", nticks=20, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="lightgray", nticks=20, zeroline=False)
    )

    s_grid = np.linspace(0, 1, 2000)

    def compute_driver_overall(session_obj, driver):
        driver_laps = valid_laps[valid_laps.Driver == driver]

        if driver_laps.empty:
            zeros = np.zeros_like(s_grid)
            return s_grid, zeros, zeros, zeros, zeros

        speeds = []
        throttles = []
        brakes = []
        times = []

        for _, row in driver_laps.iterrows():
            tel = row.get_car_data().add_distance()
            tel = tel.dropna(subset=["Distance", "Speed", "Throttle", "Brake", "Time"])
            if tel.empty:
                continue
            d = tel["Distance"].to_numpy()
            if d.max() == d.min():
                continue
            s = (d - d.min()) / (d.max() - d.min())
            spd = np.interp(s_grid, s, tel["Speed"])
            thr = np.interp(s_grid, s, tel["Throttle"])
            brk = np.interp(s_grid, s, tel["Brake"])
            t = tel["Time"].dt.total_seconds().to_numpy()
            t = t - t[0]
            t_interp = np.interp(s_grid, s, t)

            speeds.append(spd)
            throttles.append(thr)
            brakes.append(brk)
            times.append(t_interp)

        return (
            s_grid,
            np.mean(np.vstack(speeds), axis=0),
            np.mean(np.vstack(throttles), axis=0),
            np.mean(np.vstack(brakes), axis=0),
            np.mean(np.vstack(times), axis=0),
        )

    def compute_single_lap(session_obj, driver, lap_num):
        laps_all = session_obj.laps
        lap = laps_all[(laps_all.Driver == driver) & (laps_all.LapNumber == lap_num)]
        if lap.empty:
            zeros = np.zeros_like(s_grid)
            return s_grid, zeros, zeros, zeros, zeros

        row = lap.iloc[0]
        tel = row.get_car_data().add_distance()
        tel = tel.dropna(subset=["Distance", "Speed", "Throttle", "Brake", "Time"])

        d = tel["Distance"].to_numpy()
        if d.max() == d.min():
            zeros = np.zeros_like(s_grid)
            return s_grid, zeros, zeros, zeros, zeros

        s = (d - d.min()) / (d.max() - d.min())
        sp = np.interp(s_grid, s, tel["Speed"])
        th = np.interp(s_grid, s, tel["Throttle"])
        br = np.interp(s_grid, s, tel["Brake"])

        t = tel["Time"].dt.total_seconds().to_numpy()
        t = t - t[0]
        t_interp = np.interp(s_grid, s, t)

        return s_grid, sp, th, br, t_interp

    def compute_fastest_lap(session_obj, driver):
        laps = session_obj.laps
        fastest = laps[(laps.Driver == driver)].pick_fastest()
        if fastest is None:
            zeros = np.zeros_like(s_grid)
            return s_grid, zeros, zeros, zeros, zeros

        tel = fastest.get_car_data().add_distance()
        tel = tel.dropna(subset=["Distance", "Speed", "Throttle", "Brake", "Time"])

        d = tel["Distance"].to_numpy()
        s = (d - d.min()) / (d.max() - d.min())

        sp = np.interp(s_grid, s, tel["Speed"])
        th = np.interp(s_grid, s, tel["Throttle"])
        br = np.interp(s_grid, s, tel["Brake"])

        t = tel["Time"].dt.total_seconds().to_numpy()
        t = t - t[0]
        t_interp = np.interp(s_grid, s, t)

        return s_grid, sp, th, br, t_interp

    if quali_mode:
        dist, sp1, th1, br1, t1 = compute_fastest_lap(session, driver1)
        _, sp2, th2, br2, t2 = compute_fastest_lap(session, driver2)
        title_text = f"{event_name} {year} - QUALIFICATION - FASTEST LAP"

    elif overall_mode:
        dist, sp1, th1, br1, t1 = compute_driver_overall(session, driver1)
        _, sp2, th2, br2, t2 = compute_driver_overall(session, driver2)
        title_text = f"{event_name} {year} - RACE - AVERAGE PACE"

    else:
        dist, sp1, th1, br1, t1 = compute_single_lap(session, driver1, lap_selection)
        _, sp2, th2, br2, t2 = compute_single_lap(session, driver2, lap_selection)
        title_text = f"{event_name} {year} - RACE - LAP {lap_selection}"

    L = min(len(t1), len(t2), len(dist))
    dist_aligned = dist[:L]
    delta = t1[:L] - t2[:L]

    gain_mask = delta < 0
    lose_mask = delta > 0

    th1_aligned = th1[:L]
    total_length = dist_aligned[-1] - dist_aligned[0] if dist_aligned[-1] > dist_aligned[0] else 1.0
    min_segment_length = 0.05 * total_length

    straight_mask = np.zeros(L, dtype=bool)
    i = 0
    while i < L:
        if th1_aligned[i] >= 99:
            start_i = i
            while i + 1 < L and th1_aligned[i + 1] >= 99:
                i += 1
            seg_len = dist_aligned[i] - dist_aligned[start_i]
            if seg_len >= min_segment_length:
                straight_mask[start_i:i + 1] = True
            i += 1
        else:
            i += 1

    corner_mask = ~straight_mask

    if straight_mask.any():
        straight_diff = np.mean(sp1[:L][straight_mask] - sp2[:L][straight_mask])
    else:
        straight_diff = 0.0

    if corner_mask.any():
        corner_diff = np.mean(sp1[:L][corner_mask] - sp2[:L][corner_mask])
    else:
        corner_diff = 0.0

    straight_leader = driver1 if straight_diff > 0 else driver2
    corner_leader = driver1 if corner_diff > 0 else driver2

    st.markdown(
        f"""
        <div style="padding: 15px; border-radius: 10px; background-color: #eef2f7; margin-bottom: 20px; font-size: 18px;">
        <b>Straight Speed Advantage:</b> {straight_leader} {abs(straight_diff):.2f} km/h<br>
        <b>Corner Speed Advantage:</b> {corner_leader} {abs(corner_diff):.2f} km/h
        </div>
        """,
        unsafe_allow_html=True
    )

    fig_speed = go.Figure()
    fig_speed.add_trace(go.Scatter(x=dist, y=sp1, mode="lines", name=f"{driver1}", line=dict(color=pastel_blue)))
    fig_speed.add_trace(go.Scatter(x=dist, y=sp2, mode="lines", name=f"{driver2}", line=dict(color=pastel_orange)))

    fig_speed.update_layout(title=dict(text=title_text + " - SPEED", x=0.0), **layout_style)
    st.plotly_chart(fig_speed)

    fig_throttle = go.Figure()
    fig_throttle.add_trace(go.Scatter(x=dist, y=th1, mode="lines", name=f"{driver1}", line=dict(color=pastel_blue)))
    fig_throttle.add_trace(go.Scatter(x=dist, y=th2, mode="lines", name=f"{driver2}", line=dict(color=pastel_orange)))
    fig_throttle.update_layout(title=dict(text=title_text + " - THROTTLE", x=0.0), **layout_style)
    st.plotly_chart(fig_throttle)

    fig_brake = go.Figure()
    fig_brake.add_trace(go.Scatter(x=dist, y=br1, mode="lines", name=f"{driver1}", line=dict(color=pastel_blue)))
    fig_brake.add_trace(go.Scatter(x=dist, y=br2, mode="lines", name=f"{driver2}", line=dict(color=pastel_orange)))
    fig_brake.update_layout(title=dict(text=title_text + " - BRAKE", x=0.0), **layout_style)
    st.plotly_chart(fig_brake)

    fig_delta = go.Figure()
    fig_delta.add_trace(go.Scatter(x=dist_aligned[gain_mask], y=delta[gain_mask], mode="lines", name="Gain", line=dict(color=pastel_green)))
    fig_delta.add_trace(go.Scatter(x=dist_aligned[lose_mask], y=delta[lose_mask], mode="lines", name="Loss", line=dict(color=pastel_red)))
    fig_delta.update_layout(title=dict(text=title_text + " - DELTA TIME", x=0.0), **layout_style)
    st.plotly_chart(fig_delta)