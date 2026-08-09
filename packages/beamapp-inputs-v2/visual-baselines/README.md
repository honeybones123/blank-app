# Inputs V2 visual baselines

The manifest defines the required reference states and viewports. Reference PNGs
must be captured from the current Inputs page and stored here only after the
current page is inspected. V2 screenshots are compared against those references
with an explicit image-difference threshold.

The current status is intentionally `reference_capture_pending`; this prevents
the architecture suite from claiming pixel parity before real reference images
exist.

