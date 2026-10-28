# Ringtone Orchestrator

The ringtone orchestrator provides the API and generation pipeline for creating personalized AI-generated ringtones.

It coordinates the LLM and TTS models running in the GPU orchestrator and manages job information through PostgreSQL.

## Architecture

```text
Web Interface / PubSub Worker
             |
             v
       FastAPI API
             |
             +-- PostgreSQL
             |      Job metadata and status
             |
             +-- GPU Orchestrator
             |      LLM script generation
             |      TTS audio generation
             |
             +-- RustFS
                    Voice references
                    Generated ringtones
```

## API

The API is also accessible through the simple web interface.

| Endpoint | Description |
|---|---|
| `POST /generate` | Submit a ringtone generation request |
| `GET /status/{job_id}` | Retrieve generation status |
| `GET /download/{job_id}` | Download a completed ringtone |
| `GET /voices` | List available voices |
| `GET /voice-preview` | Preview reference audio |
| `GET /health` | Health check |

Job IDs are UUID4 values. Clients can supply their own IDs or let the orchestrator generate them.

Job metadata is persisted in PostgreSQL, allowing status information to survive application restarts.
