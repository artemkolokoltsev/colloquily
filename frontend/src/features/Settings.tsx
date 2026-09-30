import { useEffect, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice } from "../components/Common";
interface SettingsData {
  values: Record<string, string | number | boolean>;
  data_directory: string;
  sections: {
    section: string;
    fields: { key: string; label: string; type: string; options?: string[] }[];
  }[];
}
export function Settings({ exam }: { exam: number }) {
  const [data, setData] = useState<SettingsData>();
  const [models, setModels] = useState<{
    task_models: Record<string, string>;
    embedding_config: { model: string };
  }>();
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  useEffect(() => {
    Promise.all([
      api<SettingsData>("/settings").then(setData),
      api<NonNullable<typeof models>>(`/exams/${exam}/models`).then(setModels),
    ]).catch((e) => setError(String(e)));
  }, [exam]);
  async function save() {
    setError("");
    try {
      await api("/settings", "PATCH", { values: data?.values });
      if (models)
        await api(`/exams/${exam}/models`, "PATCH", {
          task_models: models.task_models,
          embedding_model: models.embedding_config.model,
        });
      setMessage(
        "Settings saved. Rebuild the exam index after changing its embedding model.",
      );
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <section>
      <h2>Advanced settings</h2>
      <p>Experiment with RAG parsing, chunking, retrieval, and local models.</p>
      <ErrorNotice error={error} />
      <p role="status">{message}</p>
      <p>Data directory: {data?.data_directory}</p>
      {models && (
        <fieldset>
          <legend>Models for this exam (Ollama)</legend>
          {Object.entries(models.task_models).map(([task, value]) => (
            <label key={task}>
              {task.replaceAll("_", " ")}
              <input
                value={value}
                onChange={(e) =>
                  setModels({
                    ...models,
                    task_models: {
                      ...models.task_models,
                      [task]: e.target.value,
                    },
                  })
                }
              />
            </label>
          ))}
          <label>
            Embedding model
            <input
              value={models.embedding_config.model}
              onChange={(e) =>
                setModels({
                  ...models,
                  embedding_config: { model: e.target.value },
                })
              }
            />
          </label>
        </fieldset>
      )}
      {data?.sections.map((s) => (
        <details key={s.section}>
          <summary>{s.section}</summary>
          {s.fields
            .filter((f) => f.key !== "ST_ALLOW_DOWNLOAD")
            .map((f) => (
              <label key={f.key}>
                {f.label}
                {f.type === "bool" ? (
                  <input
                    type="checkbox"
                    checked={!!data.values[f.key]}
                    onChange={(e) =>
                      setData({
                        ...data,
                        values: { ...data.values, [f.key]: e.target.checked },
                      })
                    }
                  />
                ) : f.type === "select" ? (
                  <select
                    value={String(data.values[f.key])}
                    onChange={(e) =>
                      setData({
                        ...data,
                        values: { ...data.values, [f.key]: e.target.value },
                      })
                    }
                  >
                    {f.options?.map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={String(data.values[f.key] ?? "")}
                    onChange={(e) =>
                      setData({
                        ...data,
                        values: { ...data.values, [f.key]: e.target.value },
                      })
                    }
                  />
                )}
              </label>
            ))}
        </details>
      ))}
      <button onClick={save}>Save settings</button>
    </section>
  );
}
