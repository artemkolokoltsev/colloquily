# Privacy

Colloquily stores exams, documents, generated questions, answers, evaluations, indexes, settings, and logs locally. It has no accounts, telemetry, advertising, or cloud-inference fallback. The API binds to loopback, rejects foreign browser origins, and packaged launches use a random per-process token.

Automatic software updates are enabled by default and can be disabled in Software updates. Colloquily checks GitHub on startup, every six hours, and when connectivity returns; failed checks retry after 15 minutes. Updates are downloaded and signatures verified before installation. This sends ordinary connection metadata to GitHub, but no study content. Other network access includes opening reference links or the Ollama download page and asking local Ollama to download a chosen model. Uploaded documents and answers are not sent to Colloquily servers.

Workspace backups contain personal study data. A backup excludes regenerable caches and Ollama weights, but includes documents, SQLite records, settings, and relevant indexes. Restore validates paths, checksums, format, database integrity, and schema compatibility, and creates a safety backup before replacement.
