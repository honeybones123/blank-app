# Inputs V2 installation contract

Runtime consumes Inputs V2 as the installed `beamapp-inputs-v2` distribution.
It does not locate or import directly from a V2 checkout.

Until the distribution is published to a package feed, a two-repository
checkout is installed into one Python environment in this order:

```powershell
python -m pip install C:\path\to\inputs-v2-lab
python -m pip install -r requirements.txt
```

For editable development, use:

```powershell
python -m pip install -e C:\path\to\inputs-v2-lab
```

The installed distribution must report version `0.1.1`. Verify a completely
fresh installation and the Runtime adapter boundary with:

```powershell
python -m tools.verification.run_inputs_v2_clean_install_contract `
  --v2-checkout C:\path\to\inputs-v2-lab
```

Hosted Runtime deployments install the tested V2 wheel vendored at
`vendor/beamapp_inputs_v2-0.1.1-py3-none-any.whl` through `requirements.txt`.
Its SHA-256 digest is
`8f6cffb30a9d53951623a7abf705f87ec86f22886d5c04dcd30912d2900cb4e1`.

Publishing `beamapp-inputs-v2==0.1.1` to the deployment package feed is the
remaining distribution step. Once published, add the pinned dependency to the
deployment requirements without restoring any checkout-path discovery.
