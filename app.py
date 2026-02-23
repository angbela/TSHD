"""
Streamlit App for TSHD Dredging Discrete Event Simulation
Interactive web interface for configuring and running simulations
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from des_framework import Simulation
from tshd import TSHD, TSHDConfig, TSHDState
from segments import SegmentManager

# Page configuration
st.set_page_config(
    page_title="TSHD Dredging Simulation",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)


def run_simulation_streamlit(fleet_vessels, target_volume: float, segment_manager: SegmentManager | None = None):
    """
    Run simulation until the target volume is dredged and return results.

    fleet_vessels: list of (type_label: str, config: TSHDConfig)
    """
    sim = Simulation()
    sim.run_id = f"run_{int(np.random.randint(0, 1_000_000_000))}"
    sim.segment_manager = segment_manager
    dredgers = []

    cycle_times = []
    for type_label, cfg in fleet_vessels:
        mean_cycle = (
            cfg.dredging_time
            + cfg.distance_to_da / cfg.speed_to_da
            + cfg.dumping_time
            + cfg.distance_back / cfg.speed_back
        )
        cycle_times.append(mean_cycle)

        dredger = TSHD(f"{type_label}", cfg)
        dredger.type_label = type_label
        dredgers.append(dredger)
        sim.entities[dredger.entity_id] = dredger
        dredger.start_work(sim)

    # Run in increments based on fleet's fastest mean cycle (keeps loop count reasonable)
    step_h = max(0.25, float(min(cycle_times)) if cycle_times else 1.0)
    current_end_time = step_h
    max_simulation_time = 24 * 365  # safety cap: 1 year in hours

    while True:
        sim.run(end_time=current_end_time)

        total_material = sum(d.total_dredged for d in dredgers)
        if total_material >= target_volume or sim.clock >= max_simulation_time:
            break

        current_end_time += step_h

    return sim, dredgers


def _hours_days_str(hours: float) -> str:
    days = hours / 24.0
    return f"{hours:.1f} hours / {days:.1f} days"


def _collect_duration_samples(dredgers, run_idx: int):
    rows = []
    for dredger in dredgers:
        dredger_type = getattr(dredger, "type_label", dredger.entity_id)
        for e in dredger.event_log:
            if "duration_h" in e and "task" in e:
                row = {
                    "run": run_idx,
                    "dredger": dredger.entity_id,
                    "dredger_type": dredger_type,
                    "task": e["task"],
                    "duration_h": float(e["duration_h"]),
                }
                if "segment" in e:
                    row["segment"] = e["segment"]
                if "distance_nm" in e:
                    row["distance_nm"] = float(e["distance_nm"])
                if "volume_m3" in e:
                    row["volume_m3"] = float(e["volume_m3"])
                rows.append(row)
    return rows

def create_state_timeline(dredgers, simulation_time):
    """Create timeline visualization of state changes"""
    fig = go.Figure()
    
    state_colors = {
        'dredging': '#2ecc71',
        'moving_to_da': '#3498db',
        'dumping': '#e74c3c',
        'moving_back': '#f39c12',
        'idle': '#95a5a6'
    }
    
    state_order = ['dredging', 'moving_to_da', 'dumping', 'moving_back', 'idle']
    state_y_positions = {state: i for i, state in enumerate(state_order)}
    
    for dredger in dredgers:
        if not dredger.state_history:
            continue
            
        # Create segments for each state
        prev_time = 0
        prev_state = 'idle'
        
        for entry in dredger.state_history:
            if prev_time < entry['time']:
                # Add segment
                fig.add_trace(go.Scatter(
                    x=[prev_time, entry['time']],
                    y=[state_y_positions[prev_state], state_y_positions[prev_state]],
                    mode='lines',
                    name=f"{dredger.entity_id} - {prev_state}",
                    line=dict(color=state_colors.get(prev_state, '#95a5a6'), width=8),
                    showlegend=False,
                    hovertemplate=f"{dredger.entity_id}<br>State: {prev_state}<br>Time: %{{x:.2f}}h<extra></extra>"
                ))
            prev_time = entry['time']
            prev_state = entry['state']
        
        # Add final segment if simulation ended
        if prev_time < simulation_time:
            fig.add_trace(go.Scatter(
                x=[prev_time, simulation_time],
                y=[state_y_positions[prev_state], state_y_positions[prev_state]],
                mode='lines',
                name=f"{dredger.entity_id} - {prev_state}",
                line=dict(color=state_colors.get(prev_state, '#95a5a6'), width=8),
                showlegend=False,
                hovertemplate=f"{dredger.entity_id}<br>State: {prev_state}<br>Time: %{{x:.2f}}h<extra></extra>"
            ))
    
    fig.update_layout(
        title="TSHD State Timeline",
        xaxis_title="Time (hours)",
        yaxis=dict(
            tickmode='array',
            tickvals=list(range(len(state_order))),
            ticktext=state_order,
            title="State"
        ),
        height=400,
        hovermode='closest'
    )
    
    return fig

def create_time_distribution_chart(stats):
    """Create pie chart of time distribution"""
    labels = ['Dredging', 'Moving', 'Dumping']
    values = [
        stats['total_dredging_time'],
        stats['total_moving_time'],
        stats['total_dumping_time']
    ]
    
    colors = ['#2ecc71', '#3498db', '#e74c3c']
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker_colors=colors
    )])
    
    fig.update_layout(
        title="Time Distribution",
        height=300
    )
    
    return fig

def main():
    # Header
    st.markdown('<h1 class="main-header">🚢 TSHD Dredging Discrete Event Simulation</h1>', unsafe_allow_html=True)
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Simulation Configuration")

        tab_project, tab_fleet, tab_stoch, tab_run = st.tabs(
            ["Project", "Fleet", "Stochastic", "Running"]
        )

        with tab_project:
            st.subheader("Project Parameters (Contractor View)")

            use_segmentation = st.checkbox("Use channel segmentation", value=False, key="use_segmentation")

            target_volume = st.number_input(
                "Total Material to be Dredged (m³)",
                min_value=1_000.0,
                max_value=10_000_000.0,
                value=100_000.0,
                step=1_000.0,
                help="Total project volume to be dredged",
                key="target_volume",
                disabled=use_segmentation,
            )

            colp1, colp2 = st.columns(2)
            with colp1:
                distance_to_da = st.number_input(
                    "Distance to DA (nm)",
                    min_value=1.0,
                    max_value=50.0,
                    value=5.0,
                    step=0.5,
                    key="distance_to_da",
                    disabled=use_segmentation,
                )
            with colp2:
                st.caption("Assumption: distance back = distance to DA")
                distance_back = float(distance_to_da)

            segment_manager = None
            if use_segmentation:
                st.markdown("**Segments table (Segment / Volume m³)**")
                default_segments = pd.DataFrame(
                    {
                        "Segment": [1, 2, 3, 4, 5, 6, 7, 8],
                        "Volume": [387_371, 1_476_950, 552_566, 66_186, 217, 189_128, 0, 14_676],
                    }
                )
                seg_df = st.data_editor(
                    default_segments,
                    use_container_width=True,
                    num_rows="fixed",
                    key="segments_table",
                )

                segment_length_nm = st.number_input(
                    "Segment length (nm)",
                    min_value=0.1,
                    max_value=50.0,
                    value=1.0,
                    step=0.1,
                    help="Equal length for all segments. Segment 1 is nearest to DA reference point.",
                    key="segment_length_nm",
                )

                # sanitize volumes
                seg_df = seg_df.copy()
                seg_df["Volume"] = pd.to_numeric(seg_df["Volume"], errors="coerce").fillna(0.0)
                seg_df["Volume"] = seg_df["Volume"].clip(lower=0.0)

                segment_volumes = seg_df.sort_values("Segment")["Volume"].tolist()
                target_volume = float(sum(segment_volumes))
                st.info(f"Target volume is derived from segments: {target_volume:,.0f} m³")

                segment_manager = SegmentManager(segment_volumes_m3=segment_volumes, segment_length_nm=float(segment_length_nm))
                # in segmentation mode, distance to DA is derived from segment index:
                # distance_nm = (segment_index - 1) * segment_length_nm
                distance_to_da = 0.0
                distance_back = 0.0

        with tab_fleet:
            st.subheader("Fleet (Multiple Dredger Types)")

            fleet_rows = []
            for slot in [1, 2, 3, 4, 5]:
                with st.expander(f"Dredger {slot}", expanded=(slot == 1)):
                    enabled = st.checkbox(
                        "Enable this dredger", value=(slot == 1), key=f"fleet_enabled_{slot}"
                    )

                    type_label = st.text_input(
                        "Dredger type/name (label)",
                        value=f"TSHD_{slot}",
                        key=f"fleet_label_{slot}",
                        help="Used for grouping results and PDFs (e.g., 'Small', 'Large', 'Unit-A')",
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        hopper_capacity = st.number_input(
                            "Hopper Capacity (m³)",
                            min_value=1000.0,
                            max_value=50000.0,
                            value=5000.0,
                            step=500.0,
                            key=f"fleet_hopper_{slot}",
                        )
                        dredging_time = st.number_input(
                            "Dredging Time (hours)",
                            min_value=0.5,
                            max_value=10.0,
                            value=2.0,
                            step=0.1,
                            help="Mean time to fill hopper",
                            key=f"fleet_dredging_{slot}",
                        )
                        dumping_time = st.number_input(
                            "Dumping Time (hours)",
                            min_value=0.1,
                            max_value=3.0,
                            value=0.5,
                            step=0.05,
                            help="Mean time to empty hopper",
                            key=f"fleet_dumping_{slot}",
                        )
                    with c2:
                        speed_to_da = st.number_input(
                            "Speed to DA (knots)",
                            min_value=5.0,
                            max_value=25.0,
                            value=10.0,
                            step=0.5,
                            key=f"fleet_speed_to_da_{slot}",
                        )
                        speed_back = st.number_input(
                            "Speed Back (knots)",
                            min_value=5.0,
                            max_value=25.0,
                            value=10.0,
                            step=0.5,
                            key=f"fleet_speed_back_{slot}",
                        )

                    if enabled and type_label.strip():
                        fleet_rows.append(
                            {
                                "type_label": type_label.strip(),
                                "hopper_capacity": float(hopper_capacity),
                                "dredging_time": float(dredging_time),
                                "dumping_time": float(dumping_time),
                                "speed_to_da": float(speed_to_da),
                                "speed_back": float(speed_back),
                            }
                        )

            fleet_df = pd.DataFrame(fleet_rows)
            if not fleet_df.empty:
                st.caption("Fleet summary (enabled types only):")
                st.dataframe(
                    fleet_df[
                        [
                            "type_label",
                            "hopper_capacity",
                            "dredging_time",
                            "dumping_time",
                            "speed_to_da",
                            "speed_back",
                        ]
                    ],
                    hide_index=True,
                )

        with tab_stoch:
            st.subheader("Stochastic Parameters (Std Dev %)")
            dredging_stdev_pct = st.number_input(
                "Dredging Time Std Dev (%)",
                min_value=0.0,
                max_value=50.0,
                value=10.0,
                step=1.0,
                help="Standard deviation as percentage of mean dredging time",
                key="dredging_stdev_pct",
            )
            dumping_stdev_pct = st.number_input(
                "Dumping Time Std Dev (%)",
                min_value=0.0,
                max_value=50.0,
                value=10.0,
                step=1.0,
                help="Standard deviation as percentage of mean dumping time",
                key="dumping_stdev_pct",
            )
            moving_stdev_pct = st.number_input(
                "Moving Operations Std Dev (%)",
                min_value=0.0,
                max_value=50.0,
                value=15.0,
                step=1.0,
                help="Standard deviation as percentage of mean travel time (applies to both moving to DA and back)",
                key="moving_stdev_pct",
            )

        with tab_run:
            st.subheader("Running Parameters")
            n_runs = st.number_input(
                "Number of DES Runs",
                min_value=1,
                max_value=200,
                value=30,
                step=1,
                help="Run the DES multiple times to estimate average project duration",
                key="n_runs",
            )
            use_fixed_seed = st.checkbox("Use fixed random seed (reproducible)", value=False, key="use_fixed_seed")
            seed_value = st.number_input(
                "Random seed",
                min_value=0,
                max_value=1_000_000_000,
                value=42,
                step=1,
                disabled=not use_fixed_seed,
                key="seed_value",
            )

            # Run button
            run_sim = st.button("▶️ Run Simulation", type="primary", use_container_width=True)
    
    # Main content area
    if run_sim:
        if fleet_df.empty:
            st.error("Please enable at least 1 dredger in the Fleet tab.")
            return

        # Build fleet configs (each type can have different mean parameters)
        fleet_vessels = []
        for row in fleet_df.to_dict(orient="records"):
            cfg = TSHDConfig(
                dredging_time=row["dredging_time"],
                dredging_stdev_pct=dredging_stdev_pct,
                speed_to_da=row["speed_to_da"],
                distance_to_da=distance_to_da,
                moving_stdev_pct=moving_stdev_pct,
                dumping_time=row["dumping_time"],
                dumping_stdev_pct=dumping_stdev_pct,
                speed_back=row["speed_back"],
                distance_back=distance_to_da,
                hopper_capacity=row["hopper_capacity"],
            )
            fleet_vessels.append((row["type_label"], cfg))

        # Run simulations with progress (driven by target volume)
        with st.spinner("Running simulation(s)..."):
            run_summaries = []
            duration_rows = []
            sims = []
            dredgers_by_run = []

            for run_idx in range(int(n_runs)):
                if use_fixed_seed:
                    np.random.seed(int(seed_value) + run_idx)

                # IMPORTANT: Segment manager must be per-run (it is stateful)
                sm_for_run = None
                if use_segmentation and segment_manager is not None:
                    sm_for_run = SegmentManager(segment_manager.remaining_m3, segment_manager.segment_length_nm)

                sim, dredgers = run_simulation_streamlit(fleet_vessels, target_volume, segment_manager=sm_for_run)
                sims.append(sim)
                dredgers_by_run.append(dredgers)

                run_summaries.append(
                    {
                        "run": run_idx,
                        "simulation_time_h": float(sim.clock),
                        "cycles": int(sim.get_statistics()["dredging_cycles"]),
                    }
                )
                duration_rows.extend(_collect_duration_samples(dredgers, run_idx))

            results_df = pd.DataFrame(run_summaries)
            durations_df = pd.DataFrame(duration_rows)
        
        st.success("✅ Simulation completed!")
        
        # Statistics section
        st.header("📊 Simulation Statistics")

        avg_time = results_df["simulation_time_h"].mean()

        # Key metrics (keep only what you asked for)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Target Volume", f"{target_volume:,.0f} m³")
        with col2:
            st.metric("Average Project Duration", _hours_days_str(avg_time))

        st.subheader("🧾 Per-run results table")
        table_df = results_df.copy()
        table_df["duration_str"] = table_df["simulation_time_h"].apply(_hours_days_str)
        st.dataframe(
            table_df[["run", "duration_str", "simulation_time_h", "cycles"]],
            use_container_width=True,
            hide_index=True,
        )

        if "segment" in durations_df.columns and durations_df["segment"].notna().any():
            st.subheader("📍 Segment recap")
            seg_df = durations_df[durations_df["segment"].notna()].copy()
            seg_df["segment"] = seg_df["segment"].astype(int)

            vol_df = (
                seg_df[seg_df["task"] == "dredging"]
                .dropna(subset=["volume_m3"])
                .groupby("segment")["volume_m3"]
                .sum()
            )

            dist_df = (
                seg_df.dropna(subset=["distance_nm"])
                .groupby("segment")["distance_nm"]
                .mean()
            )

            work_df = seg_df.groupby("segment")["duration_h"].sum()

            all_segments = sorted(set(vol_df.index) | set(dist_df.index) | set(work_df.index))
            recap_df = pd.DataFrame({"Segment": all_segments})
            recap_df["Volume"] = recap_df["Segment"].map(vol_df).fillna(0.0)
            recap_df["Average_distance_DA"] = recap_df["Segment"].map(dist_df)
            recap_df["Total_working_hours"] = recap_df["Segment"].map(work_df).fillna(0.0)

            st.dataframe(
                recap_df,
                use_container_width=True,
                hide_index=True,
            )

        # Diagnostics (collapsed by default for neat results)
        with st.expander("📈 Work task duration PDFs (stochastic evidence)", expanded=False):
            if not durations_df.empty:
                task_order = ["dredging", "moving_to_da", "dumping", "moving_back"]

                dredger_types = sorted(durations_df["dredger_type"].dropna().unique().tolist())
                for dredger_type in dredger_types:
                    st.markdown(f"**Dredger type: `{dredger_type}`**")
                    for task in task_order:
                        task_df = durations_df[
                            (durations_df["task"] == task)
                            & (durations_df["dredger_type"] == dredger_type)
                        ]
                        if task_df.empty:
                            continue
                        fig_task = px.histogram(
                            task_df,
                            x="duration_h",
                            nbins=30,
                            histnorm="probability density",
                            title=f"{dredger_type} — {task} duration PDF (hours)",
                        )
                        st.plotly_chart(fig_task, use_container_width=True)
            else:
                st.warning("No duration samples captured yet (unexpected).")
    
    else:
        # Welcome message
        st.info("👈 Configure your simulation parameters in the sidebar and click 'Run Simulation' to start!")
        
        st.markdown("""
        ### About This Simulation
        
        This discrete event simulation models the workflow of a **Trailing Suction Hopper Dredger (TSHD)**:
        
        1. **Dredging** - Filling the hopper with dredged material from the navigation channel
        2. **Moving to Dumping Area** - Traveling to the designated dumping location
        3. **Dumping** - Emptying the hopper at the dumping area
        4. **Moving Back** - Returning to the navigation channel to continue dredging
        
        ### Features
        
        - ⚙️ Configurable TSHD parameters (hopper capacity, speeds, distances)
        - 📊 Real-time statistics and visualizations
        - 📈 State timeline visualization
        - 📦 Material tracking over time
        - 🚢 Support for multiple dredgers
        
        ### How to Use
        
        1. Adjust simulation parameters in the sidebar
        2. Configure TSHD operational parameters
        3. Set travel distances and speeds
        4. Click "Run Simulation" to execute
        5. View results, charts, and statistics
        """)

if __name__ == "__main__":
    main()
