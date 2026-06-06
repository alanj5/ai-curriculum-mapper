/** Tiny hash router.
 *  Routes look like  #/explore?module=IC50001  — a page name plus optional
 *  query params. Pages register a mount(appEl, params) function; navigating
 *  swaps the #app contents and updates the active nav item. Real URLs mean the
 *  back button and shareable links just work. */

const routes = {};
// Land on the Overview (a friendly home that foregrounds the Curriculum Map as
// its primary call-to-action), so first-timers get context before the graph.
const DEFAULT = 'overview';

export function registerRoute(name, mountFn) { routes[name] = mountFn; }

export function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');          // "explore?module=IC50001"
  const [path, query = ''] = raw.split('?');
  const name = path || DEFAULT;
  const params = Object.fromEntries(new URLSearchParams(query));
  return { name, params };
}

/** Programmatic navigation used by deep-link buttons across pages. */
export function navigate(name, params = {}) {
  const q = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
  ).toString();
  location.hash = `#/${name}${q ? '?' + q : ''}`;
}

async function handleRoute() {
  const { name, params } = parseHash();
  const resolved = routes[name] ? name : DEFAULT;

  document.querySelectorAll('.tab-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.route === resolved));

  const app = document.getElementById('app');
  app.scrollTop = 0;
  window.scrollTo(0, 0);
  try {
    await routes[resolved](app, params);
  } catch (e) {
    app.innerHTML = `<div class="page"><p class="placeholder error">Could not load this page: ${e.message}</p></div>`;
  }
}

export function initRouter() {
  window.addEventListener('hashchange', handleRoute);
  if (!location.hash) { location.hash = `#/${DEFAULT}`; return; }  // triggers hashchange
  handleRoute();
}
