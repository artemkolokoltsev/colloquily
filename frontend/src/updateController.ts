// Framework-independent update lifecycle; native calls are injected for testing.
export interface UpdateArtifact {
  version: string;
  body?: string;
  download: (
    progress: (event: {
      event: string;
      data?: { contentLength?: number; chunkLength?: number };
    }) => void,
  ) => Promise<void>;
  install: () => Promise<void>;
  close: () => Promise<void>;
}
export interface UpdateState {
  phase:
    | "idle"
    | "checking"
    | "current"
    | "available"
    | "downloading"
    | "ready"
    | "installing"
    | "restarting"
    | "error";
  version?: string;
  notes?: string;
  progress?: number;
  error?: string;
}
export class UpdateController {
  state: UpdateState = { phase: "idle" };
  artifact: UpdateArtifact | null = null;
  downloaded = false;
  installed = false;
  listeners = new Set<() => void>();
  private operation: Promise<unknown> | null = null;
  private deps: {
    check: () => Promise<UpdateArtifact | null>;
    safe: () => Promise<boolean>;
    begin: () => Promise<unknown>;
    cancel: () => Promise<unknown>;
    relaunch: () => Promise<void>;
  };
  constructor(deps: UpdateController["deps"]) {
    this.deps = deps;
  }
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  snapshot = () => this.state;
  private set(next: Partial<UpdateState>) {
    this.state = { ...this.state, ...next };
    this.listeners.forEach((listener) => listener());
  }
  private run(work: () => Promise<unknown>) {
    if (this.operation) return this.operation;
    this.operation = work().finally(() => {
      this.operation = null;
    });
    return this.operation;
  }
  async check() {
    if (this.artifact) return this.artifact; // Keep a verified/downloaded release until restart.
    await this.run(async () => {
      this.set({ phase: "checking", error: undefined });
      try {
        this.artifact = await this.deps.check();
        this.set({
          phase: this.artifact ? "available" : "current",
          version: this.artifact?.version,
          notes: this.artifact?.body,
        });
      } catch (error) {
        this.set({ phase: "error", error: String(error) });
        throw error;
      }
    });
    return this.artifact;
  }
  async download() {
    if (!this.artifact || this.downloaded) return;
    await this.run(async () => {
      this.set({ phase: "downloading", error: undefined, progress: undefined });
      let total = 0,
        completed = 0;
      try {
        await this.artifact!.download((event) => {
          if (event.event === "Started") total = event.data?.contentLength ?? 0;
          if (event.event === "Progress")
            completed += event.data?.chunkLength ?? 0;
          this.set({
            progress: total
              ? Math.min(100, Math.round((completed / total) * 100))
              : undefined,
          });
        });
        this.downloaded = true;
        this.set({ phase: "ready", progress: 100 });
      } catch (error) {
        this.set({ phase: "error", error: String(error) });
        throw error;
      }
    });
  }
  async install() {
    if (!this.artifact || this.operation) return;
    await this.download();
    await this.run(async () => {
      let reserved = false;
      try {
        if (!(await this.deps.safe())) {
          this.set({ phase: "ready" });
          return;
        }
        this.set({ phase: "installing", error: undefined });
        // The server rechecks activity under its exclusive workspace lock and backs up first.
        reserved = true;
        await this.deps.begin();
        if (!this.installed) {
          await this.artifact!.install();
          this.installed = true;
        }
        this.set({ phase: "restarting" });
        await this.deps.relaunch();
      } catch (error) {
        if (reserved) await this.deps.cancel().catch(() => undefined);
        this.set({ phase: "error", error: String(error) });
        throw error;
      }
    });
  }
}
