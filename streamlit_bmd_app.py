"""
Render entrypoint wrapper.

Render is configured to run:
    streamlit run streamlit_bmd_app.py --server.port $PORT --server.address 0.0.0.0

This wrapper simply calls the real Streamlit app in app.py.
"""

from app import main

# Streamlit executes this file as the script entrypoint.
# Call your app's main() directly.
main()
