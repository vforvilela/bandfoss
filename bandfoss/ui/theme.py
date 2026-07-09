"""Visual "Tube Amp" theme — warm charcoal + amber glow, audio-gear look."""

from __future__ import annotations

# Palette ----------------------------------------------------------------------
BG = "#1A1614"          # warm charcoal (background)
PANEL = "#241E1A"       # panels / fields
PANEL_HI = "#2E2620"    # secondary button / subtle hover
BORDER = "#3A302A"      # warm borders
TEXT = "#EDE6DA"        # cream
MUTED = "#9A8C7E"       # secondary text (warm gray)
AMBER = "#FF7A18"       # primary accent (tube glow)
AMBER_HI = "#FF8C34"    # hover
AMBER_LO = "#4A3B2E"    # dimmed amber (disabled)
REC = "#E5484D"         # "REC" red (live capture)
REC_HI = "#F05860"
GROOVE = "#141010"      # fader track (darker)

STYLESHEET = f"""
QWidget {{
    background: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QLabel {{ background: transparent; }}
QLabel#wordmark {{ background: transparent; }}
QLabel#subtitle {{ color: {MUTED}; background: transparent; }}
QLabel#sectionLabel {{ color: {MUTED}; font-weight: 700; background: transparent; }}

QLineEdit, QComboBox {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 6px 8px;
    selection-background-color: {AMBER};
    selection-color: {BG};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {AMBER}; }}
QComboBox QAbstractItemView {{
    background: {PANEL};
    border: 1px solid {BORDER};
    selection-background-color: {AMBER};
    selection-color: {BG};
    outline: none;
}}

QPushButton {{
    background: {PANEL_HI};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 3px;
    padding: 6px 12px;
    font-weight: 600;
}}
QPushButton:hover {{ border-color: {AMBER}; }}
QPushButton:pressed {{ background: {PANEL}; }}
QPushButton:disabled {{ color: #6B5F54; border-color: #2A231E; }}

/* primary action (Separate) — full amber */
QPushButton#primaryBtn {{
    background: {AMBER}; color: {BG}; border: none; font-weight: 800;
    padding: 7px 18px;
}}
QPushButton#primaryBtn:hover {{ background: {AMBER_HI}; }}
QPushButton#primaryBtn:disabled {{ background: {AMBER_LO}; color: #8A7A6C; }}

/* record action (Capture live) — REC red */
QPushButton#recordBtn {{
    background: {REC}; color: #1A1614; border: none; font-weight: 800;
    padding: 7px 18px;
}}
QPushButton#recordBtn:hover {{ background: {REC_HI}; }}
QPushButton#recordBtn:checked {{ background: #8F3538; color: {TEXT}; }}
QPushButton#recordBtn:disabled {{ background: #4A2A2B; color: #8A7A6C; }}

/* "Advanced" expander — discreet */
QPushButton#advBtn {{
    background: transparent; border: none; color: {MUTED};
    text-align: left; font-weight: 700; padding: 4px 2px;
}}
QPushButton#advBtn:hover {{ color: {AMBER}; border: none; }}

/* per-strip M/S buttons */
QPushButton#muteBtn:checked {{
    background: {REC}; color: {BG}; border-color: {REC}; font-weight: 800;
}}
QPushButton#soloBtn:checked {{
    background: #F2C14E; color: {BG}; border-color: #F2C14E; font-weight: 800;
}}

QProgressBar {{
    background: {PANEL}; border: 1px solid {BORDER}; border-radius: 3px;
    text-align: center; color: {TEXT}; height: 20px;
}}
QProgressBar::chunk {{ background: {AMBER}; border-radius: 2px; }}

QFrame#stemPanel {{
    background: #201A16; border: 1px solid {BORDER}; border-radius: 8px;
}}
QWidget#advPanel {{ background: #1E1815; border: 1px solid {BORDER}; border-radius: 6px; }}

QToolTip {{
    background: {PANEL}; color: {TEXT}; border: 1px solid {AMBER}; padding: 4px;
}}

/* vertical faders (base; the channel color is applied per-strip) */
QSlider::groove:vertical {{
    width: 6px; background: {GROOVE}; border-radius: 3px;
}}
QSlider::handle:vertical {{
    height: 20px; margin: 0 -9px; background: {TEXT}; border-radius: 3px;
}}
QSlider::groove:horizontal {{
    height: 6px; background: {GROOVE}; border-radius: 3px;
}}
QSlider::sub-page:horizontal {{ background: {AMBER}; border-radius: 3px; }}
QSlider::handle:horizontal {{
    width: 14px; margin: -6px 0; background: {TEXT}; border-radius: 3px;
}}
"""


def fader_style(color: str) -> str:
    """Per-strip stylesheet: fills the section BELOW the handle (level, bottom-up)."""
    return f"""
    QSlider::groove:vertical {{ width: 6px; background: {GROOVE}; border-radius: 3px; }}
    QSlider::add-page:vertical {{ background: {color}; border-radius: 3px; }}
    QSlider::sub-page:vertical {{ background: {GROOVE}; border-radius: 3px; }}
    QSlider::handle:vertical {{
        height: 20px; margin: 0 -9px; background: {color};
        border: 1px solid {BG}; border-radius: 3px;
    }}
    """
