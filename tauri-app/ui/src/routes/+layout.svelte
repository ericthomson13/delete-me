<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';

  let { children } = $props();
  let path = $derived(page.url.pathname);
</script>

<nav>
  <a href="/" class="brand" aria-label="delete-me home">
    delete-<span class="erased">me</span>
  </a>
  <div class="links">
    <a href="/" class:active={path === '/'}>Cases</a>
    <a href="/profiles" class:active={path.startsWith('/profiles')}>People</a>
    <a href="/brokers" class:active={path.startsWith('/brokers')}>Brokers</a>
    <a href="/discovery" class:active={path.startsWith('/discovery')}>Discovery</a>
  </div>
</nav>

{@render children()}

<style>
  nav {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 0.85rem 2rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg-elevated);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }

  .brand {
    font-weight: 600;
    font-size: 1.05rem;
    color: var(--fg);
    text-decoration: none;
    letter-spacing: -0.01em;
    margin-right: 0.5rem;
  }
  .brand .erased {
    color: var(--accent);
    position: relative;
    display: inline-block;
  }
  .brand .erased::after {
    content: '';
    position: absolute;
    left: -1px;
    right: -1px;
    top: 51%;
    border-bottom: 1.5px solid var(--accent);
    transform-origin: left center;
    transform: rotate(-3deg);
  }

  .links {
    display: flex;
    gap: 1.25rem;
  }

  nav a:not(.brand) {
    color: var(--fg-muted);
    text-decoration: none;
    font-size: 0.92rem;
    padding-bottom: 0.15rem;
    border-bottom: 2px solid transparent;
    transition: color 120ms;
  }
  nav a:not(.brand):hover { color: var(--fg); }
  nav a.active {
    color: var(--fg);
    border-bottom-color: var(--accent);
  }
</style>
