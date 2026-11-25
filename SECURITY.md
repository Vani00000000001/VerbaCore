# Security Policy

## Supported Versions

Security fixes and updates are provided for the current release series:

| Version | Supported |
| ------- | --------- |
| 0.2.x   | Yes       |
| < 0.2.0 | No        |

## Reporting a Vulnerability

Please **do not** report security vulnerabilities through public GitHub issues, pull requests, or discussions.

Instead, report vulnerabilities privately via **GitHub Private Vulnerability Reporting**:

1. Open the repository on GitHub and go to the **Security** tab.
2. Select **Advisories** -> **Report a vulnerability**.
3. Include a clear description of the issue, steps to reproduce, affected files or API endpoints, and potential impact.

We will acknowledge receipt and work with you to validate and address confirmed issues before public disclosure.

## Privacy & Security Architecture

VerbaCore is built with a local-first security model:

- **Local-First Processing**: Speech recognition (`faster-whisper`) and local Brain LLM reasoning (`Ollama` / `llama-server`) run 100% locally by default. No audio or transcript data leaves your computer during local transcription.
- **Opt-In Cloud Fallback**: Cloud transcription (`Google Gemini` / `Groq`) is disabled by default (`auto_fallback: false`) and only transmits audio when explicitly selected or enabled with user-supplied API keys.
- **Localhost Binding & CORS**: The server binds to `127.0.0.1:7860` by default with localhost-only CORS (`allow_credentials=False`).
- **API Key Hygiene**: Cloud API keys are stored locally in the gitignored `cloud_config.json` file or provided via environment variables. `GET /api/cloud-config` returns only boolean configuration status (`has_gemini`, `has_groq`) and never echoes raw or masked keys.
- **Upload & Export Isolation**: Recordings, chunked upload sessions, and report exports use UUID-isolated directories, size bounds, XML escaping for generated documents, and path-traversal checks.
