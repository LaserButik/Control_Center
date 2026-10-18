# -*- coding: utf-8 -*-
"""Prepare per-platform text for manual publishing. Writes text files only;
never posts anywhere."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import components as C
from atlas_services import content_distribution as CD
from connectors import paths

page_config(st, "Content Distribution")
render_sidebar(st)

page_header(st, "Content distribution", "", "share")
st.caption("Turns a list of {title, body, url} items into per-platform text "
           "files to copy and paste. It NEVER posts anything or calls any "
           "social API.")

C.render(st, C.section_header("1) Content items"))
mode = st.radio("Source", ["Write one item", "Upload JSON"],
                horizontal=True)
items = []
if mode == "Write one item":
    title = st.text_input("Title")
    body = st.text_area("Body")
    url = st.text_input("URL", placeholder="https://…")
    if title or body:
        items = [{"title": title, "body": body, "url": url}]
else:
    up = st.file_uploader("JSON: a list of items, or {\"items\": [...]}",
                          type=["json"])
    if up:
        try:
            data = json.loads(up.getvalue().decode("utf-8"))
            items = data.get("items", data) if isinstance(data, dict) \
                else data
        except (ValueError, UnicodeDecodeError) as e:
            st.error("Could not read JSON: %s" % e)

platforms = st.multiselect("Platforms", list(CD.PLATFORMS),
                           default=["twitter", "linkedin"])

C.render(st, C.section_header("2) Prepare files"))
if st.button("Prepare", type="primary", disabled=not (items and platforms)):
    out_dir = paths.ensure_cc_data() / "distribution"
    # write the items to a temp input, then run the service
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      dir=str(paths.ensure_cc_data()),
                                      encoding="utf-8")
    json.dump({"items": items}, tmp, ensure_ascii=False)
    tmp.close()
    with st.spinner("Writing text files…"):
        r = CD.prepare_posts(tmp.name, platforms, str(out_dir))
    if r.get("ok"):
        st.success("Wrote %d files for %d item(s)." % (
            len(r["files_written"]), r["items"]))
        for f in r["files_written"]:
            with st.expander(Path(f).name):
                st.code(Path(f).read_text(encoding="utf-8"))
    else:
        st.error("Stopped: %s" % r.get("reason"))
