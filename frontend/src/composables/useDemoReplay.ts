import { onBeforeUnmount, onMounted } from "vue";

import { getDemoEngine } from "../demo/engine";
import { useDashboardStore } from "../stores/dashboard";

/** The replay build's stand-in for `useDashboardSocket`.
 *
 * Same contract, same store actions, same event shapes: it subscribes to the
 * in-browser engine and forwards each frame to `store.applyEvent`, which is
 * the identical call the real WebSocket makes. The connection badge is set
 * to "online" because, for the purposes of the dashboard, the event source
 * is up; the banner in the header is what tells the reader it is a replay.
 */
export function useDemoReplay(): void {
  const store = useDashboardStore();
  let unsubscribe: (() => void) | null = null;

  onMounted(() => {
    store.setConnection("connecting");
    unsubscribe = getDemoEngine().subscribe((event) => store.applyEvent(event));
    getDemoEngine().start();
    store.setConnection("online");
  });

  onBeforeUnmount(() => {
    unsubscribe?.();
    getDemoEngine().stop();
  });
}
