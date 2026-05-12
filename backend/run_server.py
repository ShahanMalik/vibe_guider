#!/usr/bin/env python
"""
Backend server startup wrapper that ensures proper module loading for uvicorn.
"""
import sys
import os

# Ensure backend directory is in the path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Now import and run uvicorn
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
