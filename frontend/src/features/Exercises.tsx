import { lazy, Suspense, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, apiBytes, downloadBytes } from "../api/client";
import { ErrorNotice } from "../components/Common";
import type { ExerciseSheet, SubmissionProfile } from "../types";
const PdfPreview = lazy(() => import("../components/SourcePdfPreview"));

function readDraft<T>(key: string): T | undefined {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") || undefined;
  } catch {
    return undefined;
  }
}

export function Exercises({ exam }: { exam: number }) {
  const { t } = useTranslation();
  const [data, setData] = useState<{
    sheets: ExerciseSheet[];
    pdf_export_available: boolean;
  }>();
  const [profile, setProfile] = useState<SubmissionProfile>();
  const [selected, setSelected] = useState<number>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [profileSaved, setProfileSaved] = useState(false);
  const profileKey = `colloquily.submission.${exam}`;
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      api<NonNullable<typeof data>>(
        `/exams/${exam}/exercises`,
        "GET",
        undefined,
        controller.signal,
      ),
      api<SubmissionProfile>(
        `/exams/${exam}/submission-profile`,
        "GET",
        undefined,
        controller.signal,
      ),
    ])
      .then(([list, details]) => {
        setData(list);
        setProfile(readDraft<SubmissionProfile>(profileKey) || details);
        setSelected(list.sheets[0]?.id);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      });
    return () => controller.abort();
  }, [exam, profileKey]);
  function changeProfile(next: SubmissionProfile) {
    setProfile(next);
    setProfileSaved(false);
    try {
      localStorage.setItem(profileKey, JSON.stringify(next));
    } catch (e) {
      setError(String(e));
    }
  }
  async function saveProfile() {
    if (!profile) return;
    await api(`/exams/${exam}/submission-profile`, "PUT", profile);
    localStorage.removeItem(profileKey);
    setProfileSaved(true);
  }
  async function action(work: () => Promise<void>) {
    setError("");
    setBusy(true);
    try {
      await work();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <p className="eyebrow">{t("ui.courseWorkspace")}</p>
      <h2>{t("ui.courseExercises")}</h2>
      <p>{t("ui.courseExercisesHelp")}</p>
      <ErrorNotice error={error} />
      {!data && !error && <p role="status">{t("ui.courseLoading")}</p>}
      {profile && (
        <details className="submission-details" open>
          <summary>{t("ui.courseSubmissionDetails")}</summary>
          <fieldset disabled={busy}>
            <div className="course-fields">
              <label>
                {t("ui.courseName")}
                <input
                  value={profile.course_name}
                  maxLength={200}
                  onChange={(e) =>
                    changeProfile({ ...profile, course_name: e.target.value })
                  }
                />
              </label>
              <label>
                {t("ui.courseSemester")}
                <input
                  value={profile.semester}
                  maxLength={80}
                  placeholder="WS26/27"
                  onChange={(e) =>
                    changeProfile({ ...profile, semester: e.target.value })
                  }
                />
              </label>
            </div>
            {profile.authors.map((author, index) => (
              <div key={index} className="course-fields">
                <label>
                  {t("ui.courseAuthor", { number: index + 1 })}
                  <input
                    value={author.name}
                    maxLength={160}
                    onChange={(e) =>
                      changeProfile({
                        ...profile,
                        authors: profile.authors.map((a, i) =>
                          i === index ? { ...a, name: e.target.value } : a,
                        ),
                      })
                    }
                  />
                </label>
                <label>
                  {t("ui.courseMatriculation")}
                  <input
                    value={author.matrikelnummer}
                    maxLength={40}
                    onChange={(e) =>
                      changeProfile({
                        ...profile,
                        authors: profile.authors.map((a, i) =>
                          i === index
                            ? { ...a, matrikelnummer: e.target.value }
                            : a,
                        ),
                      })
                    }
                  />
                </label>
                <button
                  disabled={profile.authors.length === 1}
                  onClick={() =>
                    changeProfile({
                      ...profile,
                      authors: profile.authors.filter((_, i) => i !== index),
                    })
                  }
                >
                  {t("ui.courseRemoveAuthor")}
                </button>
              </div>
            ))}
            <button
              disabled={profile.authors.length >= 10}
              onClick={() =>
                changeProfile({
                  ...profile,
                  authors: [
                    ...profile.authors,
                    { name: "", matrikelnummer: "" },
                  ],
                })
              }
            >
              {t("ui.courseAddAuthor")}
            </button>
            <button onClick={() => void action(saveProfile)}>
              {t("ui.courseSaveDetails")}
            </button>
            {profileSaved && <span role="status">{t("ui.courseSaved")}</span>}
          </fieldset>
        </details>
      )}
      <label>
        {t("ui.courseUploadExercise")}
        <input
          type="file"
          accept=".pdf"
          disabled={busy || !data}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            void action(async () => {
              const form = new FormData();
              form.append("file", file);
              const sheet = await api<ExerciseSheet>(
                `/exams/${exam}/exercises`,
                "POST",
                form,
              );
              setData(await api(`/exams/${exam}/exercises`));
              setSelected(sheet.id);
            });
          }}
        />
      </label>
      {data && !data.sheets.length && <p>{t("ui.courseEmpty")}</p>}
      {!!data?.sheets.length && (
        <label>
          {t("ui.courseChooseSheet")}
          <select
            value={selected || ""}
            disabled={busy}
            onChange={(e) => setSelected(Number(e.target.value))}
          >
            {data.sheets.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
      )}
      {selected && data && (
        <ExerciseEditor
          key={`${exam}:${selected}`}
          exam={exam}
          ident={selected}
          pdfAvailable={data.pdf_export_available}
          saveProfile={saveProfile}
          busy={busy}
          setBusy={setBusy}
          onSaved={(sheet) =>
            setData(
              (previous) =>
                previous && {
                  ...previous,
                  sheets: previous.sheets.map((s) =>
                    s.id === sheet.id ? sheet : s,
                  ),
                },
            )
          }
        />
      )}
    </section>
  );
}

function ExerciseEditor({
  exam,
  ident,
  pdfAvailable,
  saveProfile,
  busy,
  setBusy,
  onSaved,
}: {
  exam: number;
  ident: number;
  pdfAvailable: boolean;
  saveProfile: () => Promise<void>;
  busy: boolean;
  setBusy: (busy: boolean) => void;
  onSaved: (sheet: ExerciseSheet) => void;
}) {
  const { t } = useTranslation();
  const [sheet, setSheet] = useState<ExerciseSheet>();
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [pdf, setPdf] = useState<Uint8Array>();
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPages, setPreviewPages] = useState(1);
  const draftKey = `colloquily.exercise.${exam}.${ident}`;
  const path = `/exams/${exam}/exercises/${ident}`;
  useEffect(() => {
    const controller = new AbortController();
    void api<ExerciseSheet>(path, "GET", undefined, controller.signal)
      .then((value) => {
        const draft = readDraft<ExerciseSheet>(draftKey);
        setSheet(draft || value);
        setDirty(!!draft);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e));
      });
    return () => controller.abort();
  }, [path, draftKey]);
  function change(next: ExerciseSheet) {
    setSheet(next);
    setDirty(true);
    setPdf(undefined);
    try {
      localStorage.setItem(draftKey, JSON.stringify(next));
    } catch (e) {
      setError(String(e));
    }
  }
  async function save() {
    if (!sheet) throw new Error(t("ui.courseLoading"));
    const saved = await api<ExerciseSheet>(path, "PUT", {
      title: sheet.title,
      latex: sheet.latex,
      revision: sheet.revision,
    });
    setSheet(saved);
    setDirty(false);
    localStorage.removeItem(draftKey);
    onSaved(saved);
    return saved;
  }
  async function act(kind: "save" | "tex" | "pdf") {
    setBusy(true);
    setError("");
    try {
      await save();
      if (kind !== "save") {
        await saveProfile();
        const bytes = await apiBytes(
          `${path}/${kind}`,
          kind === "pdf" ? "POST" : "GET",
        );
        if (kind === "pdf") {
          setPdf(bytes);
          setPreviewPage(1);
        }
        downloadBytes(
          bytes,
          `exercise-${ident}.${kind}`,
          kind === "pdf" ? "application/pdf" : "application/x-tex",
        );
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <ErrorNotice error={error} />
      {!sheet ? (
        <p role="status">{t("ui.courseLoading")}</p>
      ) : (
        <>
          <div className="exercise-columns">
            <article>
              <h3>{t("ui.courseSheet")}</h3>
              <div className="toolbar">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  {t("ui.coursePrevious")}
                </button>
                <span>
                  {page} / {sheet.pages}
                </span>
                <button
                  disabled={page >= sheet.pages}
                  onClick={() => setPage(page + 1)}
                >
                  {t("ui.courseNext")}
                </button>
              </div>
              <Suspense fallback={<p>{t("ui.loadingPdf")}</p>}>
                <PdfPreview
                  exam={exam}
                  path=""
                  apiPath={`${path}/source`}
                  page={page}
                />
              </Suspense>
            </article>
            <article>
              <h3>{t("ui.courseSolution")}</h3>
              <fieldset disabled={busy}>
                <label>
                  {t("ui.courseSheetTitle")}
                  <input
                    value={sheet.title}
                    maxLength={200}
                    onChange={(e) =>
                      change({ ...sheet, title: e.target.value })
                    }
                  />
                </label>
                <p className="muted">{t("ui.courseLatexHelp")}</p>
                <label htmlFor="exercise-latex">
                  {t("ui.courseLatexBody")}
                </label>
                <textarea
                  id="exercise-latex"
                  className="latex-editor"
                  spellCheck={false}
                  value={sheet.latex}
                  maxLength={200000}
                  onChange={(e) => change({ ...sheet, latex: e.target.value })}
                />
                <p role="status">
                  {t(
                    busy
                      ? "ui.courseSaving"
                      : dirty
                        ? "ui.courseDraft"
                        : "ui.courseSaved",
                  )}
                </p>
                <div className="toolbar">
                  {dirty && (
                    <button
                      onClick={() => {
                        if (!window.confirm(t("ui.courseDiscardDraft"))) return;
                        setBusy(true);
                        setError("");
                        void api<ExerciseSheet>(path)
                          .then((saved) => {
                            setSheet(saved);
                            setDirty(false);
                            setPdf(undefined);
                            localStorage.removeItem(draftKey);
                          })
                          .catch((e) => setError(String(e)))
                          .finally(() => setBusy(false));
                      }}
                    >
                      {t("ui.courseLoadSaved")}
                    </button>
                  )}
                  <button onClick={() => void act("save")}>
                    {t("ui.courseSaveSolution")}
                  </button>
                  <button onClick={() => void act("tex")}>
                    {t("ui.courseExportTex")}
                  </button>
                  <button
                    className="primary"
                    disabled={!pdfAvailable}
                    onClick={() => void act("pdf")}
                  >
                    {t("ui.courseExportPdf")}
                  </button>
                </div>
              </fieldset>
              {!pdfAvailable && <p>{t("ui.courseLatexMissing")}</p>}
            </article>
          </div>
          {pdf && (
            <article>
              <h3>{t("ui.courseExportPreview")}</h3>
              <p>{t("ui.courseExportPreviewHelp")}</p>
              <div className="toolbar">
                <button
                  disabled={previewPage <= 1}
                  onClick={() => setPreviewPage(previewPage - 1)}
                >
                  {t("ui.coursePrevious")}
                </button>
                <span>
                  {previewPage} / {previewPages}
                </span>
                <button
                  disabled={previewPage >= previewPages}
                  onClick={() => setPreviewPage(previewPage + 1)}
                >
                  {t("ui.courseNext")}
                </button>
              </div>
              <Suspense fallback={<p>{t("ui.loadingPdf")}</p>}>
                <PdfPreview
                  exam={exam}
                  path=""
                  bytes={pdf}
                  page={previewPage}
                  onPageCount={setPreviewPages}
                />
              </Suspense>
            </article>
          )}
        </>
      )}
    </>
  );
}
