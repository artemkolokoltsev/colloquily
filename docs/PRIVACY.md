# Privacy

Colloquily stores exams, documents, generated questions, answers, evaluations, indexes, settings, and logs locally. It has no accounts, telemetry, advertising, or cloud-inference fallback. The API binds to loopback, rejects foreign browser origins, and packaged launches use a random per-process token.

Network access occurs only for visible actions: checking or installing GitHub-hosted updates, opening the Ollama download page, and asking local Ollama to download a chosen model. Uploaded documents and answers are not sent to Colloquily servers.

Workspace backups contain personal study data. A backup excludes regenerable caches and Ollama weights, but includes documents, SQLite records, settings, and relevant indexes. Restore validates paths, checksums, format, database integrity, and schema compatibility, and creates a safety backup before replacement.
