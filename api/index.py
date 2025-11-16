"""Vercel entrypoint module for the Lift Bot FastAPI service."""
from lift_bot_api import app as fastapi_app

# The variable name `app` is what Vercel's FastAPI runtime expects.
app = fastapi_app
