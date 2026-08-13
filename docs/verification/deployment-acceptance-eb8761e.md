# Deployment acceptance audit — `eb8761e`

Date: 2026-08-13  
Local control: `http://localhost:8530`  
Render deployment: `https://structuralbase-rc-frwfwf.onrender.com`  
Commit: `eb8761ee2fb01c925e714a5acc2001fd211957d7`

## Result

Conditional failure. The deployed application matches the local application for ordinary ULS workflows, but the serviceability Apply path is not yet demonstrably effective and Render exposes a longer stale visual window while SLS results converge.

## Verified behaviours

- Fresh local and Render sessions loaded without a traceback or import error.
- Matching bending-failure inputs produced the same family, candidate and final utilisation.
- Bending Apply changed both applications directly to `PASS Target band reached` at 0.99 utilisation.
- Matching shear-failure inputs produced the same shear repair.
- The bounded Fast-mode second repair produced the same combined-strength family in both applications.
- A second Apply produced the same final `PASS Target band reached` at 0.97 utilisation.
- No `stale_apply_candidate_source_revision` error occurred in these ULS Apply flows.
- Inputs retained committed values after navigation through Bending, Shear, Creep, Shrinkage, Crack Control and Deflection.
- No tested engineering page displayed `Awaiting current calculation` after navigation.
- The Beam Inputs action-source toggle selected Load Analysis actions and restored Beam Inputs actions consistently in local and Render sessions.
- Manual ULS actions were retained after toggling back.
- A display-only Deflection control did not show a calculation shell or trigger an observable whole-page engineering rerun.

## Timing observations

- Initial fresh load: local approximately 2.38 s; Render approximately 2.00 s in this run.
- Bending candidate: local approximately 0.44 s; Render approximately 1.43 s.
- Shear candidate: local approximately 0.39 s; Render approximately 0.95 s.
- Render Apply briefly retained the old card before switching directly to the final card. No intermediate candidate or stale error appeared.
- Crack Control navigation was the slowest Render page in this run at approximately 6.95 s.

## Remaining defects

### 1. Serviceability Apply does not visibly commit the verified proposal

With an 8,000 mm span and a high SLS moment, both applications produced the same serviceability failure and the same `ACTION Verified serviceability revision` card. The Apply button was enabled. After Apply:

- the same action card remained;
- the same geometry and reinforcement remained visible;
- the same Apply button remained available;
- no stale-revision message or exception was displayed.

This is an Apply no-op until the committed proposal can be proven to change the authoritative input snapshot and calculation result.

### 2. Render has a longer SLS convergence window

For the matched SLS edit, local results updated promptly. Render temporarily showed the previous serviceability state before converging to the same crack-control, deflection and Design Brain result several seconds later. The final engineering result matched, but the temporary mixed state is user-visible.

## Release judgement

The deployed ULS Design Brain and Apply path are behaving consistently with the local control for the tested bending, shear and combined cases. Do not treat the deployment as fully accepted until the serviceability Apply no-op is fixed and rerun through this same matched-session audit.
