#!/usr/bin/env python3
"""Shared brand-folder reader for Content Foundry.

Parses an agent's Tier-2 files into structured values. Used by composite.py and
brand_lint.py so that BOTH read brand truth from exactly one place — if they
diverged, the lint would be validating something other than what was composited.

Tenancy: every path resolved here is inside agents/{slug}/. Nothing outside that
folder can influence a run.
"""

import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"(<!--.*?-->|\[[A-Za-z][^\]]*\]|_{3,})", re.DOTALL)
HEX_RE = re.compile(r"#([0-9a-fA-F]{6})\b")


class BrandError(Exception):
    """A brand fact is missing or unusable. Always actionable — name the file."""


def _strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def is_blank_template(text):
    """True if the file still contains unfilled template placeholders."""
    body = _strip_comments(text)
    if re.search(r"\[[A-Za-z][^\]]*\]", body):
        return True
    if re.search(r"_{3,}", body):
        return True
    return not body.strip()


def _field(text, key):
    """Pull `- key: value` or `key: value` from a markdown bullet list."""
    body = _strip_comments(text)
    m = re.search(rf"^\s*[-*]?\s*{re.escape(key)}\s*:\s*(.+)$", body,
                  re.MULTILINE | re.IGNORECASE)
    if not m:
        return None
    val = m.group(1).strip().strip('"').strip()
    return val or None


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(rgb):
    def chan(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(c) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1, rgb2):
    """WCAG contrast ratio. 4.5:1 is the AA bar for normal text."""
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    lo, hi = sorted((l1, l2))
    return (hi + 0.05) / (lo + 0.05)


class AgentBrand:
    """Brand truth for one agent. The tenancy unit."""

    def __init__(self, agent_dir):
        self.dir = Path(agent_dir).expanduser().resolve()
        if not self.dir.is_dir():
            raise BrandError(f"agent folder not found: {self.dir}")
        self.slug = self.dir.name
        self.visual = self._load("brand-context-visual.md")
        self.compliance = self._load("brand-context-compliance.md")

    def _load(self, name):
        p = self.dir / name
        if not p.exists():
            raise BrandError(
                f"{self.slug}: missing {name}. Run `setup --agent {self.slug}` "
                f"— see references/context-kit-import.md")
        text = p.read_text(encoding="utf-8")
        if is_blank_template(text):
            raise BrandError(
                f"{self.slug}: {name} is still a blank template. Run "
                f"`setup --agent {self.slug}` and interview — do not fabricate.")
        return text

    # --- visual -----------------------------------------------------------
    @property
    def colors(self):
        out = {}
        for key in ("primary", "secondary", "accent",
                    "text-on-light", "text-on-dark"):
            val = _field(self.visual, key)
            if val:
                m = HEX_RE.search(val)
                if m:
                    out[key] = "#" + m.group(1).lower()
        if "primary" not in out:
            raise BrandError(
                f"{self.slug}: no primary color hex in brand-context-visual.md. "
                f"Extract it from the logo and confirm before writing.")
        return out

    def logo_path(self, variant="light"):
        """variant: 'light' = logo for light backgrounds."""
        key = {"light": "light background", "dark": "dark background",
               "mark": "mark only"}[variant]
        val = _field(self.visual, key)
        if not val:
            raise BrandError(
                f"{self.slug}: no '{key}' logo declared in brand-context-visual.md")
        p = (self.dir / val).resolve()
        if not p.exists():
            raise BrandError(
                f"{self.slug}: logo path does not resolve: {val} (looked in {p}). "
                f"Setup must verify logo paths before production.")
        if self.dir not in p.parents and p != self.dir:
            raise BrandError(
                f"{self.slug}: logo path escapes the agent folder: {val}. "
                f"Tenancy requires assets live inside agents/{self.slug}/.")
        return p

    @property
    def headshot_path(self):
        """Agent headshot when declared and present; None otherwise. Used on
        video endcards and outreach pages — the agent IS the brand."""
        val = _field(self.visual, "headshot")
        if not val:
            return None
        p = (self.dir / val).resolve()
        if not p.exists() or (self.dir not in p.parents):
            return None
        return p

    @property
    def logo_min_width(self):
        val = _field(self.visual, "minimum width")
        m = re.search(r"(\d+)", val or "")
        return int(m.group(1)) if m else 120

    @property
    def logo_clear_space(self):
        val = _field(self.visual, "clear space")
        m = re.search(r"(\d+)", val or "")
        return int(m.group(1)) if m else 24

    @property
    def logo_placement(self):
        return (_field(self.visual, "default placement") or "bottom-left").split("|")[0].strip()

    @property
    def headline_font(self):
        """Path or name of the brand headline font; None if undeclared."""
        return _field(self.visual, "headline font")

    @property
    def max_headline_chars(self):
        val = _field(self.visual, "max headline length")
        m = re.search(r"(\d+)", val or "")
        return int(m.group(1)) if m else 60

    # --- compliance -------------------------------------------------------
    @property
    def license_number(self):
        return _field(self.compliance, "agent license number")

    @property
    def disclosure(self):
        return _field(self.compliance, "disclosure text")

    @property
    def fair_housing(self):
        return _field(self.compliance, "required language")

    @property
    def demo(self):
        """True when this folder is a demo/fixture persona. Demo agents may not
        produce listing content without an explicit --allow-demo override."""
        return (_field(self.compliance, "demo") or "false").lower() == "true"

    @property
    def design(self):
        """Design tokens from brand-context-design.md (research-drafted).

        Defaults preserve the original editorial look when the file is absent.
        layout_family: editorial-panel | full-bleed-bold | split-frame
        display_type:  serif | sans
        motion_energy: calm | confident | energetic
        accent_treatment: rule | block
        """
        path = self.dir / "brand-context-design.md"
        out = {"layout_family": "editorial-panel", "display_type": "serif",
               "motion_energy": "calm", "accent_treatment": "rule"}
        if path.exists():
            text = path.read_text(encoding="utf-8")
            for key in out:
                val = _field(text, key.replace("_", " "))
                if val:
                    out[key] = val.split("|")[0].strip()
        return out

    @property
    def auto_publish(self):
        return (_field(self.compliance, "auto_publish") or "false").lower() == "true"

    @property
    def banned_words(self):
        """Compliance bans only. Stylistic bans live in brand-voice.md (Tier 1)."""
        body = _strip_comments(self.compliance)
        m = re.search(r"##\s*Banned claims and words(.*?)(?=\n##|\Z)", body,
                      re.DOTALL | re.IGNORECASE)
        if not m:
            return []
        return [ln.strip("-* ").strip() for ln in m.group(1).splitlines()
                if ln.strip().startswith(("-", "*")) and len(ln.strip()) > 2]

    def required_strings(self):
        """Every string that MUST appear verbatim on a production asset.

        Missing entries are returned as PENDING so the lint can block rather
        than the composite silently omitting a legal requirement.
        """
        out = {}
        for key, val in (("license", self.license_number),
                         ("disclosure", self.disclosure),
                         ("fair_housing", self.fair_housing)):
            if val and not val.upper().startswith("[PENDING"):
                out[key] = val
            else:
                out[key] = None
        return out
