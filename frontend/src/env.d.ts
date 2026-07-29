/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>;
  export default component;
}

interface ImportMetaEnv {
  /** Absolute base URL of the Django core API; empty = same origin (nginx). */
  readonly VITE_API_BASE?: string;
  /** Absolute base URL of the realtime WS service; empty = same origin (nginx). */
  readonly VITE_WS_BASE?: string;
  /** "1" builds the backend-free replay published to GitHub Pages. */
  readonly VITE_REPLAY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
