# Beamapp Inputs V2 Lab

Standalone, isolated proof for the Beamapp Inputs V2 architecture.

The measurable end-state is defined in
`outputs/INPUTS_V2_COMPLETION_GOAL.md`. This lab is not complete while that
goal's acceptance conditions remain open.

V2 remains independent of Runtime internals. Runtime consumes V2 through the
installed distribution and its own adapter; V2 must not import Runtime modules.

## Run

```powershell
python -m pip install -e ".[test]"
python -m streamlit run src/inputs_v2/app.py --server.port 8511
```

Runtime consumes V2 as the installed `beamapp-inputs-v2` distribution. Runtime
must not locate this checkout directly or add its `src` directory to
`sys.path`. For a two-repository development checkout, install this package
into the same Python environment used to run Runtime.

## Verify

```powershell
python -m pytest -q
```

The first slice contains rectangular beam geometry, one bottom-reinforcement row,
an immutable canonical input revision, and a diagram derived directly from that revision.
