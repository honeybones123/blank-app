# Inputs V2 installation contract

Runtime consumes Inputs V2 as the installed `beamapp-inputs-v2` distribution.
It does not locate or import directly from a V2 checkout.

The package source is owned by this Runtime repository at
`packages/beamapp-inputs-v2`. Install the application environment from the
repository root:

```powershell
python -m pip install -r requirements.txt
```

For editable development, use:

```powershell
python -m pip install -e .\packages\beamapp-inputs-v2
```

The installed distribution must report version `0.1.0`. Its source package
retains an independent architecture and test boundary even though Runtime now
owns deployment and version control in one repository.

Verify V2 directly with:

```powershell
python -m pytest .\packages\beamapp-inputs-v2\tests -q
python .\packages\beamapp-inputs-v2\tools\architecture_check.py
```

Hosted deployments build the internal package from source through
`requirements.txt`; no external V2 checkout, binary wheel, source-path
discovery, or package feed is required.
