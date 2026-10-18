# -*- coding: utf-8 -*-
"""Inline SVG icons, Lucide-style (24x24 grid, stroke=currentColor,
stroke-width 1.75, round caps/joins). No external dependency.

ICONS[name] is a ready SVG string at 20px; icon(name, size) re-renders at
another size. Colour comes from the surrounding CSS `color`.
"""

from __future__ import annotations

_BODIES = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/>'
            '<path d="M10 21v-6h4v6"/>',
    "spider": '<circle cx="12" cy="13" r="3"/><path d="M12 10V7"/>'
              '<path d="M9 12 4 9"/><path d="m15 12 5-3"/>'
              '<path d="M9 14l-5 2"/><path d="m15 14 5 2"/>'
              '<path d="M10 16l-3 5"/><path d="m14 16 3 5"/>'
              '<path d="M10.5 7.5 8 3"/><path d="M13.5 7.5 16 3"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
              '<path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/>'
            '<path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    "send": '<path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7z"/>',
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
             '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6'
             'l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "bot": '<rect x="4" y="8" width="16" height="12" rx="3"/>'
           '<path d="M12 8V4"/><circle cx="12" cy="3" r="1"/>'
           '<path d="M9 13v2"/><path d="M15 13v2"/><path d="M2 14h2"/>'
           '<path d="M20 14h2"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/>'
             '<path d="M12 3a14 14 0 0 1 0 18a14 14 0 0 1 0-18z"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 '
                '1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06'
                'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 '
                '0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82'
                '.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 '
                '4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 '
                '1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 '
                '1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 '
                '1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 '
                '1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65'
                ' 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 '
                '4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
             '<circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/>'
             '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07'
            'l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 '
            '0 0 7.07 7.07l1.71-1.71"/>',
    "sword": '<path d="M14.5 17.5 3 6V3h3l11.5 11.5"/><path d="m13 19 6-6"/>'
             '<path d="m16 16 4 4"/><path d="m19 21 2-2"/>',
    "flask": '<path d="M9 3h6"/><path d="M10 3v6L4.5 19a1.5 1.5 0 0 0 '
             '1.3 2.2h12.4a1.5 1.5 0 0 0 1.3-2.2L14 9V3"/>'
             '<path d="M7 15h10"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 '
            '2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8"/>'
            '<path d="M8 17h5"/>',
    "share": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/>'
             '<circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4"/>'
             '<path d="m15.4 6.5-6.8 4"/>',
    "play": '<path d="m6 3 14 9-14 9V3z"/>',
    "stop": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "refresh": '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/>'
               '<path d="M3 21v-5h5"/><path d="M3 12A9 9 0 0 1 18.5 5.8L21 8"/>'
               '<path d="M21 3v5h-5"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                '<path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "external": '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 '
                '1 2-2h6"/><path d="M15 3h6v6"/><path d="M10 14 21 3"/>',
    "alert": '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3'
             'L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/>'
             '<path d="M12 17h.01"/>',
    "trend_up": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "trend_down": '<path d="m22 17-8.5-8.5-5 5L2 7"/><path d="M16 17h6v-6"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
              '<path d="m9 12 2 2 4-4"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/>'
                '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'
                '<path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/>'
                '<path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/>'
             '<path d="M8 17v-3"/>',
    "sparkle": '<path d="M12 3l1.9 5.6L19.5 10.5l-5.6 1.9L12 18l-1.9-5.6'
               'L4.5 10.5l5.6-1.9z"/><path d="M19 3v4"/><path d="M21 5h-4"/>',
    "arrow_right": '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
    "arrow_up_right": '<path d="M7 17 17 7"/><path d="M7 7h10v10"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "filter": '<path d="M22 3H2l8 9.46V19l4 2v-8.54z"/>',
    "star": '<path d="m12 2 3.09 6.26L22 9.27l-5 4.87L18.18 21 12 17.77 '
            '5.82 21 7 14.14l-5-4.87 6.91-1.01z"/>',
    "bookmark": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "copy": '<rect x="9" y="9" width="13" height="13" rx="2"/>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
}


def icon(name: str, size: int = 20, stroke_width: float = 1.75) -> str:
    """An inline SVG for `name` at `size` px. Unknown names fall back to a
    neutral dot so a typo never breaks a page."""
    body = _BODIES.get(name, '<circle cx="12" cy="12" r="2"/>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="%s" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true" focusable="false">%s</svg>'
            % (size, size, stroke_width, body))


ICONS = {name: icon(name) for name in _BODIES}
NAMES = tuple(_BODIES)
