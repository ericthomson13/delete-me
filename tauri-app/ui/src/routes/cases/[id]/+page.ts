// This route renders client-side: it fetches the case by id from the
// FastAPI sidecar on mount. SvelteKit can't prerender a dynamic [id]
// without an entries() resolver, and the adapter-static fallback
// (index.html) handles SPA navigation at runtime.
export const prerender = false;
