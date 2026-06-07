/** Small shared cache for data reused across pages (avoids refetching). */
import { api } from './api.js';

let _ka = null;
let _modules = null;

/** CS2023 Knowledge-Area options [{code, name}], cached for the session. */
export async function getKaOptions() {
  if (_ka) return _ka;
  const coverage = await api.coverage();
  _ka = coverage.map(c => ({ code: c.ka_code, name: c.ka_name }));
  return _ka;
}

/** Full module list, cached for the session. */
export async function getModules() {
  if (_modules) return _modules;
  _modules = await api.modules({ limit: 200 });
  return _modules;
}
