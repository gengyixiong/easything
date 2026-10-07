# EasyThing contributor instructions

Keep V1 a single PySide6 desktop process. Use the official EmbeddingGemma 2
Text + Vision 440M LiteRT-LM model and embedded LanceDB. No cloud inference,
telemetry, servers, plugins, or vendor-specific GPU code.

Index only explicitly selected folders. Source documents are always read-only.
Preserve LICENSE and NOTICE. Use .venv/Scripts/python.exe for development.
Run tests/smoke.py before a stable commit. Build with build.ps1 and Inno Setup.
Do not add speculative abstractions or dependencies. User instructions take precedence.
