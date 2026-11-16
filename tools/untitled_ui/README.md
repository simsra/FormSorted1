# Untitled UI look (Simon, 16 Nov 2026)
- `static/ui.css` is built from `ui.css.tpl`: `python3 tools/untitled_ui/build_css.py static/ui.css`
- formsorted.com rebuild (test copy): `APP_DIR=$PWD python3 tools/untitled_ui/site_build.py <built site dir> <out dir>` (uses site.css, static/ui.css, chat.js, Inter)
- Icons: Untitled UI Icons free line set (@untitledui/icons 0.0.23). Licence: use in personal and commercial projects is allowed;
  not allowed to sell/redistribute the icons or build an icon library from them. We only inline ~40 paths in our own pages (`uikit.py`, `icons.json`).
- Font: Inter (SIL Open Font License 1.1), self-hosted `static/inter-var.woff2`, licence in `static/inter-OFL.txt`.
- Switch: CHAT_UI=0 brings back the old step-by-step look (app.css) with no code change.
