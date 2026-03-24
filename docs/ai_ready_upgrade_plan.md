# AI-Ready Upgrade Plan for Crossroads Traffic Light Simulation

## 1. Current Coverage vs Target

### Already implemented (or partially implemented)
- Multiple control strategies: `time_based`, `traffic_responsive`, `adaptive`, `ml_optimized`, `coordinated`, `emergency`.
- Vehicle diversity: car, bus, truck, motorcycle, emergency.
- Pedestrian entities and walk/stop signaling.
- Weather and day/night effects.
- Random incident generation (accident/closure/weather shift) and obstacle modeling.
- Real-time metrics: wait time, throughput, queue lengths, average speed, close calls.
- Congestion heatmap data and visualization.
- Scenario save/load and JSON metric export.

### Newly improved in this iteration
- UI now exposes all traffic algorithms and explains each mode.
- Interactive sliders added for:
  - simulation speed
  - traffic density
  - NS green timing
  - EW green timing
- Live UI toggles added for analytics panel, heatmap visibility, stats card, and rush-hour mode.
- Toolbar quick actions for analytics, save, load, and export.
- Heatmap/stats/analytics are now rendered directly in the live simulation workflow.

### Still missing relative to full target
- True 3D rendering engine and camera controls.
- Split-screen side-by-side simulation with independent algorithms running in parallel.
- Full road layout drag-and-drop editor (lanes, signals, geometry graph).
- Scenario authoring wizard with scripted event timeline and parameter sweeps.
- Machine learning training pipeline with model persistence and recommendations.
- Historical replay/timeline scrubber for recorded sessions.
- External real-time traffic API ingestion and normalization.

## 2. Proposed Architecture Expansion

## Data and Domain Layer
- Introduce `RoadGraph` model for editable intersections (nodes, lanes, turn constraints).
- Introduce `ScenarioTimeline` model for deterministic events (closures, incidents, weather windows).
- Introduce `ReplayFrame` stream for full simulation state snapshots.

## Simulation Layer
- Create multi-instance simulation runner to support A/B strategy comparison.
- Add deterministic seed mode for fair algorithm benchmarking.
- Add event scheduler for incidents, emergency routing priorities, and construction windows.

## AI Layer
- Add `PolicyAdvisor` service that consumes KPI history and suggests timing changes.
- Persist feature vectors and outcomes for offline training (`data/exports/training/`).
- Start with contextual bandit baseline, then graduate to RL policy if needed.

## Visualization and UX Layer
- Add a `DashboardLayout` manager with dockable/collapsible panes.
- Add split-screen viewport manager with independent render contexts.
- Add timeline replay control (play, pause, scrub, speed).
- Add layout editor mode with drag handles and snapping.

## Integration Layer
- Add `TrafficDataProvider` interface:
  - `MockTrafficProvider`
  - `CsvTrafficProvider`
  - `ApiTrafficProvider` (provider-specific adapters)

## 3. Delivery Plan

## Phase 1 (Done or in progress)
- Improve operational UI controls.
- Improve mode explainability.
- Make analytics and heatmap always accessible.

## Phase 2
- Multi-run strategy comparison engine with synchronized seeds.
- KPI report generator with side-by-side summary table and export.
- Replay recording pipeline and timeline UI.

## Phase 3
- Layout editor MVP (single intersection and lane graph editing).
- Scenario builder with event timeline and condition presets.

## Phase 4
- External traffic data adapter and ingestion pipeline.
- ML recommendation service with confidence score and recommended timing plan.

## Phase 5
- 3D visualization migration path (e.g., Panda3D/Unity/Godot bridge, or WebGL front-end).
- Production-grade API surface and plugin system for new controllers.

## 4. Suggested KPIs for AI Readiness
- Mean wait time by approach and by vehicle type.
- 95th percentile queue length.
- Throughput per 5-minute equivalent window.
- Emergency vehicle corridor clearance time.
- Pedestrian crossing delay and compliance.
- Incident recovery time.
- Strategy score: weighted utility function for comparative benchmarking.

## 5. Immediate Next Build Tasks
1. Add deterministic dual-simulation compare mode with shared random seed.
2. Add replay recorder and timeline scrubber in analytics panel.
3. Add road-graph editor primitives (lane add/remove, signal placement).
4. Add `TrafficDataProvider` abstraction and mock API adapter.
5. Add exporter for strategy comparison reports (CSV + JSON).
