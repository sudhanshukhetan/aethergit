"""Vercel Serverless Function entrypoint."""

import os
import sys

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, application, handler

__all__ = ["app", "application", "handler"]
