#!/usr/bin/env python3
import sys
try:
    from app import app
    print("✓ App imported successfully")
    print(f"✓ Flask version: {app.import_name}")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    sys.exit(1)
