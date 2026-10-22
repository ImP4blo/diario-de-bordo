# Diário de Bordo

> 🚧 Work in progress — Stage 1 (local version) under construction.

A voice-powered work log. It listens to **your microphone** during the workday, transcribes what you say with timestamps, reminds you when you go too long without logging what you're doing, and uses AI to turn the day's transcript into a structured diary exported as a **Word (.docx)** document.

## Features (Stage 1 – local)

- Continuous speech recognition in Chrome (Web Speech API, `pt-BR`), with auto-restart
- Every recognized sentence saved instantly with a timestamp
- Keyword **"Diário"** marks explicit notes and sets the current activity
- Inactivity reminder ("Are you still working on X?") via system notification
- Configurable fixed daily routine (dailies, breaks…)
- AI-generated diary (pluggable provider: Groq or Anthropic Claude) with a review screen
- Word export and raw transcript export

## Tech stack

Python 3.12+ · FastAPI · SQLModel (SQLite → Postgres) · python-docx · vanilla HTML/CSS/JS · uv · pytest · ruff

## Running locally

Requires [uv](https://docs.astral.sh/uv/) and Google Chrome.

```bash
git clone https://github.com/ImP4blo/diario-de-bordo.git
cd diario-de-bordo
cp .env.example .env          # then edit the values
cp config/routine.example.toml config/routine.toml
uv sync
uv run uvicorn app.main:app --reload
```

Open <http://localhost:8000> in Chrome.

## Privacy notice

Chrome's Web Speech API sends audio to Google servers for recognition, and the AI step sends the transcript to the configured LLM provider. Check your company's policies before using it at work. A fully local option (Whisper) is on the roadmap.

## Roadmap

- **Stage 2:** cloud backend (Render) + Supabase (Postgres + Auth) + installable PWA with push-to-talk on mobile
- **Stage 3 (optional):** Play Store / App Store
- Local speech recognition with Whisper

---

## 🇧🇷 Em português

App que transcreve sua voz durante o expediente e usa IA para gerar o **diário de bordo** semanal em Word. Projeto pessoal de estudo de Python e AI Engineering. Instruções detalhadas em português chegam na versão final deste README.

## License

[MIT](LICENSE)
