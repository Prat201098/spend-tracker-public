"""
Centralized configuration loader.
- Loads config from config.yaml if present.
- Overlays secrets from Streamlit Cloud (st.secrets) when available, e.g. pdf_passwords, smtp, pushover, twilio.
- Returns a single merged config dict used across the app.
"""
from __future__ import annotations

import os
from typing import Any, Dict

import yaml

# Streamlit is optional at import time (for local CLI runs)
try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None  # type: ignore


def _read_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _overlay_dict(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow overlay: overlay values overwrite base when keys collide."""
    if not overlay:
        return base
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _overlay_dict(dict(base[k]), v)
        else:
            base[k] = v
    return base


def _apply_pdf_password_secrets(cfg: Dict[str, Any]) -> None:
    """If st.secrets['pdf_passwords'] is present, map into email.bank_emails entries.
    Matching is by exact card_name key in secrets.
    """
    if st is None or not hasattr(st, "secrets"):
        return
    try:
        secrets_pw = dict(st.secrets.get("pdf_passwords", {}))
    except Exception:
        secrets_pw = {}
    if not secrets_pw:
        return

    email_cfg = cfg.get("email", {})
    bank_emails = email_cfg.get("bank_emails", []) or []
    changed = False
    for entry in bank_emails:
        card_name = entry.get("card_name")
        if card_name and card_name in secrets_pw:
            entry["pdf_password"] = secrets_pw[card_name]
            changed = True
    if changed:
        cfg.setdefault("email", {})["bank_emails"] = bank_emails


def _apply_other_secrets(cfg: Dict[str, Any]) -> None:
    """Optionally overlay smtp/pushover/twilio sections from st.secrets if provided."""
    if st is None or not hasattr(st, "secrets"):
        return
    for section in ("smtp", "pushover", "twilio"):
        try:
            sec = dict(st.secrets.get(section, {}))
        except Exception:
            sec = {}
        if sec:
            cfg[section] = _overlay_dict(cfg.get(section, {}) or {}, sec)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load config.yaml and overlay Streamlit Secrets if available.

    Returns a dict with at least:
      - database.path (default: data/spend_tracker.db if missing)
    """
    cfg = _read_yaml(config_path)

    # Minimal defaults
    cfg.setdefault("database", {}).setdefault("path", "data/spend_tracker.db")
    cfg.setdefault("email", {}).setdefault("bank_emails", [])
    cfg["email"].setdefault("max_emails_per_card", 12)

    # Apply secrets overlays
    _apply_pdf_password_secrets(cfg)
    _apply_other_secrets(cfg)

    return cfg
