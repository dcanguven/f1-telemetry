import streamlit as st
import fastf1
import plotly.graph_objects as go
import numpy as np

fastf1.Cache.enable_cache("fastf1_cache")
st.set_page_config(page_title="Lap Telemetry · Session: Race", layout="wide")

st.title("Lap Telemetry - Session: Race")

colA, colB = st.columns([1, 2])

with colA:
    years = list(range(2021, 2026))
    selected_year = st.selectbox("Select Year", years)

with colB:
    schedule = fastf1.get_event_schedule(selected_year, include_testing=False)
    gp_list = list(schedule["EventName"])
    selected_gp = st.selectbox("Select Grand Prix", gp_list)

session_type = "R"

if st.button("Load Session"):
    session = fastf1.get_session(selected_year, selected_gp, session_type)
    session.load()
    st.session_state["session_loaded"] = True
    st.session_state["session_obj"] = session
    st.success(f"{selected_gp} {selected_year} Race Loaded")

if st.session_state.get("session_loaded", False):
    session = st.session_state["session_obj"]
    drivers = session.drivers
    driver_codes = [session.get_driver(d)["Abbreviation"] for d in drivers]

    col1, col2, col3 = st.columns(3)

    with col1:
        driver1 = st.selectbox("Driver 1", driver_codes, key="driver1_widget")

    with col2:
        driver2 = st.selectbox("Driver 2", driver_codes, key="driver2_widget")

    with col3:
        lap_number = st.number_input("Lap Number", min_value=1, max_value=100, value=58, key="lap_widget")

    if st.button("View Telemetry Data"):
        st.session_state["driver1"] = driver1
        st.session_state["driver2"] = driver2
        st.session_state["lap_number"] = lap_number
        st.session_state["telemetry_ready"] = True
        st.success("Telemetry data is ready")

if st.session_state.get("telemetry_ready", False):

    session = st.session_state["session_obj"]
    driver1 = st.session_state["driver1"]
    driver2 = st.session_state["driver2"]
    lap_number = st.session_state["lap_number"]

    event_name = session.event.EventName.upper()
    year = session.event.year
    session_name = session.name.upper()
    title_text = f"{event_name} {year} - {session_name} - LAP {lap_number}"

    lap1 = session.laps[(session.laps.Driver == driver1) & (session.laps.LapNumber == lap_number)].iloc[0]
    lap2 = session.laps[(session.laps.Driver == driver2) & (session.laps.LapNumber == lap_number)].iloc[0]

    car1 = lap1.get_car_data().add_distance()
    car2 = lap2.get_car_data().add_distance()

    layout_style = dict(
        width=1100,
        height=600,
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Roboto Mono, Arial", size=16, color="black"),
        xaxis=dict(showgrid=True, gridcolor="lightgray", nticks=20, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="lightgray", nticks=20, zeroline=False)
    )

    fig_speed = go.Figure()
    fig_speed.add_trace(go.Scatter(x=car1["Distance"], y=car1["Speed"], mode="lines", name=f"{driver1} Speed", line=dict(color="blue")))
    fig_speed.add_trace(go.Scatter(x=car2["Distance"], y=car2["Speed"], mode="lines", name=f"{driver2} Speed", line=dict(color="orange")))
    fig_speed.update_layout(title=dict(text=title_text + " SPEED", x=0.0), **layout_style)
    st.plotly_chart(fig_speed)

    fig_throttle = go.Figure()
    fig_throttle.add_trace(go.Scatter(x=car1["Distance"], y=car1["Throttle"], mode="lines", name=f"{driver1} Throttle", line=dict(color="blue")))
    fig_throttle.add_trace(go.Scatter(x=car2["Distance"], y=car2["Throttle"], mode="lines", name=f"{driver2} Throttle", line=dict(color="orange")))
    fig_throttle.update_layout(title=dict(text=title_text + " THROTTLE", x=0.0), **layout_style)
    st.plotly_chart(fig_throttle)

    fig_brake = go.Figure()
    fig_brake.add_trace(go.Scatter(x=car1["Distance"], y=car1["Brake"], mode="lines", name=f"{driver1} Brake", line=dict(color="blue")))
    fig_brake.add_trace(go.Scatter(x=car2["Distance"], y=car2["Brake"], mode="lines", name=f"{driver2} Brake", line=dict(color="orange")))
    fig_brake.update_layout(title=dict(text=title_text + " BRAKE", x=0.0), **layout_style)
    st.plotly_chart(fig_brake)

    def compute_delta(l1, l2):
        t1 = l1.get_car_data().add_distance()
        t2 = l2.get_car_data().add_distance()
        d_min = max(t1["Distance"].min(), t2["Distance"].min())
        d_max = min(t1["Distance"].max(), t2["Distance"].max())
        common = np.linspace(d_min, d_max, 2000)
        time1 = np.interp(common, t1["Distance"], t1["Time"].dt.total_seconds())
        time2 = np.interp(common, t2["Distance"], t2["Time"].dt.total_seconds())
        return common, time1 - time2

    dist, delta = compute_delta(lap1, lap2)

    gain_mask = delta < 0
    lose_mask = delta > 0

    fig_delta = go.Figure()

    fig_delta.add_trace(go.Scatter(
        x=dist[gain_mask],
        y=delta[gain_mask],
        mode="lines",
        name="Gain",
        line=dict(color="green")
    ))

    fig_delta.add_trace(go.Scatter(
        x=dist[lose_mask],
        y=delta[lose_mask],
        mode="lines",
        name="Loss",
        line=dict(color="red")
    ))

    fig_delta.update_layout(title=dict(text=title_text + " DELTA TIME", x=0.0), **layout_style)
    st.plotly_chart(fig_delta)