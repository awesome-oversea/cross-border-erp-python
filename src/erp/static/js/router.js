import api from './api.js';

const routes = {};
let currentRoute = '';

function register(path, handler) {
  routes[path] = handler;
}

function navigate(path) {
  window.location.hash = `#${path}`;
}

function resolve() {
  const hash = window.location.hash.slice(1) || '/login';
  const [path, queryStr] = hash.split('?');
  const params = {};
  if (queryStr) {
    for (const pair of queryStr.split('&')) {
      const [k, v] = pair.split('=');
      params[decodeURIComponent(k)] = decodeURIComponent(v || '');
    }
  }

  const matched = Object.keys(routes).find(r => {
    if (r.includes(':')) {
      const regex = new RegExp('^' + r.replace(/:[^/]+/g, '[^/]+') + '$');
      return regex.test(path);
    }
    return r === path;
  });

  if (!matched) {
    if (routes['/404']) routes['/404'](params);
    return;
  }

  if (matched !== '/login' && !api.isAuthenticated) {
    navigate('/login');
    return;
  }

  currentRoute = matched;
  const routeParams = {};
  if (matched.includes(':')) {
    const rParts = matched.split('/');
    const pParts = path.split('/');
    for (let i = 0; i < rParts.length; i++) {
      if (rParts[i].startsWith(':')) {
        routeParams[rParts[i].slice(1)] = pParts[i];
      }
    }
  }

  routes[matched]({ ...routeParams, ...params });
}

window.addEventListener('hashchange', resolve);

export { register, navigate, resolve, currentRoute };
