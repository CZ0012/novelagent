# StoryGraph Desktop Shell

This is the Tauri shell for the StoryGraph Workbench.

The desktop app hosts the same React UI from `apps/web` and talks to the local FastAPI backend. It must not write canon directly; canon writes still go through backend seed or review APIs.

Current MVP files are configuration-only. A production desktop package should add the Rust Tauri crate files and startup orchestration for the local API process.
