const root = document.querySelector('#pageRoot');
const crumbs = document.querySelector('#breadcrumbs');
const banner = document.querySelector('#degradedBanner');
const healthPill = document.querySelector('#healthPill');
const navStatusText = document.querySelector('#navStatusText');
const navStatusDot = document.querySelector('#navStatusDot');
const searchBox = document.querySelector('#globalSearch');
const appShell = document.querySelector('#appShell');
const navToggle = document.querySelector('#navToggle');
function setNavigationOpen(open) {
  appShell.classList.toggle('nav-open', open);
  navToggle.setAttribute('aria-expanded', String(open));
}
const i18n = window.SCP_I18N;
const localeZh = document.querySelector('#localeZh');
const localeEn = document.querySelector('#localeEn');
const themePreference = document.querySelector('#themePreference');
const themeMedia = matchMedia('(prefers-color-scheme: dark)');
function applyTheme() {
  document.documentElement.dataset.theme = themePreference.value === 'system'
    ? (themeMedia.matches ? 'dark' : 'light') : themePreference.value;
  document.querySelector('meta[name="theme-color"]').content =
    document.documentElement.dataset.theme === 'dark' ? '#121c1e' : '#f7f8f4';
}
try { themePreference.value = localStorage.getItem('scp-theme') || 'light'; } catch { themePreference.value = 'light'; }
applyTheme();
themePreference.addEventListener('change', () => {
  try { localStorage.setItem('scp-theme', themePreference.value); } catch {}
  applyTheme();
});
themeMedia.addEventListener('change', () => {
  if (themePreference.value === 'system') applyTheme();
});
const state = { health: null, editor: null, locale: i18n.resolveLocale(), localizing: false };

function applyLocale(scope = document) {
  i18n.applyStatic(document, state.locale);
  for (const node of document.querySelectorAll('.mono,.path,pre,code,[data-no-i18n]')) {
    node.setAttribute('translate', 'no');
  }
  if (state.locale === 'zh-CN') {
    state.localizing = true;
    i18n.localizeTree(scope === document ? document.body : scope, state.locale);
    state.localizing = false;
  }
  localeZh.setAttribute('aria-pressed', String(state.locale === 'zh-CN'));
  localeEn.setAttribute('aria-pressed', String(state.locale === 'en'));
  localeZh.classList.toggle('active', state.locale === 'zh-CN');
  localeEn.classList.toggle('active', state.locale === 'en');
}

async function setLocale(locale) {
  if (!i18n.LOCALES.includes(locale) || locale === state.locale) return;
  state.locale = locale;
  try { localStorage.setItem(i18n.STORAGE_KEY, locale); } catch {}
  applyLocale(document);
  await render();
}

let localizationScheduled = false;
const localizationObserver = new MutationObserver(() => {
  if (state.locale !== 'zh-CN' || state.localizing || localizationScheduled) return;
  localizationScheduled = true;
  queueMicrotask(() => {
    localizationScheduled = false;
    applyLocale(root);
  });
});
localizationObserver.observe(root, { childList: true, subtree: true });

const esc = (value = '') => String(value).replace(/[&<>"']/g, ch => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[ch]));
const pretty = value => JSON.stringify(value ?? {}, null, 2);
const mono = value => `<span class="mono">${esc(value ?? '—')}</span>`;
const badge = (label, tone = '') => `<span class="badge ${tone}">${esc(label)}</span>`;
const statusTone = status => ({ completed: 'good', active: 'accent', running: 'accent', blocked: 'warn', failed: 'bad', planned: '' }[status] || '');
const msg = (key, vars = {}) => i18n.message(state.locale, key, vars);

function iconSvg(name, className = 'ui-icon') {
  return '<svg class="' + esc(className) + '" aria-hidden="true" focusable="false"><use href="/assets/icons.svg#' +
    esc(name) + '"></use></svg>';
}

async function api(path, options = {}) {
  const config = { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } };
  if (config.body && typeof config.body !== 'string') config.body = JSON.stringify(config.body);
  const response = await fetch(path, config);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

function toast(message, bad = false) {
  const node = document.createElement('div');
  node.className = `toast${bad ? ' bad' : ''}`;
  node.textContent = state.locale === 'zh-CN' ? i18n.translateText(state.locale, message) : message;
  document.querySelector('#toastRegion').append(node);
  setTimeout(() => node.remove(), 4200);
}

function routeInfo() {
  const raw = (location.hash || '#/overview').slice(1);
  const [path, query = ''] = raw.split('?');
  return { parts: path.split('/').filter(Boolean), query: new URLSearchParams(query) };
}

function setCrumbs(parts) {
  const routeLabels = {
    overview: 'Overview',
    skills: 'Skills',
    workflows: 'Workflows',
    runs: 'Runs',
    deployments: 'Deployments',
    advanced: 'Advanced Tools',
    tools: 'Tools & MCP',
    system: 'System',
    health: 'Health',
    sources: 'Sources',
    organization: 'Organization',
    contexts: 'Contexts',
    validation: 'Validation',
    variants: 'Variants',
    body: 'Body',
    relations: 'Relations'
    ,about: 'About'
    ,new: 'Create'
  };
  crumbs.innerHTML = parts.map((part, index) => {
    const path = '#/' + parts.slice(0, index + 1).join('/');
    const label = routeLabels[part] || part;
    return `<a href="${path}">${esc(label)}</a>${index < parts.length - 1 ? ' / ' : ''}`;
  }).join('');
}

function loading() {
  root.innerHTML = `<div class="loading"><div class="skeleton"></div><p>Loading local canonical state…</p></div>`;
}

function pageHead(title, description = '', actions = '') {
  return `<div class="page-head"><div><h1>${esc(title)}</h1><p>${esc(description)}</p></div><div class="actions">${actions}</div></div>`;
}

const USE_CASES = [
  { id: 'web', title: 'Web & UI', query: 'frontend', icon: 'web', hint: 'Websites, frontend, UI, design and accessibility' },
  { id: 'writing', title: 'Writing & content', query: 'writing', icon: 'writing', hint: 'Copy, scripts, articles and social content' },
  { id: 'image', title: 'Images & visual', query: 'image', icon: 'image', hint: 'Image generation, posters, visual design and editing' },
  { id: 'video', title: 'Video & spoken content', query: 'video', icon: 'video', hint: 'Video, spoken content, subtitles, animation and editing' },
  { id: 'research', title: 'Research & learning', query: 'research', icon: 'research', hint: 'Research, papers, source organization and learning' },
  { id: 'browser', title: 'Browser & web actions', query: 'browser', icon: 'browser', hint: 'Web automation, testing, forms and data extraction' },
  { id: 'automation', title: 'Automation & Agents', query: 'automation', icon: 'agent', hint: 'Agents, automations, orchestration and tool calls' },
  { id: 'knowledge', title: 'Knowledge & Obsidian', query: 'obsidian', icon: 'knowledge', hint: 'Obsidian, Markdown, knowledge bases and PKM' },
  { id: 'data', title: 'Data & analysis', query: 'data', icon: 'data', hint: 'Data processing, spreadsheets, analysis and visualization' },
  { id: 'slides', title: 'Slides & office', query: 'presentation', icon: 'slides', hint: 'Slides, presentations, office documents and reports' },
  { id: 'code', title: 'Coding & development', query: 'coding', icon: 'code', hint: 'Coding, debugging, testing, refactoring and engineering' },
  { id: 'system', title: 'System & tools', query: 'mcp', icon: 'system', hint: 'MCP, system tools, terminals and development environments' }
];

function useCaseLabel(item) {
  return msg(item.title);
}
const LOCATION_GROUPS = [
  { id: 'workspace', title: 'Workspace Skills', query: 'coding-tools-mcp-demo', icon: 'folder', hint: 'Skills discovered inside the current coding-tools workspace.' },
  { id: 'workbuddy', title: 'WorkBuddy Skills', query: 'workbuddy', icon: 'folder', hint: 'Skills installed by WorkBuddy plugin marketplaces.' },
  { id: 'trae', title: 'Trae Skills', query: 'trae-cn', icon: 'folder', hint: 'Skills from Trae skills and design libraries.' },
  { id: 'chatbox', title: 'ChatBox built-in Skills', query: 'xyz.chatboxapp.app', icon: 'folder', hint: 'Skills bundled with the local ChatBox app.' },
  { id: 'archive', title: 'Archived Skills', query: '40_Archive', icon: 'folder', hint: 'Older Skill copies kept under the local archive.' }
];

function skillLocation(path = '') {
  const value = String(path).toLowerCase();
  if (value.includes('\\.workbuddy\\')) return LOCATION_GROUPS.find(item => item.id === 'workbuddy');
  if (value.includes('\\.trae-cn\\')) return LOCATION_GROUPS.find(item => item.id === 'trae');
  if (value.includes('xyz.chatboxapp.app')) return LOCATION_GROUPS.find(item => item.id === 'chatbox');
  if (value.includes('\\40_archive\\')) return LOCATION_GROUPS.find(item => item.id === 'archive');
  if (value.includes('coding-tools-mcp-demo')) return LOCATION_GROUPS.find(item => item.id === 'workspace');
  return { id: 'other', title: 'Other local Skills', icon: 'folder', hint: 'Skills discovered from other local folders.' };
}

async function loadLocationCounts() {
  const values = await Promise.all(LOCATION_GROUPS.map(async item => {
    try {
      const data = await api('/api/skills?limit=1&query=' + encodeURIComponent(item.query));
      return [item.id, Number(data.total || 0)];
    } catch {
      return [item.id, 0];
    }
  }));
  return Object.fromEntries(values);
}

function locationGrid(counts, activeId = '') {
  return '<div class="location-grid">' + LOCATION_GROUPS.map(item =>
    '<a class="location-card' + (item.id === activeId ? ' active' : '') + '" href="#/skills?browse=location&location=' + encodeURIComponent(item.id) + '">' +
    '<span class="location-icon">' + iconSvg(item.icon) + '</span><span class="location-copy"><strong>' + esc(msg(item.title)) +
    '</strong><small>' + esc(msg(item.hint)) + '</small><b>' + esc(msg('location.count', { count: counts[item.id] || 0 })) +
    '</b></span>' + iconSvg('arrow', 'card-arrow') + '</a>'
  ).join('') + '</div>';
}

function inferUseCases(skill) {
  const haystack = [skill.name, skill.skill_id, skill.description].filter(Boolean).join(' ').toLowerCase();
  const matches = USE_CASES.filter(item => {
    const words = {
      web: ['frontend', 'web ', 'ui ', 'ux ', 'design', 'css', 'html', 'accessibility'],
      writing: ['writing', 'writer', 'copy', 'script', 'social', 'content', '文章', '文案'],
      image: ['image', 'visual', 'poster', 'photo', 'figma', 'illustration'],
      video: ['video', 'remotion', 'subtitle', 'media', '口播', '剪辑'],
      research: ['research', 'paper', 'academic', 'study', 'literature', '调研'],
      browser: ['browser', 'playwright', 'selenium', 'website automation'],
      automation: ['automation', 'agent', 'workflow', 'orchestrat', 'mcp'],
      knowledge: ['obsidian', 'markdown', 'knowledge', 'pkm', 'notion'],
      data: ['data', 'csv', 'spreadsheet', 'excel', 'analytics', 'visualization'],
      slides: ['presentation', 'slides', 'ppt', 'powerpoint', 'office'],
      code: ['code', 'coding', 'debug', 'test', 'refactor', 'typescript', 'python', 'developer'],
      system: ['mcp', 'windows', 'shell', 'terminal', 'devops', 'server']
    }[item.id] || [item.query];
    return words.some(word => haystack.includes(word));
  });
  return matches.slice(0, 3);
}

function beginnerSkillSummary(skill, cases = inferUseCases(skill)) {
  const raw = skill.description && skill.description !== '>'
    ? String(skill.description).trim()
    : '';
  if (!raw) return 'This Skill does not have a clear summary yet. Open its details to inspect the original description.';
  if (state.locale === 'zh-CN' && !/[\u4e00-\u9fff]/.test(raw)) {
    const labels = cases.map(useCaseLabel).join('、');
    return labels
      ? msg('skill.detectedSummary', { useCases: labels })
      : msg('skill.detectedSummaryUnknown');
  }
  return raw;
}

const CAPABILITY_KINDS = {
  single: {
    label: 'Single Skill',
    hint: 'Completes one focused task directly.',
    icon: 'skill'
  },
  composite: {
    label: 'Composite Skill',
    hint: 'Contains its own multi-step workflow or coordinates other Skills.',
    icon: 'automation'
  },
  router: {
    label: 'Router Skill',
    hint: 'Chooses an internal route or child Skill based on the task.',
    icon: 'route'
  },
  agent: {
    label: 'Agent & tool Skill',
    hint: 'Defines how an Agent should use MCPs, tools, recovery and validation.',
    icon: 'agent'
  }
};

const AGENT_TOOL_HINTS = [
  { id: 'coding-tools', label: 'Coding Tools', icon: 'code', pattern: /coding tools|code edit|edit files|run tests|git\b|build\b/i },
  { id: 'playwright', label: 'Playwright', icon: 'browser', pattern: /playwright|browser automation|browser qa|web page|webpage|dom\b/i },
  { id: 'desktop', label: 'Remote Desktop Commander', icon: 'system', pattern: /desktop commander|remote desktop|host files|local process|processes|local service/i },
  { id: 'serena', label: 'Serena', icon: 'research', pattern: /serena|symbol search|references to symbol|code structure|semantic code/i },
  { id: 'windows', label: 'Windows-MCP', icon: 'advanced', pattern: /windows-mcp|windows mcp|native windows|system dialog|desktop ui/i }
];

function inferCapabilityKind(skill, content = '') {
  const text = [
    skill?.name,
    skill?.skill_id,
    skill?.description,
    content
  ].filter(Boolean).join('\n').toLowerCase();

  const explicitRouter = skill?.category_router || text.includes('references/routes.md');
  if (explicitRouter) {
    return CAPABILITY_KINDS.router;
  }

  const hasToolProtocol = /\bmcp\b|playwright|serena|coding tools|windows-mcp|desktop commander|gateway/.test(text);
  const hasAgentProtocol = /\bagent\b|tool routing|recovery|fallback|validation|执行协议|工具路由|恢复/.test(text);
  if (hasToolProtocol && hasAgentProtocol) return CAPABILITY_KINDS.agent;

  if (/\brouter\b|route selection|routing skill|内部路由|路由技能/.test(text)) {
    return CAPABILITY_KINDS.router;
  }

  const hasWorkflow = /default workflow|workflow|orchestrat|pipeline|multi-step|工作流|执行流程|多步流程/.test(text);
  const coordinatesOthers = /other skills|child skill|route.+skill|use.+skill|call.+skill|调用.{0,20}skill|使用.{0,20}skill/.test(text);
  if (hasWorkflow || coordinatesOthers) return CAPABILITY_KINDS.composite;

  return CAPABILITY_KINDS.single;
}

function analyzeSkillContent(skill, content = '') {
  const body = String(content || '');
  const kind = inferCapabilityKind(skill, body);
  const childSkills = new Set();
  const internalFiles = new Set();
  const toolHints = AGENT_TOOL_HINTS.filter(tool => tool.pattern.test(body));
  const childPatterns = [
    /(?:use|using|invoke|call|load|route(?:s)? to|使用|调用|加载|路由到|切换到)[^\n`]{0,80}`([a-z0-9][a-z0-9._-]{1,})`/gi,
    /`([a-z0-9][a-z0-9._-]{1,})`\s*(?:skill|技能)/gi,
    /(?:skill(?:_id)?|子\s*skill|子技能)\s*[:=：]\s*`?([a-z0-9][a-z0-9._-]{1,})`?/gi,
    /(?:route through|route to|delegate to|路由到|交给)\s+`?([a-z][a-z0-9._-]{2,})`?/gi
  ];
  for (const pattern of childPatterns) {
    for (const match of body.matchAll(pattern)) {
      const value = String(match[1] || '').trim();
      if (!value || /[\\/]/.test(value) || /\.(md|json|js|mjs|cjs|ts|py|ps1|cmd|sh|yaml|yml|png|svg)$/i.test(value)) continue;
      if (/^v?\d+(?:\.\d+){1,3}(?:[-+][\w.-]+)?$/i.test(value)) continue;
      if (value.toLowerCase() === String(skill?.skill_id || '').toLowerCase()) continue;
      childSkills.add(value);
    }
  }
  const filePattern = /(?:\(|`)((?:references|routes|scripts|assets)\/[^\s)`]+|EVOLUTION\.md)(?:\)|`)/gi;
  for (const match of body.matchAll(filePattern)) internalFiles.add(String(match[1]));
  return {
    kind,
    childSkills: [...childSkills].slice(0, 12),
    internalFiles: [...internalFiles].slice(0, 12),
    toolHints,
    recursive: kind !== CAPABILITY_KINDS.single || childSkills.size > 0 || internalFiles.size > 0
  };
}

const skillResolveCache = new Map();

async function resolveKnownChildSkills(candidates = []) {
  const unique = [...new Set(
    candidates
      .map(value => String(value || '').trim().toLowerCase())
      .filter(Boolean)
  )].slice(0, 16);
  const resolved = await Promise.all(unique.map(async skillId => {
    if (skillResolveCache.has(skillId)) return skillResolveCache.get(skillId) ? skillId : null;
    let exists = false;
    try {
      const result = await api('/api/skills?query=' + encodeURIComponent(skillId) + '&limit=8');
      exists = (result.items || []).some(item => String(item.skill_id || '').toLowerCase() === skillId);
    } catch {
      exists = false;
    }
    skillResolveCache.set(skillId, exists);
    return exists ? skillId : null;
  }));
  return resolved.filter(Boolean);
}

function referencedResourcePaths(content = '') {
  const paths = new Set();
  const text = String(content || '');
  const pattern = /(?:\.\/)?((?:[a-z0-9._-]+\/)*[a-z0-9._-]+\.(?:md|txt|json|ya?ml|py|m?js|cjs|tsx?|jsx|ps1|cmd|bat|sh))/gi;
  for (const match of text.matchAll(pattern)) {
    const path = String(match[1] || '').replace(/\\/g, '/').replace(/^\.\//, '');
    if (path && !path.includes('../')) paths.add(path);
  }
  return [...paths];
}

function capabilityResourceClosure(rootContent, resources = []) {
  const byPath = new Map(resources.map(resource => [
    String(resource.path || '').replace(/\\/g, '/').toLowerCase(),
    resource
  ]));
  const selected = [];
  const seen = new Set();
  const queue = referencedResourcePaths(rootContent);
  while (queue.length && selected.length < 64) {
    const requested = String(queue.shift() || '').toLowerCase();
    const resource = byPath.get(requested);
    if (!resource || seen.has(requested)) continue;
    seen.add(requested);
    selected.push(resource);
    for (const nested of referencedResourcePaths(resource.content || '')) {
      if (!seen.has(nested.toLowerCase())) queue.push(nested);
    }
  }
  return selected;
}

function internalRouteSkills(resources = []) {
  return resources
    .filter(resource => /(?:^|\/)routes\/[^/]+\/SKILL\.md$/i.test(String(resource.path || '')))
    .slice(0, 12)
    .map(resource => {
      const path = String(resource.path || '');
      const name = path.split('/').slice(-2, -1)[0] || path;
      const content = String(resource.content || '');
      const descriptionMatch = content.match(/^description:\s*["']?(.+?)["']?\s*$/mi);
      return {
        name,
        path,
        description: descriptionMatch ? descriptionMatch[1].trim() : ''
      };
    });
}

async function loadSkillCapabilityBundle(skillId, depth = 0, visited = new Set()) {
  const normalized = String(skillId || '').trim().toLowerCase();
  if (!normalized || visited.has(normalized)) return null;
  const nextVisited = new Set(visited);
  nextVisited.add(normalized);

  const [skill, body, bundle] = await Promise.all([
    api('/api/skills/' + encodeURIComponent(normalized)),
    api('/api/skills/' + encodeURIComponent(normalized) + '/body'),
    api('/api/skills/' + encodeURIComponent(normalized) + '/resources')
  ]);
  const resources = Array.isArray(bundle.resources) ? bundle.resources : [];
  const rootContent = String(body.content || '');
  const rootAnalysis = analyzeSkillContent(skill, rootContent);
  let followedResources = capabilityResourceClosure(rootContent, resources);
  if (!followedResources.length && rootAnalysis.kind === CAPABILITY_KINDS.router) {
    followedResources = resources.filter(resource =>
      /(?:^|\/)(?:routing\.md|references\/routes\.md|routes\.md|route\.md|routes\/[^/]+\/SKILL\.md)$/i.test(
        String(resource.path || '')
      )
    ).slice(0, 24);
  }
  const executionText = followedResources
    .map(resource => '\n\n# Followed capability resource: ' + resource.path + '\n' + (resource.content || ''))
    .join('');
  const routeAnalysis = analyzeSkillContent(skill, rootContent + executionText);
  const internalRoutes = internalRouteSkills(resources);
  const followedRouteFile = followedResources.some(resource =>
    /(?:^|\/)(?:routing\.md|routes\.md|route\.md|references\/routes\.md|routes\/)/i.test(
      String(resource.path || '')
    )
  );
  const effectiveKind = rootAnalysis.kind === CAPABILITY_KINDS.agent
    ? CAPABILITY_KINDS.agent
    : (
        rootAnalysis.kind === CAPABILITY_KINDS.router ||
        internalRoutes.length ||
        followedRouteFile
      )
      ? CAPABILITY_KINDS.router
      : (rootAnalysis.kind !== CAPABILITY_KINDS.single ? rootAnalysis.kind : routeAnalysis.kind);
  const analysis = {
    ...routeAnalysis,
    kind: effectiveKind,
    childSkills: await resolveKnownChildSkills(routeAnalysis.childSkills),
    internalFiles: followedResources.map(resource => String(resource.path || '')).filter(Boolean).slice(0, 24),
    internalRoutes,
    toolHints: routeAnalysis.toolHints,
    recursive: rootAnalysis.recursive || resources.length > 0 || routeAnalysis.childSkills.length > 0
  };
  analysis.resourcePaths = resources.map(resource => resource.path);
  analysis.resourceCount = Number(bundle.resource_count || resources.length);
  analysis.followedResourcePaths = followedResources.map(resource => resource.path);
  analysis.followedResourceCount = followedResources.length;
  analysis.bundleTruncated = !!bundle.truncated;

  const children = [];
  if (depth > 0) {
    for (const childId of analysis.childSkills.slice(0, 8)) {
      try {
        const child = await loadSkillCapabilityBundle(childId, depth - 1, nextVisited);
        if (child) children.push(child);
      } catch {
        children.push({
          skill: { skill_id: childId, name: childId },
          analysis: { kind: CAPABILITY_KINDS.single, resourceCount: 0, childSkills: [] },
          children: [],
          unresolved: true
        });
      }
    }
  }

  return { skill, body, bundle, analysis, children };
}

function capabilityRouteGraph(bundle) {
  if (!bundle) return '';
  const renderNode = (node, depth = 0) => {
    const analysis = node.analysis || {};
    const capability = analysis.kind || CAPABILITY_KINDS.single;
    const childRows = Array.isArray(node.children) ? node.children : [];
    const internalRoutes = Array.isArray(analysis.internalRoutes) ? analysis.internalRoutes : [];
    const resourceCount = Number(analysis.followedResourceCount || analysis.resourceCount || 0);
    const classes = ['capability-route-node'];
    if (node.unresolved) classes.push('unresolved');
    if (capability === CAPABILITY_KINDS.router) classes.push('router-node');
    const note = node.unresolved
      ? '<small>Could not resolve this child Skill locally</small>'
      : '<small>' + esc(msg(capability.label)) +
        (resourceCount ? ' · ' + resourceCount + ' ' + esc(msg('Loaded internal files')) : '') + '</small>';
    const internalRouteRows = internalRoutes.map(route =>
      '<div class="capability-route-node internal-route-node" style="--route-depth:' + (depth + 1) + '">' +
      '<div class="capability-route-node-main"><span class="capability-route-icon">' + iconSvg('route') + '</span>' +
      '<div><strong>' + esc(route.name) + '</strong><small>' + esc(msg('Internal route')) +
      ' · <span class="mono">' + esc(route.path) + '</span></small></div></div></div>'
    ).join('');
    const childSkillRows = childRows.map(child => renderNode(child, depth + 1)).join('');
    const children = internalRouteRows || childSkillRows
      ? '<div class="capability-route-children">' + internalRouteRows + childSkillRows + '</div>'
      : '';
    return '<div class="' + classes.join(' ') + '" style="--route-depth:' + depth + '">' +
      '<div class="capability-route-node-main"><span class="capability-route-icon">' + iconSvg(capability.icon) + '</span>' +
      '<div><strong>' + esc(node.skill?.name || node.skill?.skill_id || 'Skill') + '</strong>' + note + '</div></div>' +
      children + '</div>';
  };
  const rootIsRouter = bundle.analysis?.kind === CAPABILITY_KINDS.router;
  const intro = rootIsRouter
    ? '<span class="route-entry-badge">Router entry</span>'
    : '';
  return '<section class="capability-route-panel"><div class="capability-route-head"><div><strong>Route / orchestration chain</strong>' +
    '<p>This view follows SKILL.md into internal files and child Skills. A Router Skill is not considered fully loaded until its route reaches executable capabilities.</p></div>' +
    intro + '</div>' + renderNode(bundle) + '</section>';
}

function useCaseGrid() {
  return '<div class="use-case-grid">' + USE_CASES.map((item, index) =>
    '<a class="use-case-card tone-' + ((index % 4) + 1) + '" href="#/skills?use_case=' + encodeURIComponent(item.id) + '&query=' + encodeURIComponent(item.query) + '">' +
    '<span class="use-case-icon">' + iconSvg(item.icon) + '</span>' +
    '<span class="use-case-copy"><strong>' + esc(useCaseLabel(item)) + '</strong>' +
    '<span>' + esc(msg(item.hint)) + '</span></span>' + iconSvg('arrow', 'card-arrow') + '</a>'
  ).join('') + '</div>';
}

async function refreshHealth() {
  try {
    state.health = await api('/api/health');
    const ok = !!state.health.ok;
    healthPill.textContent = ok ? 'System ready' : 'System needs attention';
    healthPill.className = `health-pill ${ok ? 'good' : 'bad'}`;
    navStatusText.textContent = ok ? 'Everything is ready' : 'Some services need attention';
    navStatusDot.className = `status-dot ${ok ? 'good' : 'bad'}`;
    banner.hidden = !!state.health.mutations_allowed;
  } catch (error) {
    state.health = { ok: false, mutations_allowed: false };
    healthPill.textContent = 'System needs attention';
    healthPill.className = 'health-pill bad';
    navStatusText.textContent = 'Some services need attention';
    navStatusDot.className = 'status-dot bad';
    banner.hidden = false;
  }
}

function canMutate() {
  if (state.health?.mutations_allowed) return true;
  toast('Canonical truth is degraded; mutation is disabled.', true);
  return false;
}

async function render() {
  const { parts, query } = routeInfo();
  const section = parts[0] || 'overview';
  crumbs.hidden = section === 'overview';
  document.querySelectorAll('[data-route]').forEach(node => {
    const active = node.dataset.route === section;
    node.classList.toggle('active', active);
    if (active) node.setAttribute('aria-current', 'page');
    else node.removeAttribute('aria-current');
  });
  setCrumbs(parts.length ? parts : ['overview']);
  loading();
  setNavigationOpen(false);
  await refreshHealth();
  try {
    if (section === 'overview') await renderOverview();
    else if (section === 'skills' && parts[1]) await renderSkillDetail(parts[1], parts[2] || 'about');
    else if (section === 'skills') await renderSkills(query);
    else if (section === 'workflows' && parts[1] === 'new') await renderWorkflowEditor();
    else if (section === 'workflows' && parts[1] && parts[2] === 'new-version') await renderWorkflowEditor(parts[1]);
    else if (section === 'workflows' && parts[1]) await renderWorkflowDetail(parts[1]);
    else if (section === 'workflows') await renderWorkflows();
    else if (section === 'runs' && parts[1]) await renderRunDetail(parts[1]);
    else if (section === 'runs') await renderRuns(query);
    else if (section === 'advanced') await renderAdvanced();
    else if (section === 'tools') await renderAgentTools();
    else if (section === 'deployments') await renderDeployments();
    else if (section === 'system') await renderSystem(parts[1] || 'health', query);
    else root.innerHTML = `<div class="empty">Unknown route.</div>`;
  } catch (error) {
    root.innerHTML = `<div class="error-state"><strong>${esc(error.message)}</strong><p>Use the current page controls to retry. No mutation was retried automatically.</p></div>`;
  }
  applyLocale(document);
  const currentTitle = root.querySelector('h1')?.textContent?.trim();
  document.title = currentTitle ? currentTitle + ' · Skill Control Plane' : 'Skill Control Plane';
  document.querySelector('#main').focus({ preventScroll: true });
}

async function renderOverview() {
  const data = await api('/api/overview');
  const inv = data.inventory;
  const counts = data.counts;
  const healthy = !!data.health.ok;

  root.innerHTML =
    '<section class="welcome-hero">' +
      '<div class="welcome-copy"><span class="eyebrow">Skill Control Plane</span>' +
      '<h1>What do you want AI to help with?</h1>' +
      '<p>Skills are reusable AI capabilities. Start with the task you want to finish; you do not need to understand Skills, MCP, versions or sources first.</p></div>' +
      '<form class="hero-search" id="heroSearch"><label class="sr-only" for="heroSearchInput">Search Skills</label>' +
      '<div class="hero-search-field">' + iconSvg('search', 'search-icon') +
      '<input id="heroSearchInput" autocomplete="off" placeholder="For example: build a webpage, write a script, research a topic, edit an image, automate a browser…"></div>' +
      '<button class="button primary" type="submit">Find Skills</button></form>' +
      '<div class="home-summary"><span>' + badge(healthy ? 'System healthy' : 'Needs attention', healthy ? 'good' : 'warn') + '</span>' +
      '<span>' + esc(msg('home.availableSkills', { count: inv.skill_count })) + '</span>' +
      '<span>' + esc(msg('home.automations', { count: counts.workflows })) + '</span></div>' +
    '</section>';

  root.innerHTML += '<section class="agent-model-section" aria-label="How the Agent works">' +
    '<div class="section-head compact-head"><div><span class="section-kicker">Agent model</span><h2>How the Agent works</h2>' +
    '<p>One simple model: Skills describe capabilities, Workflows arrange them, and MCP/tools let the Agent actually operate software and the web.</p></div></div>' +
    '<div class="agent-model-grid">' +
      '<a class="agent-model-card" href="#/skills">' + iconSvg('skill', 'agent-model-icon') +
        '<span><strong>Skills</strong><small>What the Agent knows how to do</small><b>Skills are entry points, not flat commands.</b></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
      '<a class="agent-model-card" href="#/workflows">' + iconSvg('automation', 'agent-model-icon') +
        '<span><strong>Workflows</strong><small>How several capabilities work together</small><b>Composite Skills can stay intact inside one step.</b></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
      '<a class="agent-model-card" href="#/tools">' + iconSvg('system', 'agent-model-icon') +
        '<span><strong>Tools & MCP</strong><small>What the Agent can actually operate</small><b>Open tool connections</b></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
    '</div></section>';

  root.innerHTML += '<section class="home-section use-cases-section"><div class="section-head"><div><span class="section-kicker">Discover</span><h2>Browse by use case</h2><p>Start with what you want to accomplish. You do not need to remember a Skill name.</p></div><a class="section-link" href="#/skills">View all</a></div>' + useCaseGrid() + '</section>';

  root.innerHTML += '<section class="home-section quick-section"><div class="section-head"><div><span class="section-kicker">Start here</span><h2>Quick starts</h2><p>If this is your first visit, these three paths are enough.</p></div></div>' +
    '<div class="quick-grid">' +
      '<a class="quick-card quick-primary" href="#/skills"><span class="quick-icon">' + iconSvg('library') + '</span><strong>Find one Skill</strong><span>Search or browse local Skills by use case.</span><b>Start browsing →</b></a>' +
      '<a class="quick-card" href="#/workflows"><span class="quick-icon">' + iconSvg('automation') + '</span><strong>Connect multiple Skills</strong><span>Automations call multiple Skills in order and work well for repeated tasks.</span><b>View automations →</b></a>' +
      '<a class="quick-card" href="#/runs"><span class="quick-icon">' + iconSvg('activity') + '</span><strong>See recent activity</strong><span>Activity shows whether an automation succeeded, where it stopped, and which Skills it used.</span><b>View activity →</b></a>' +
    '</div></section>';

  const runLines = data.recent_runs.length ? data.recent_runs.slice(0, 4).map(run =>
    '<a class="activity-row" href="#/runs/' + esc(run.run_id) + '">' +
      '<span class="activity-status">' + badge(run.status, statusTone(run.status)) + '</span>' +
      '<span class="activity-main"><strong>' + esc(run.task || run.workflow_name) + '</strong><small>' + esc(run.workflow_name) + '</small></span>' +
      iconSvg('arrow', 'activity-arrow') + '</a>'
  ).join('') : '<div class="empty">No activity yet. Runs from your automations will appear here.</div>';

  root.innerHTML += '<section class="home-section activity-section"><div class="section-head"><div><span class="section-kicker">History</span><h2>Recent activity</h2><p>Remember work by the task itself, not by a run_id.</p></div><a class="section-link" href="#/runs">All activity</a></div>' +
    '<div class="activity-list">' + runLines + '</div></section>';

  root.innerHTML += '<details class="advanced-summary"><summary>' + iconSvg('system', 'summary-icon') + '<span>View technical system status</span></summary><div class="advanced-summary-body">' +
    '<p>These details are mainly for troubleshooting and maintenance. You usually do not need them.</p>' +
    '<div class="grid metrics compact">' +
      '<div class="metric"><strong>' + inv.variant_count + '</strong><span>Variants</span></div>' +
      '<div class="metric"><strong>' + inv.invalid_count + '</strong><span>Discovery issues</span></div>' +
      '<div class="metric"><strong>' + (data.health.parity.ok ? 'PASS' : 'DEGRADED') + '</strong><span>Parity</span></div>' +
    '</div><a class="button" href="#/advanced">Open Advanced Tools</a></div></details>';

  document.querySelector('#heroSearch').addEventListener('submit', event => {
    event.preventDefault();
    const query = document.querySelector('#heroSearchInput').value.trim();
    location.hash = '#/skills' + (query ? '?query=' + encodeURIComponent(query) : '');
  });
}

async function renderSkills(params) {
  const q = params.get('query') || '';
  const browse = params.get('browse') || 'usecase';
  const useCaseId = params.get('use_case') || '';
  const locationId = params.get('location') || '';
  const source = params.get('source_class') || '';
  const category = params.get('category_id') || '';
  const tag = params.get('tag_id') || '';
  const view = params.get('view') || 'cards';
  const cursor = Number(params.get('cursor') || 0);
  const activeUseCase = USE_CASES.find(item => item.id === useCaseId);
  const activeLocation = LOCATION_GROUPS.find(item => item.id === locationId);
  const effectiveQuery = q || activeLocation?.query || '';

  const url = new URL('/api/skills', location.origin);
  url.searchParams.set('limit', view === 'advanced' ? '50' : '24');
  url.searchParams.set('cursor', String(cursor));
  if (effectiveQuery) url.searchParams.set('query', effectiveQuery);
  if (source) url.searchParams.set('source_class', source);
  if (category) url.searchParams.set('category_id', category);
  if (tag) url.searchParams.set('tag_id', tag);
  const data = await api(url.pathname + url.search);

  let intro = 'You do not need to know a Skill name. Search for the task you want to finish, or choose a use case first.';
  if (activeUseCase) intro = msg('skills.browsingUseCase', { name: useCaseLabel(activeUseCase) });
  if (activeLocation) intro = msg(activeLocation.hint);
  root.innerHTML = pageHead('Skill Library', intro);

  root.innerHTML += '<div class="library-intro">' +
    '<form class="library-search" id="skillFilters"><div class="field grow"><label for="skillQuery">What do you want to accomplish?</label>' +
    '<div class="library-search-field">' + iconSvg('search', 'search-icon') +
    '<input id="skillQuery" name="skill-query" autocomplete="off" value="' + esc(q) + '" placeholder="For example: build a webpage, write a Xiaohongshu post, automate a browser…"></div></div>' +
    '<button class="button primary" type="submit">Search</button></form>' +
    '<div class="view-switch" role="group" aria-label="View mode"><a class="button' + (view === 'cards' ? ' primary' : '') + '" href="#/skills?' + buildSkillParams(params, { view: 'cards', cursor: null }) + '">Simple mode</a>' +
    '<a class="button' + (view === 'advanced' ? ' primary' : '') + '" href="#/skills?' + buildSkillParams(params, { view: 'advanced', cursor: null }) + '">Advanced mode</a></div></div>';

  root.innerHTML += '<div class="browse-switch" role="group" aria-label="Browse Skills">' +
    '<a class="browse-option' + (browse === 'usecase' ? ' active' : '') + '" href="#/skills?' + buildSkillParams(params, { browse: 'usecase', location: null, cursor: null }) + '">' +
    iconSvg('grid', 'browse-icon') + '<span><strong>Browse by use case</strong><small>Skill Control Plane automatically recognizes likely Skill types from names, descriptions and paths.</small></span></a>' +
    '<a class="browse-option' + (browse === 'location' ? ' active' : '') + '" href="#/skills?' + buildSkillParams(params, { browse: 'location', use_case: null, cursor: null }) + '">' +
    iconSvg('folder', 'browse-icon') + '<span><strong>Browse by location</strong><small>Choose where the Skill comes from. This is useful when the same machine has several Skill collections.</small></span></a></div>';

  if (browse === 'location') {
    const counts = await loadLocationCounts();
    root.innerHTML += locationGrid(counts, locationId);
  } else {
    root.innerHTML += '<div class="use-case-strip">' + USE_CASES.map(item =>
      '<a class="use-case-chip' + (useCaseId === item.id ? ' active' : '') + '" href="#/skills?browse=usecase&use_case=' + encodeURIComponent(item.id) + '&query=' + encodeURIComponent(item.query) + '">' +
      esc(useCaseLabel(item)) + '</a>'
    ).join('') + '</div>';
  }

  if (view === 'advanced') {
    const options = ['<option value="">All sources</option>'].concat(
      data.facets.source_classes.map(f => '<option value="' + esc(f.value) + '"' + (source === f.value ? ' selected' : '') + '>' + esc(f.value) + ' (' + f.count + ')</option>')
    ).join('');
    const categoryOptions = ['<option value="">All categories</option>'].concat(
      (data.facets.categories || []).map(item => '<option value="' + esc(item.category_id) + '"' + (category === item.category_id ? ' selected' : '') + '>' + esc(item.name) + ' (' + item.skill_count + ')</option>')
    ).join('');
    const tagOptions = ['<option value="">All tags</option>'].concat(
      (data.facets.tags || []).map(item => '<option value="' + esc(item.tag_id) + '"' + (tag === item.tag_id ? ' selected' : '') + '>' + esc(item.name) + ' (' + item.skill_count + ')</option>')
    ).join('');
    root.innerHTML += '<details class="advanced-filters" open><summary>Advanced filters</summary><div class="toolbar">' +
      '<div class="field"><label for="skillSource">Source</label><select id="skillSource">' + options + '</select></div>' +
      '<div class="field"><label for="skillCategory">Category</label><select id="skillCategory">' + categoryOptions + '</select></div>' +
      '<div class="field"><label for="skillTag">Tag</label><select id="skillTag">' + tagOptions + '</select></div>' +
      '<button class="button" id="applyAdvancedFilters">Apply advanced filters</button></div></details>';
  }

  if (!data.items.length) {
    root.innerHTML += '<div class="empty-state-card">' + iconSvg('search', 'empty-icon') + '<strong>No matching Skills</strong><p>Try a shorter, more general task such as “webpage”, “image”, “research”, or “video”.</p><a class="button" href="#/skills">Clear filters</a></div>';
  } else if (view === 'advanced') {
    const rows = data.items.map(item => {
      const org = [...(item.organization?.categories || []), ...(item.organization?.tags || [])]
        .slice(0, 4).map(value => badge(value.name)).join(' ');
      return '<tr><td><a class="row-link" href="#/skills/' + esc(item.skill_id) + '">' + esc(item.name) + '</a><span class="path" title="' + esc(item.path) + '">' + esc(item.path) + '</span></td><td>' + badge(item.source_class, 'accent') + '</td><td>' + mono(item.authority_tier) + '</td><td>' + item.variant_count + ' total · ' + item.nonselectable_variant_count + ' non-selectable</td><td>' + (org || '<span class="muted">—</span>') + '</td></tr>';
    }).join('');
    root.innerHTML += '<div class="table-wrap"><table><thead><tr><th scope="col">Skill</th><th scope="col">Selected source</th><th scope="col">Authority</th><th scope="col">Variants</th><th scope="col">Organization</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
  } else {
    root.innerHTML += '<div class="skill-card-grid">' + data.items.map(item => {
      const cases = inferUseCases(item);
      const origin = skillLocation(item.path);
      const capability = inferCapabilityKind(item);
      const description = beginnerSkillSummary(item, cases);
      return '<article class="skill-card"><div class="skill-card-top"><div class="skill-card-copy"><h2><a href="#/skills/' + esc(item.skill_id) + '">' + esc(item.name) + '</a></h2>' +
        '<p>' + esc(description) + '</p></div><span class="skill-version">' + esc(msg('skills.versionCount', { count: item.variant_count, label: item.variant_count === 1 ? 'version' : 'versions' })) + '</span></div>' +
        '<div class="skill-detection"><span>' + iconSvg('folder', 'skill-origin-icon') + '<small>Detected location</small><strong>' + esc(msg(origin.title)) + '</strong></span>' +
        '<span>' + iconSvg(capability.icon, 'skill-origin-icon') + '<small>Detected capability type</small><strong>' + esc(msg(capability.label)) + '</strong></span></div>' +
        '<div class="skill-use-cases">' + (cases.length ? cases.map(useCase => '<span class="use-case-chip static">' + esc(useCaseLabel(useCase)) + '</span>').join('') : '<span class="muted">Not categorized yet</span>') + '</div>' +
        '<div class="skill-card-actions"><a class="button primary" href="#/skills/' + esc(item.skill_id) + '">See what it can do</a>' +
        '<a class="text-action" href="#/skills/' + esc(item.skill_id) + '/technical">Technical details</a></div></article>';
    }).join('') + '</div>';
  }

  const limit = view === 'advanced' ? 50 : 24;
  const next = data.next_cursor == null ? '' : '<button class="button" id="skillsNext">Next</button>';
  const prev = cursor > 0 ? '<button class="button" id="skillsPrev">Previous</button>' : '';
  root.innerHTML += '<div class="pagination"><span>' + (data.total ? (cursor + 1) + '–' + Math.min(cursor + data.items.length, data.total) + ' of ' + data.total + ' results' : '0 results') + '</span><div class="actions">' + prev + next + '</div></div>';

  document.querySelector('#skillFilters').addEventListener('submit', event => {
    event.preventDefault();
    const nextParams = new URLSearchParams();
    const nextQuery = document.querySelector('#skillQuery').value.trim();
    if (nextQuery) nextParams.set('query', nextQuery);
    nextParams.set('browse', browse);
    if (view === 'advanced') nextParams.set('view', 'advanced');
    location.hash = '#/skills?' + nextParams.toString();
  });

  document.querySelector('#applyAdvancedFilters')?.addEventListener('click', () => {
    const nextParams = new URLSearchParams(params);
    const values = {
      source_class: document.querySelector('#skillSource').value,
      category_id: document.querySelector('#skillCategory').value,
      tag_id: document.querySelector('#skillTag').value
    };
    Object.entries(values).forEach(([key, value]) => value ? nextParams.set(key, value) : nextParams.delete(key));
    nextParams.delete('cursor');
    location.hash = '#/skills?' + nextParams.toString();
  });

  document.querySelector('#skillsNext')?.addEventListener('click', () => {
    params.set('cursor', String(data.next_cursor));
    location.hash = '#/skills?' + params.toString();
  });
  document.querySelector('#skillsPrev')?.addEventListener('click', () => {
    params.set('cursor', String(Math.max(0, cursor - limit)));
    location.hash = '#/skills?' + params.toString();
  });
}

function buildSkillParams(params, changes = {}) {
  const next = new URLSearchParams(params);
  Object.entries(changes).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') next.delete(key);
    else next.set(key, value);
  });
  const value = next.toString();
  return value ? value : '';
}

async function renderSkillDetail(skillId, tab) {
  const skill = await api('/api/skills/' + encodeURIComponent(skillId));
  const pageCases = inferUseCases(skill);
  const pageSummary = beginnerSkillSummary(skill, pageCases);
  const legacyTechnicalTabs = ['overview', 'variants', 'body', 'validation', 'relations'];
  const primaryTabs = ['about', 'organization', 'technical'];
  const allowedTabs = [...primaryTabs, ...legacyTechnicalTabs];
  if (!allowedTabs.includes(tab)) tab = 'about';
  const primaryTab = legacyTechnicalTabs.includes(tab) ? 'technical' : tab;
  const labels = { about: 'What it does', organization: 'Categories & tags', technical: 'Technical details' };
  const tabBar = primaryTabs.map(name =>
    '<a class="tab"' + (primaryTab === name ? ' aria-current="page"' : '') +
    ' href="#/skills/' + esc(skillId) + '/' + name + '">' + labels[name] + '</a>'
  ).join('');
  const showTechActions = primaryTab === 'technical';
  root.innerHTML = pageHead(
    skill.name,
    pageSummary,
    showTechActions
      ? '<button class="button" id="copyPath">Copy path</button><button class="button" id="openFolder">Open in Explorer</button>'
      : ''
  ) + '<nav class="tabs" aria-label="Skill sections">' + tabBar + '</nav><div id="skillTab"></div>';

  document.querySelector('#copyPath')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(skill.path);
      toast('Path copied.');
    } catch {
      toast('Clipboard unavailable.', true);
    }
  });
  document.querySelector('#openFolder')?.addEventListener('click', async () => {
    try {
      await api('/api/skills/' + encodeURIComponent(skillId) + '/open-folder', {
        method: 'POST',
        body: {}
      });
      toast('Opened canonical Skill folder.');
    } catch (error) {
      toast(error.message, true);
    }
  });

  const host = document.querySelector('#skillTab');
  if (tab === 'about') {
    const cases = pageCases;
    const rawDescription = skill.description && skill.description !== '>' ? String(skill.description).trim() : '';
    const description = beginnerSkillSummary(skill, cases);
    let analysis = analyzeSkillContent(skill, '');
    let capabilityBundle = null;
    try {
      capabilityBundle = await loadSkillCapabilityBundle(skillId, 2);
      analysis = capabilityBundle.analysis;
    } catch {
      try {
        const body = await api('/api/skills/' + encodeURIComponent(skillId) + '/body');
        analysis = analyzeSkillContent(skill, body.content || '');
      } catch {
        // Capability analysis is explanatory. Canonical metadata remains usable without it.
      }
    }
    const capability = analysis.kind;
    const origin = skillLocation(skill.path);
    const childSkillList = analysis.childSkills.length
      ? '<div class="capability-reference-group"><strong>Detected inner Skills</strong><div class="reference-chips">' +
        analysis.childSkills.map(value => '<span class="reference-chip">' + esc(value) + '</span>').join('') + '</div></div>'
      : '<p class="capability-note">No explicit child Skill names were detected. The Skill may still contain its own workflow instructions.</p>';
    const loadedFiles = (analysis.followedResourcePaths?.length
      ? analysis.followedResourcePaths
      : (analysis.internalFiles || []));
    const fileList = loadedFiles.length
      ? (() => {
          const featuredFiles = loadedFiles
            .filter(value => /(?:^|\/)(?:routes?|references|workflows?)\//i.test(value) || /(?:^|\/)(?:routes?\.md|EVOLUTION\.md)$/i.test(value))
            .slice(0, 6);
          const visibleFiles = featuredFiles.length ? featuredFiles : loadedFiles.slice(0, 4);
          return '<div class="capability-reference-group capability-bundle-summary"><strong>Capability bundle</strong><p class="capability-helper">' +
            esc(msg('Followed execution files')) + ': ' + loadedFiles.length +
            (analysis.resourceCount ? ' · ' + esc(msg('Discovered internal text files')) + ': ' + analysis.resourceCount : '') +
            '. ' + esc(msg('The Agent loads internal capability files instead of stopping at SKILL.md.')) +
            '</p><div class="reference-chips">' +
            visibleFiles.map(value => '<span class="reference-chip mono">' + esc(value) + '</span>').join('') + '</div>' +
            (loadedFiles.length > visibleFiles.length
              ? '<details class="internal-file-details"><summary>' + esc(msg('Show all internal files')) + '</summary>' +
                '<div class="reference-chips">' +
                loadedFiles.map(value => '<span class="reference-chip mono">' + esc(value) + '</span>').join('') +
                '</div></details>'
              : '') + '</div>';
        })()
      : '';
    const toolList = analysis.toolHints.length
      ? '<div class="capability-reference-group"><strong>Likely tools / MCP</strong><p class="capability-helper">Detected from the full Skill instructions. The Agent still decides at execution time which connections are actually needed.</p><div class="tool-hint-list">' +
        analysis.toolHints.map(tool => '<a class="tool-hint" href="#/tools">' + iconSvg(tool.icon, 'tool-hint-icon') + '<span>' + esc(tool.label) + '</span></a>').join('') + '</div></div>'
      : '';
    const sourceDescription = rawDescription && rawDescription !== description
      ? '<details class="source-description"><summary>Original description</summary>' +
        '<p>The original Skill description is preserved here for reference.</p><div>' + esc(rawDescription) + '</div></details>'
      : '';
    host.innerHTML =
      '<div class="beginner-detail-grid"><section class="purpose-card"><span class="eyebrow">What does this Skill do?</span>' +
      '<h2>' + esc(skill.name) + '</h2><p class="purpose-copy">' + esc(description) + '</p>' +
      '<div class="skill-use-cases">' +
      (cases.length ? cases.map(item => '<span class="use-case-chip static">' + esc(useCaseLabel(item)) + '</span>').join('') : '<span class="muted">No automatic use-case match yet</span>') +
      '</div>' + sourceDescription +
      '<section class="capability-explainer capability-' + esc(capability.label.toLowerCase().replace(/[^a-z]+/g, '-')) + '">' +
      '<div class="capability-explainer-head"><span class="capability-icon">' + iconSvg(capability.icon) + '</span><div><small>Detected capability type</small><strong>' +
      esc(msg(capability.label)) + '</strong><p>' + esc(msg(capability.hint)) + '</p></div></div>' +
      '<div class="capability-agent-rule"><strong>How the Agent should use it</strong><p>Read this Skill fully first. If it references routes, references, scripts or other Skills, follow those instructions recursively instead of stopping at this page.</p>' +
      (analysis.recursive ? '<p class="capability-emphasis">This Skill can be used as one complete Workflow step. Its internal steps stay intact unless the outer Workflow explicitly overrides them.</p>' : '') +
      '</div>' + childSkillList + fileList + toolList + capabilityRouteGraph(capabilityBundle) +
      '<a class="text-action capability-body-link" href="#/skills/' + esc(skillId) + '/body">' +
      esc(msg('View full Skill instructions')) + ' →</a></section>' +
      '<div class="purpose-actions"><a class="button primary" href="#/skills/' + esc(skillId) + '/organization">Organize</a>' +
      '<a class="button" href="#/skills/' + esc(skillId) + '/technical">View technical details</a></div></section>' +
      '<aside class="simple-facts"><h3>What you need to know first</h3>' +
      '<div><span>Skill name</span><strong>' + esc(skill.name) + '</strong></div>' +
      '<div><span>Detected capability type</span><strong>' + esc(msg(capability.label)) + '</strong></div>' +
      '<div><span>Detected location</span><strong>' + esc(msg(origin.title)) + '</strong></div>' +
      '<div><span>Available versions</span><strong>' + esc(String(skill.variant_count || (skill.variants || []).length || 1)) + '</strong></div>' +
      '<div><span>Current status</span><strong>' + (skill.selectable ? 'Available' : 'Unavailable') + '</strong></div>' +
      '<p>Source, authority, hashes and local paths are maintenance details. They do not need to block understanding what the Skill can do.</p></aside></div>';
    return;
  }

  if (tab === 'technical') {
    host.innerHTML =
      '<div class="tech-explainer">' + iconSvg('system', 'tech-icon') + '<div><strong>This is maintenance and troubleshooting information.</strong><span>If you only want to use the Skill, you usually do not need the details below.</span></div></div>' +
      '<div class="technical-link-grid">' +
      '<a class="technical-link" href="#/skills/' + esc(skillId) + '/overview">' + iconSvg('info', 'technical-link-icon') + '<span><strong>Basic technical information</strong><small>skill_id, source, authority, path and digest</small></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
      '<a class="technical-link" href="#/skills/' + esc(skillId) + '/variants">' + iconSvg('sources', 'technical-link-icon') + '<span><strong>Versions & sources</strong><small>Inspect the selected, alternate and historical versions</small></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
      '<a class="technical-link" href="#/skills/' + esc(skillId) + '/body">' + iconSvg('document', 'technical-link-icon') + '<span><strong>Raw SKILL.md</strong><small>Read the complete original Skill instructions</small></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
      '<a class="technical-link" href="#/skills/' + esc(skillId) + '/validation">' + iconSvg('check', 'technical-link-icon') + '<span><strong>Validation & evaluation</strong><small>Run Skill validation or evaluate it for a task</small></span>' + iconSvg('arrow', 'card-arrow') + '</a>' +
      '<a class="technical-link" href="#/skills/' + esc(skillId) + '/relations">' + iconSvg('activity', 'technical-link-icon') + '<span><strong>Relations & activity</strong><small>See which runs used this Skill</small></span>' + iconSvg('arrow', 'card-arrow') + '</a></div>';
    return;
  }

  if (tab === 'overview') {
    host.innerHTML =
      '<div class="detail-grid"><section class="card"><div class="card-head"><h2>Selected record</h2></div>' +
      '<div class="card-body"><dl class="kv"><dt>Name</dt><dd>' + esc(skill.name) +
      '</dd><dt>Skill ID</dt><dd>' + mono(skill.skill_id) +
      '</dd><dt>Selected variant</dt><dd>' + mono(skill.variant_id) +
      '</dd><dt>Source class</dt><dd>' + badge(skill.source_class, 'accent') +
      '</dd><dt>Authority tier</dt><dd>' + mono(skill.authority_tier) +
      '</dd><dt>Selectable</dt><dd>' + esc(String(!!skill.selectable)) +
      '</dd><dt>Digest</dt><dd>' + mono(skill.sha256) +
      '</dd><dt>Path</dt><dd class="mono">' + esc(skill.path) +
      '</dd></dl></div></section><section class="card"><div class="card-head"><h2>Description</h2></div>' +
      '<div class="card-body"><p>' + esc(skill.description || 'No description.') +
      '</p><p class="muted"><strong>Selected</strong> means chosen by the M01 authority resolver. ' +
      'It does not mean latest, best, or safe.</p></div></section></div>';
    return;
  }

  if (tab === 'variants') {
    const variants = skill.variants || [];
    const selected = variants.filter(row => row.variant_id === skill.variant_id);
    const alternate = variants.filter(row => row.variant_id !== skill.variant_id && row.selectable);
    const historical = variants.filter(row => !row.selectable);
    host.innerHTML =
      variantGroup('Selected canonical source', selected) +
      variantGroup('Alternate selectable variants', alternate) +
      variantGroup('Non-selectable / historical', historical);
    document.querySelectorAll('[data-open-variant]').forEach(button => {
      button.addEventListener('click', async () => {
        try {
          await api('/api/skills/' + encodeURIComponent(skillId) + '/open-folder', {
            method: 'POST',
            body: { variant_id: button.dataset.openVariant }
          });
          toast('Opened variant folder.');
        } catch (error) {
          toast(error.message, true);
        }
      });
    });
    return;
  }

  if (tab === 'body') {
    host.innerHTML =
      '<div class="loading"><div class="skeleton"></div><p>Loading selected SKILL.md on demand…</p></div>';
    try {
      const body = await api('/api/skills/' + encodeURIComponent(skillId) + '/body');
      host.innerHTML =
        '<section class="card"><div class="card-head"><h2>Selected SKILL.md</h2><span class="mono">' +
        esc(body.sha256) + '</span></div><div class="card-body"><p class="path" title="' +
        esc(body.path) + '">' + esc(body.path) +
        '</p><pre class="code-pane" tabindex="0">' + esc(body.content) + '</pre></div></section>';
    } catch (error) {
      host.innerHTML = '<div class="error-state">' + esc(error.message) + '</div>';
    }
    return;
  }

  if (tab === 'validation') {
    host.innerHTML =
      '<div class="detail-grid"><section class="card"><div class="card-head"><h2>Validate selected source</h2></div>' +
      '<div class="card-body"><p class="muted">Validation runs only when explicitly requested.</p>' +
      '<button class="button primary" id="validateSkill">Validate</button><div id="validationResult"></div></div></section>' +
      '<section class="card"><div class="card-head"><h2>Evaluate for a task</h2></div><div class="card-body">' +
      '<div class="field"><label for="evaluationQuery">Task query</label><input id="evaluationQuery" name="evaluation-query" autocomplete="off" placeholder="Describe the task…"></div>' +
      '<button class="button" id="evaluateSkill">Evaluate</button><div id="evaluationResult"></div></div></section></div>';
    document.querySelector('#validateSkill').addEventListener('click', async () => {
      const target = document.querySelector('#validationResult');
      try {
        const result = await api('/api/skills/' + encodeURIComponent(skillId) + '/validate', {
          method: 'POST',
          body: {}
        });
        target.innerHTML = '<pre class="code-pane">' + esc(pretty(result)) + '</pre>';
      } catch (error) {
        target.innerHTML = '<div class="error-state">' + esc(error.message) + '</div>';
      }
    });
    document.querySelector('#evaluateSkill').addEventListener('click', async () => {
      const target = document.querySelector('#evaluationResult');
      try {
        const result = await api('/api/skills/' + encodeURIComponent(skillId) + '/evaluate', {
          method: 'POST',
          body: { query: document.querySelector('#evaluationQuery').value }
        });
        target.innerHTML = '<pre class="code-pane">' + esc(pretty(result)) + '</pre>';
      } catch (error) {
        target.innerHTML = '<div class="error-state">' + esc(error.message) + '</div>';
      }
    });
    return;
  }

  if (tab === 'organization') {
    await renderSkillOrganization(host, skillId);
    return;
  }

  host.innerHTML =
    '<section class="card"><div class="card-head"><h2>Relations</h2></div><div class="card-body">' +
    '<p class="muted">Canonical skill_id is the stable relation key. Organization metadata never moves files.</p>' +
    '<a class="button" href="#/runs?skill_id=' + encodeURIComponent(skillId) + '">Runs using this Skill</a></div></section>';
}

function variantGroup(title, rows) {
  if (!rows.length) {
    return '<section class="card" style="margin-bottom:10px"><div class="card-head"><h2>' +
      esc(title) + '</h2></div><div class="card-body"><div class="empty">None</div></div></section>';
  }
  const body = rows.map(row =>
    '<tr><td>' + mono(row.variant_id) +
    '</td><td>' + badge(row.source_class, row.selectable ? 'accent' : '') +
    '</td><td>' + mono(row.authority_tier) +
    '</td><td>' + badge(row.selectable ? 'selectable' : 'non-selectable', row.selectable ? 'good' : '') +
    '</td><td><span class="path" title="' + esc(row.path) + '">' + esc(row.path) +
    '</span></td><td><button class="button" data-open-variant="' + esc(row.variant_id) +
    '">Open folder</button></td></tr>'
  ).join('');
  return '<section class="card" style="margin-bottom:10px"><div class="card-head"><h2>' +
    esc(title) + '</h2></div><div class="card-body"><div class="table-wrap"><table><thead><tr>' +
    '<th scope="col">Variant</th><th scope="col">Source</th><th scope="col">Authority</th>' +
    '<th scope="col">State</th><th scope="col">Path</th><th scope="col">Action</th></tr></thead><tbody>' +
    body + '</tbody></table></div></div></section>';
}

async function renderSkillOrganization(host, skillId) {
  const [organization, categories, tags] = await Promise.all([
    api('/api/skills/' + encodeURIComponent(skillId) + '/organization'),
    api('/api/categories'),
    api('/api/tags')
  ]);
  const currentCategories = new Set(organization.categories.map(row => row.category_id));
  const currentTags = new Set(organization.tags.map(row => row.tag_id));
  const categoryOptions = categories
    .filter(row => !currentCategories.has(row.category_id))
    .map(row => '<option value="' + esc(row.category_id) + '">' + esc(row.name) + '</option>')
    .join('');
  const tagOptions = tags
    .filter(row => !currentTags.has(row.tag_id))
    .map(row => '<option value="' + esc(row.tag_id) + '">' + esc(row.name) + '</option>')
    .join('');

  host.innerHTML =
    '<div class="risk-box"><strong>Metadata only.</strong> Category and tag changes do not change the Skill path.</div>' +
    '<div class="detail-grid" style="margin-top:10px"><section class="card"><div class="card-head"><h2>Categories</h2></div>' +
    '<div class="card-body"><div class="actions">' +
    (organization.categories.length
      ? organization.categories.map(row =>
          '<span class="badge">' + esc(row.name) +
          ' <button class="chip-remove" data-unbind-category="' + esc(row.category_id) +
          '" aria-label="Remove category">×</button></span>'
        ).join('')
      : '<span class="muted">No category metadata.</span>') +
    '</div><div class="toolbar" style="margin-top:10px"><label class="sr-only" for="categorySelect">Category</label><select id="categorySelect" name="category-select">' +
    '<option value="">Choose category…</option>' + categoryOptions +
    '</select><button class="button" id="bindCategory">Attach</button></div>' +
    '<div class="toolbar"><label class="sr-only" for="newCategoryName">New category name</label><input id="newCategoryName" name="new-category-name" autocomplete="off" placeholder="New category…">' +
    '<label class="sr-only" for="newCategoryDescription">Category description</label><input id="newCategoryDescription" name="new-category-description" autocomplete="off" placeholder="Description…">' +
    '<button class="button" id="createCategory">Create</button></div></div></section>' +
    '<section class="card"><div class="card-head"><h2>Tags</h2></div><div class="card-body"><div class="actions">' +
    (organization.tags.length
      ? organization.tags.map(row =>
          '<span class="badge">' + esc(row.name) +
          ' <button class="chip-remove" data-unbind-tag="' + esc(row.tag_id) +
          '" aria-label="Remove tag">×</button></span>'
        ).join('')
      : '<span class="muted">No tag metadata.</span>') +
    '</div><div class="toolbar" style="margin-top:10px"><label class="sr-only" for="tagSelect">Tag</label><select id="tagSelect" name="tag-select">' +
    '<option value="">Choose tag…</option>' + tagOptions +
    '</select><button class="button" id="bindTag">Attach</button></div>' +
    '<div class="toolbar"><label class="sr-only" for="newTagName">New tag name</label><input id="newTagName" name="new-tag-name" autocomplete="off" placeholder="New tag…">' +
    '<button class="button" id="createTag">Create</button></div></div></section></div>';

  const mutate = async (path, body) => {
    if (!canMutate()) return;
    try {
      await api(path, { method: 'POST', body });
      await refreshHealth();
      await renderSkillOrganization(host, skillId);
    } catch (error) {
      toast(error.message, true);
    }
  };

  document.querySelector('#bindCategory').addEventListener('click', () => {
    const categoryId = document.querySelector('#categorySelect').value;
    if (categoryId) {
      mutate('/api/skills/' + encodeURIComponent(skillId) + '/categories/bind', {
        category_id: categoryId
      });
    }
  });
  document.querySelector('#bindTag').addEventListener('click', () => {
    const tagId = document.querySelector('#tagSelect').value;
    if (tagId) {
      mutate('/api/skills/' + encodeURIComponent(skillId) + '/tags/bind', {
        tag_id: tagId
      });
    }
  });
  document.querySelectorAll('[data-unbind-category]').forEach(button => {
    button.addEventListener('click', () => {
      mutate('/api/skills/' + encodeURIComponent(skillId) + '/categories/unbind', {
        category_id: button.dataset.unbindCategory
      });
    });
  });
  document.querySelectorAll('[data-unbind-tag]').forEach(button => {
    button.addEventListener('click', () => {
      mutate('/api/skills/' + encodeURIComponent(skillId) + '/tags/unbind', {
        tag_id: button.dataset.unbindTag
      });
    });
  });
  document.querySelector('#createCategory').addEventListener('click', async () => {
    if (!canMutate()) return;
    try {
      await api('/api/categories', {
        method: 'POST',
        body: {
          name: document.querySelector('#newCategoryName').value,
          description: document.querySelector('#newCategoryDescription').value
        }
      });
      await renderSkillOrganization(host, skillId);
    } catch (error) {
      toast(error.message, true);
    }
  });
  document.querySelector('#createTag').addEventListener('click', async () => {
    if (!canMutate()) return;
    try {
      await api('/api/tags', {
        method: 'POST',
        body: { name: document.querySelector('#newTagName').value }
      });
      await renderSkillOrganization(host, skillId);
    } catch (error) {
      toast(error.message, true);
    }
  });
}


function parseJson(value, label = 'JSON') {
  try {
    return JSON.parse(value || '{}');
  } catch {
    throw new Error(label + ' is invalid JSON.');
  }
}

async function allWorkflowVersions(name = '') {
  const items = [];
  let cursor = 0;
  do {
    const params = new URLSearchParams({ limit: '200', include_archived: '1', cursor: String(cursor) });
    if (name) params.set('name', name);
    const page = await api('/api/workflows?' + params);
    items.push(...page.items);
    cursor = page.next_cursor;
  } while (cursor !== null && cursor !== undefined);
  return { items };
}

async function renderWorkflows() {
  const zh = state.locale === 'zh-CN';
  const showArchived = routeInfo().query.get('archived') === '1';
  const data = await allWorkflowVersions();
  const internalItems = data.items.filter(item => /^m\d{2}-/i.test(item.name || ''));
  const groups = new Map();
  data.items.filter(item => !/^m\d{2}-/i.test(item.name || '')).forEach(item => {
    const key = item.name.toLocaleLowerCase();
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  const families = [...groups.values()].map(items => items.sort((a, b) => b.version - a.version))
    .filter(items => showArchived || items.some(item => !item.archived));

  root.innerHTML = pageHead(
    'Automations',
    'A workflow is a reusable execution plan: describe each stage in normal language, then attach Skills only where that stage needs a specific capability.',
    '<a class="button primary" href="#/workflows/new">' + iconSvg('plus') + '<span>Create workflow</span></a>'
  );

  root.innerHTML += '<section class="workflow-user-list"><div class="section-head compact-head"><div><h2>Your workflows</h2><p>One entry per workflow; open version history when needed.</p></div><a class="button" href="#/workflows' + (showArchived ? '' : '?archived=1') + '">' + (showArchived ? 'Show active' : 'Show archived') + '</a></div>';
  if (!families.length) {
    root.innerHTML += '<div class="workflow-empty">' + iconSvg('automation', 'empty-icon') +
      '<strong>You have not created a workflow yet.</strong>' +
      '<p>Describe the stages of the job, attach the capabilities each stage needs, and Skill Control Plane will generate the Agent prompt for you.</p>' +
      '<a class="button primary" href="#/workflows/new">Create your first workflow</a></div>';
  } else {
    root.innerHTML += '<div class="workflow-family-list">' + families.map(items => {
      const current = items.find(item => !item.archived) || items[0];
      const history = items.filter(item => item.workflow_id !== current.workflow_id);
      return '<article class="workflow-family"><div class="workflow-family-main"><div><strong>' + esc(current.name) +
        '</strong><p>' + esc(current.description || 'Reusable workflow.') + '</p><small>' +
        (current.archived ? (zh ? '已归档' : 'Archived') : (zh ? '当前' : 'Current')) + ' · v' + current.version + ' · ' + items.length + (zh ? ' 个版本' : ' versions') + '</small></div>' +
        '<div class="workflow-family-actions"><a class="button primary" href="#/workflows/' + esc(current.workflow_id) + '">' + (zh ? '打开' : 'Open') + '</a>' +
        '<a class="button" href="#/workflows/' + esc(current.workflow_id) + '/new-version">' + (zh ? '新建版本' : 'New version') + '</a>' +
        '<button class="button" type="button" data-workflow-action="' + (current.archived ? 'restore' : 'archive') + '" data-workflow-id="' + esc(current.workflow_id) + '">' +
        (current.archived ? (zh ? '恢复' : 'Restore') : (zh ? '归档' : 'Archive')) + '</button></div></div>' +
        (history.length ? '<details><summary>' + (zh ? '版本历史' : 'Version history') + ' (' + history.length + ')</summary><div class="workflow-version-list">' +
          history.map(item => '<div class="workflow-version-row" data-archived="' + item.archived + '"><a href="#/workflows/' + esc(item.workflow_id) + '">v' + item.version + '</a><span>' +
          (item.archived ? (zh ? '已归档' : 'Archived') : (zh ? '可用' : 'Active')) + '</span><button class="button" type="button" data-workflow-action="' +
          (item.archived ? 'restore' : 'archive') + '" data-workflow-id="' + esc(item.workflow_id) + '">' +
          (item.archived ? (zh ? '恢复' : 'Restore') : (zh ? '归档' : 'Archive')) + '</button></div>').join('') + '</div></details>' : '') +
        (items.some(item => !item.archived) ? '<button class="button workflow-family-archive" type="button" data-family-archive="' + esc(current.name) + '">' + (zh ? '归档全部版本' : 'Archive all versions') + '</button>' : '') + '</article>';
    }).join('') + '</div>';
  }
  root.innerHTML += '</section>';
  root.innerHTML += '<details class="workflow-explainer"><summary>' + iconSvg('automation', 'workflow-explainer-icon') +
    '<span>How workflows work</span><span class="workflow-help-hint">Three steps from plan to Agent prompt</span></summary>' +
    '<div class="workflow-how-grid">' +
      '<div><span class="step-number">1</span><strong>1. Describe stages</strong><p>Write the goal, instructions and expected result for each stage.</p></div>' +
      '<div><span class="step-number">2</span><strong>2. Attach capabilities</strong><p>Bind a Skill only when that stage needs one; Router and Composite Skills keep their internal workflow.</p></div>' +
      '<div><span class="step-number">3</span><strong>3. Copy the Agent prompt</strong><p>Use the generated prompt in a new Agent conversation.</p></div>' +
    '</div></details>';
  if (internalItems.length) {
    root.innerHTML += '<details class="advanced-summary system-workflows"><summary>' + iconSvg('system', 'summary-icon') +
      '<span>System test workflows</span><span class="summary-count">' + internalItems.length + '</span></summary>' +
      '<div class="advanced-summary-body"><p>These are internal acceptance workflows kept for verification. Beginners normally do not need them.</p>' +
      '<div class="entity-list compact-entities">' + internalItems.map(item =>
        '<a class="entity-row" href="#/workflows/' + esc(item.workflow_id) + '">' +
          '<span class="entity-main"><strong>' + esc(item.name) + '</strong><small>' + esc(item.description || 'Stored workflow version.') +
          '<br><span class="mono">' + esc(item.workflow_id) + '</span></small></span>' +
          '<span class="entity-meta"><strong>v' + item.version + '</strong><span>' +
          item.stage_count + ' <span data-i18n="Stages">Stages</span></span></span>' +
          iconSvg('arrow', 'card-arrow') + '</a>'
      ).join('') + '</div></div></details>';
  }
  root.querySelectorAll('[data-workflow-action]').forEach(button => button.addEventListener('click', async () => {
    if (!canMutate()) return;
    const action = button.dataset.workflowAction;
    if (!confirm(action === 'archive' ? 'Archive this version? Existing Runs remain available.' : 'Restore this version?')) return;
    try {
      await api('/api/workflows/' + encodeURIComponent(button.dataset.workflowId) + '/' + action,
        { method: 'POST', body: {} });
      await renderWorkflows();
      toast(action === 'archive' ? 'Workflow archived.' : 'Workflow restored.');
    } catch (error) { toast(error.message, true); }
  }));
  root.querySelectorAll('[data-family-archive]').forEach(button => button.addEventListener('click', async () => {
    if (!canMutate() || !confirm(zh ? '归档此工作流的全部版本？已有 Run 仍可查看。' : 'Archive every version in this workflow? Existing Runs remain available.')) return;
    try {
      await api('/api/workflow-families/archive', { method: 'POST', body: { name: button.dataset.familyArchive } });
      await renderWorkflows();
    } catch (error) { toast(error.message, true); }
  }));
}

function workflowAgentPrompt(spec) {
  const name = String(spec.name || '').trim() || msg('Untitled workflow');
  const goal = String(spec.description || '').trim() || msg('Complete the requested task.');
  const steps = (spec.stages || []).map((stage, index) => {
    const skills = (stage.bindings || []).map(binding => binding.skill_id).filter(Boolean);
    const rawTask = String(stage.title || stage.key || '').trim();
    const task = /^step-\d+$/i.test(rawTask) ? '' : rawTask;
    const lines = [
      (index + 1) + '. ' + (task || msg('workflow.stepNumber', { number: index + 1 })),
      '   Skills: ' + (skills.length ? skills.join(', ') : msg('Choose a Skill first'))
    ];
    if (String(stage.description || '').trim()) {
      lines.push('   Purpose: ' + String(stage.description).trim());
    }
    if (String(stage.instructions || '').trim()) {
      lines.push('   Agent instructions: ' + String(stage.instructions).trim());
    }
    if (String(stage.expected_output || '').trim()) {
      lines.push('   Expected output: ' + String(stage.expected_output).trim());
    }
    if (String(stage.completion_criteria || '').trim()) {
      lines.push('   Completion criteria: ' + String(stage.completion_criteria).trim());
    }
    return lines.join('\n');
  });
  return [
    msg('workflow.prompt.header', { name }),
    msg('workflow.prompt.goal', { goal }),
    '',
    msg('workflow.prompt.rules'),
    '',
    steps.join('\n\n'),
    '',
    msg('workflow.prompt.finish')
  ].join('\n');
}

function workflowSpecForSubmit(spec) {
  return {
    ...spec,
    stages: (spec.stages || []).map((stage, index) => ({
      ...stage,
      key: String(stage.key || '').trim() || ('step-' + (index + 1)),
      bindings: (stage.bindings || []).filter(binding =>
        String(binding.skill_id || '').trim()
      )
    }))
  };
}

function workflowStageDisplayName(stage, index) {
  const raw = String(stage?.title || stage?.key || '').trim();
  return !raw || /^step-\d+$/i.test(raw)
    ? msg('workflow.stepNumber', { number: index + 1 })
    : raw;
}

function workflowPromptPanel(prompt, copyId, textareaId, sticky = false) {
  return '<section class="workflow-prompt-panel' + (sticky ? ' editor-preview' : '') + '">' +
    '<div class="workflow-prompt-head"><div>' + iconSvg('prompt', 'workflow-prompt-icon') +
    '<span><strong>Agent prompt</strong><small>This prompt tells the Agent what each stage means, which Skills provide capabilities, and how to execute them in order.</small></span></div>' +
    '<button class="button primary" id="' + esc(copyId) + '">Copy Agent prompt</button></div>' +
    '<div class="agent-execution-summary"><strong>What the Agent will do</strong>' +
      '<div class="agent-execution-grid">' +
        '<span>' + iconSvg('document', 'execution-icon') + '<b>Read each Skill fully</b></span>' +
        '<span>' + iconSvg('automation', 'execution-icon') + '<b>Keep nested workflows intact</b></span>' +
        '<span>' + iconSvg('system', 'execution-icon') + '<b>Use MCP/tools only when needed</b></span>' +
        '<span>' + iconSvg('activity', 'execution-icon') + '<b>Carry results forward step by step</b></span>' +
      '</div></div>' +
    '<details class="workflow-prompt-details"><summary>View full Agent prompt</summary>' +
      '<p>The full prompt is for the Agent. You normally do not need to edit it.</p>' +
      '<label class="sr-only" for="' + esc(textareaId) + '">Agent prompt</label>' +
      '<textarea class="workflow-prompt" id="' + esc(textareaId) + '" readonly>' + esc(prompt) + '</textarea></details>' +
    '</section>';
}

async function copyPlainText(value) {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}
async function renderWorkflowDetail(workflowId) {
  const workflow = await api('/api/workflows/' + encodeURIComponent(workflowId));
  const usage = await api('/api/workflows/' + encodeURIComponent(workflowId) + '/usage');
  const stageById = Object.fromEntries(workflow.stages.map(stage => [stage.stage_id, stage.key]));
  const workflowSkillIds = [...new Set(
    workflow.stages.flatMap(stage => stage.bindings.map(binding => binding.skill_id).filter(Boolean))
  )];
  const capabilityBySkill = {};
  await Promise.all(workflowSkillIds.map(async skillId => {
    try {
      const bundle = await loadSkillCapabilityBundle(skillId, 0);
      capabilityBySkill[skillId] = bundle.analysis;
    } catch {
      capabilityBySkill[skillId] = { kind: inferCapabilityKind({ skill_id: skillId }), childSkills: [], internalFiles: [], recursive: false };
    }
  }));
  const rows = workflow.stages.map(stage =>
    '<tr><td>' + stage.ordinal +
    '</td><td><strong>' + esc(stage.key) + '</strong></td><td>' +
    esc(stage.bindings.map(binding => binding.skill_id).join(', ') || '—') +
    '</td><td>' + stage.retry_limit +
    '</td><td>' + stage.loop_limit +
    '</td><td>' + esc(stage.fallback_stage_id ? stageById[stage.fallback_stage_id] || stage.fallback_stage_id : '—') +
    '</td></tr>'
  ).join('');
  const humanSteps = workflow.stages.map((stage, index) => {
    const skills = stage.bindings.map(binding => binding.skill_id).filter(Boolean);
    const skillTokens = skills.length
      ? skills.map(skillId => {
          const analysis = capabilityBySkill[skillId];
          const capability = analysis?.kind || CAPABILITY_KINDS.single;
          return '<span class="workflow-skill-token">' + iconSvg(capability.icon, 'workflow-skill-icon') +
            '<span><strong>' + esc(skillId) + '</strong><small>' + esc(msg(capability.label)) +
            (analysis?.recursive ? ' · ' + esc(msg('This Skill can be used as one complete Workflow step. Its internal steps stay intact unless the outer Workflow explicitly overrides them.')) : '') +
            '</small></span></span>';
        }).join('')
      : '<span class="muted">' + esc(msg('Choose a Skill first')) + '</span>';
    return '<div class="human-step"><span class="step-number">' + (index + 1) + '</span><div class="step-copy">' +
      '<strong>' + esc(workflowStageDisplayName(stage, index)) + '</strong>' +
      (stage.description ? '<p>' + esc(stage.description) + '</p>' : '') +
      (stage.instructions ? '<small><b>' + esc(msg('Instructions for the Agent')) + ':</b> ' + esc(stage.instructions) + '</small>' : '') +
      (stage.expected_output ? '<small><b>' + esc(msg('Expected output')) + ':</b> ' + esc(stage.expected_output) + '</small>' : '') +
      (stage.completion_criteria ? '<small><b>' + esc(msg('How do we know this step is done?')) + ':</b> ' + esc(stage.completion_criteria) + '</small>' : '') +
      '<div class="workflow-skill-tokens">' + skillTokens + '</div></div></div>';
  }).join('');
  const promptSpec = {
    name: workflow.name,
    version: workflow.version,
    description: workflow.description,
    stages: workflow.stages.map(stage => ({
      key: stage.key,
      title: stage.title,
      description: stage.description,
      instructions: stage.instructions,
      expected_output: stage.expected_output,
      completion_criteria: stage.completion_criteria,
      bindings: stage.bindings.map(binding => ({ skill_id: binding.skill_id }))
    }))
  };
  const agentPrompt = workflowAgentPrompt(promptSpec);

  root.innerHTML = pageHead(
    workflow.name + ' v' + workflow.version,
    (workflow.archived ? 'Archived · ' : '') + (workflow.description || 'Stored workflow version.'),
    '<a class="button primary" href="#/workflows/' + esc(workflowId) + '/new-version">Create new version</a>' +
    '<button class="button" type="button" id="workflowArchiveToggle">' + (workflow.archived ? 'Restore' : 'Archive') + '</button>' +
    (usage.can_delete ? '<button class="button danger" type="button" id="workflowDelete">Permanent delete</button>' : '')
  );
  root.innerHTML += '<p class="workflow-usage">' + usage.run_count + ' Runs · ' + usage.reference_count + ' references. ' +
    (usage.can_delete ? 'Permanent delete is available.' : 'Permanent delete requires archived, zero Run, and no references.') + '</p>';
  root.innerHTML += '<section class="automation-steps"><div class="section-head compact-head"><div><h2>Automation steps</h2><p>Each stage carries its own instructions; attached Skills provide the capabilities needed for that stage.</p></div></div>' +
    '<div class="human-steps">' + humanSteps + '</div></section>';
  root.innerHTML += workflowPromptPanel(agentPrompt, 'copyStoredWorkflowPrompt', 'storedWorkflowPrompt');
  root.innerHTML += '<details class="advanced-summary"><summary>' + iconSvg('advanced', 'summary-icon') +
    '<span>Technical stage details</span></summary><div class="advanced-summary-body"><div class="table-wrap"><table><thead><tr><th scope="col">#</th>' +
    '<th scope="col">Stage</th><th scope="col">Canonical Skills</th><th scope="col">Retry</th>' +
    '<th scope="col">Loop</th><th scope="col">Fallback stage</th></tr></thead><tbody>' +
    rows + '</tbody></table></div></div></details>';
  root.innerHTML += '<div class="detail-grid" style="margin-top:20px">' +
    '<section class="card"><div class="card-head"><h2>Deterministic plan preview</h2></div>' +
    '<div class="card-body"><div class="field"><label for="workflowPlanContext">Context JSON</label>' +
    '<textarea id="workflowPlanContext" name="workflow-plan-context">{}</textarea></div><button class="button" id="workflowPlan">Preview plan</button>' +
    '<div id="workflowPlanResult"></div></div></section>' +
    '<section class="card"><div class="card-head"><h2>Create planned Run</h2></div>' +
    '<div class="card-body"><p class="muted">Creates durable planned state; execution is started separately.</p>' +
    '<div class="field"><label for="workflowRunContext">Run context JSON</label><textarea id="workflowRunContext" name="workflow-run-context">{}</textarea></div>' +
    '<button class="button" id="workflowCreateRun" ' + (workflow.archived ? 'disabled title="Restore before creating a Run"' : '') + '>Create planned Run</button><div id="workflowRunResult"></div></div></section></div>';

  root.querySelector('#workflowArchiveToggle').addEventListener('click', async () => {
    if (!canMutate()) return;
    const action = workflow.archived ? 'restore' : 'archive';
    if (!confirm(action === 'archive' ? 'Archive this version? Existing Runs remain available.' : 'Restore this version?')) return;
    try {
      await api('/api/workflows/' + encodeURIComponent(workflowId) + '/' + action, { method: 'POST', body: {} });
      await renderWorkflowDetail(workflowId);
    } catch (error) { toast(error.message, true); }
  });
  root.querySelector('#workflowDelete')?.addEventListener('click', async () => {
    if (!canMutate()) return;
    if (prompt('Permanently delete this archived version? Enter its workflow name to confirm.', '') !== workflow.name) return;
    try {
      await api('/api/workflows/' + encodeURIComponent(workflowId) + '/delete', { method: 'POST', body: { confirm: true } });
      location.hash = '#/workflows?archived=1';
    } catch (error) { toast(error.message, true); }
  });

  document.querySelector('#copyStoredWorkflowPrompt').addEventListener('click', async () => {
    if (await copyPlainText(agentPrompt)) toast('Agent prompt copied.');
    else toast('Clipboard unavailable.', true);
  });
  document.querySelector('#workflowPlan').addEventListener('click', async () => {
    const target = document.querySelector('#workflowPlanResult');
    try {
      const result = await api('/api/workflows/' + encodeURIComponent(workflowId) + '/plan', {
        method: 'POST',
        body: { context: parseJson(document.querySelector('#workflowPlanContext').value, 'Context') }
      });
      target.innerHTML = '<pre class="code-pane">' + esc(pretty(result)) + '</pre>';
    } catch (error) {
      target.innerHTML = '<div class="error-state">' + esc(error.message) + '</div>';
    }
  });
  document.querySelector('#workflowCreateRun').addEventListener('click', async () => {
    if (!canMutate()) return;
    const target = document.querySelector('#workflowRunResult');
    try {
      const run = await api('/api/runs', {
        method: 'POST',
        body: {
          workflow_id: workflowId,
          context: parseJson(document.querySelector('#workflowRunContext').value, 'Run context')
        }
      });
      location.hash = '#/runs/' + encodeURIComponent(run.run_id);
    } catch (error) {
      target.innerHTML = '<div class="error-state">' + esc(error.message) + '</div>';
    }
  });
}

function blankStage(key = '') {
  return {
    key,
    title: '',
    description: '',
    instructions: '',
    expected_output: '',
    completion_criteria: '',
    condition: {},
    success_gate: {},
    failure_gate: {},
    retry_limit: 0,
    loop_limit: 0,
    loop_stop_condition: {},
    fallback_stage: null,
    bindings: [blankBinding('primary')]
  };
}

function blankBinding(key = 'primary') {
  return {
    key,
    skill_id: '',
    type: 'required',
    condition: {},
    fallback_skill_id: null
  };
}

async function renderWorkflowEditor(baseWorkflowId = null) {
  let spec = {
    name: '',
    version: 1,
    description: '',
    stages: [blankStage()]
  };
  if (baseWorkflowId) {
    const base = await api('/api/workflows/' + encodeURIComponent(baseWorkflowId));
    const versions = await allWorkflowVersions(base.name);
    const stageById = Object.fromEntries(base.stages.map(stage => [stage.stage_id, stage.key]));
    spec = {
      name: base.name,
      version: Math.max(...versions.items.filter(item => item.name.toLocaleLowerCase() === base.name.toLocaleLowerCase()).map(item => item.version), base.version) + 1,
      description: base.description,
      stages: base.stages.map(stage => ({
        key: stage.key,
        title: stage.title || '',
        description: stage.description || '',
        instructions: stage.instructions || '',
        expected_output: stage.expected_output || '',
        completion_criteria: stage.completion_criteria || '',
        condition: stage.condition || {},
        success_gate: stage.success_gate || {},
        failure_gate: stage.failure_gate || {},
        retry_limit: stage.retry_limit || 0,
        loop_limit: stage.loop_limit || 0,
        loop_stop_condition: stage.loop_stop_condition || {},
        fallback_stage: stage.fallback_stage_id ? stageById[stage.fallback_stage_id] || null : null,
        bindings: stage.bindings.map(binding => ({
          key: binding.key,
          skill_id: binding.skill_id,
          type: binding.type,
          condition: binding.condition || {},
          fallback_skill_id: binding.fallback_skill_id || null
        }))
      }))
    };
  }
  state.editor = spec;

  const syncFromDom = () => {
    spec.name = document.querySelector('#workflowName').value.trim();
    spec.version = Number(document.querySelector('#workflowVersion').value || 1);
    spec.description = document.querySelector('#workflowDescription').value;
    spec.stages = [...document.querySelectorAll('[data-editor-stage]')].map(card => ({
      key: card.querySelector('.stage-key').value.trim(),
      title: card.querySelector('.stage-title').value.trim(),
      description: card.querySelector('.stage-description').value.trim(),
      instructions: card.querySelector('.stage-instructions').value.trim(),
      expected_output: card.querySelector('.stage-expected-output').value.trim(),
      completion_criteria: card.querySelector('.stage-completion-criteria').value.trim(),
      condition: parseJson(card.querySelector('.stage-condition').value, 'Stage condition'),
      success_gate: parseJson(card.querySelector('.stage-success').value, 'Success gate'),
      failure_gate: parseJson(card.querySelector('.stage-failure').value, 'Failure gate'),
      retry_limit: Number(card.querySelector('.stage-retry').value || 0),
      loop_limit: Number(card.querySelector('.stage-loop').value || 0),
      loop_stop_condition: parseJson(card.querySelector('.stage-loop-stop').value, 'Loop stop condition'),
      fallback_stage: card.querySelector('.stage-fallback').value || null,
      bindings: [...card.querySelectorAll('[data-editor-binding]')].map(row => ({
        key: row.querySelector('.binding-key').value.trim(),
        skill_id: row.querySelector('.binding-skill').value.trim().toLowerCase(),
        type: row.querySelector('.binding-type').value,
        condition: parseJson(row.querySelector('.binding-condition').value, 'Binding condition'),
        fallback_skill_id: row.querySelector('.binding-fallback').value.trim().toLowerCase() || null
      }))
    }));
  };

  const draw = () => {
    const prompt = workflowAgentPrompt(spec);
    root.innerHTML = pageHead(
      baseWorkflowId ? 'Create new version' : 'Create an automation',
      'Describe what each stage should accomplish, then attach the Skills that give the Agent the capabilities it needs.'
    );
    root.innerHTML += '<div class="workflow-builder-layout"><section class="workflow-builder">' +
      '<section class="workflow-basics"><div class="field"><label for="workflowName">Workflow name</label>' +
      '<input id="workflowName" class="workflow-live-input" name="workflow-name" autocomplete="off" value="' + esc(spec.name) + '"' + (baseWorkflowId ? ' readonly' : '') + ' placeholder="Website launch workflow"></div>' +
      '<input id="workflowVersion" type="hidden" value="' + spec.version + '">' +
      '<div class="field"><label for="workflowDescription">What should the Agent finish?</label>' +
      '<textarea id="workflowDescription" class="workflow-live-input" name="workflow-description" placeholder="For example: research a product, design the page, implement it, then run browser QA.">' + esc(spec.description) + '</textarea></div>' +
      '<p class="workflow-version-note">' + iconSvg('history', 'note-icon') + '<span>Saved workflows remain versioned. Editing an existing workflow creates a new version.</span></p></section>' +
      '<section class="workflow-steps-section"><div class="section-head compact-head"><div><h2>Workflow steps</h2><p>Each step is a real instruction for the Agent. Skills provide capabilities; the text explains what this stage should actually do.</p></div>' +
      '<button class="button" id="addWorkflowStage">' + iconSvg('plus') + '<span>Add step</span></button></div>' +
      '<div class="workflow-step-list" id="workflowStages">' +
      spec.stages.map((stage, index) => workflowStageEditor(stage, index, spec.stages)).join('') + '</div></section>' +
      '<div class="workflow-save-bar"><button class="button" id="previewWorkflowVersion">Check workflow</button>' +
      '<button class="button primary" id="createWorkflowVersion">Save workflow</button></div><div id="workflowEditorResult"></div></section>' +
      workflowPromptPanel(prompt, 'copyWorkflowPrompt', 'workflowPromptPreview', true) + '</div>';

    const redraw = change => {
      try {
        syncFromDom();
        change();
        draw();
      } catch (error) {
        toast(error.message, true);
      }
    };

    const updatePrompt = () => {
      try {
        syncFromDom();
        document.querySelector('#workflowPromptPreview').value = workflowAgentPrompt(spec);
      } catch {
        // Invalid advanced JSON is surfaced by explicit validation/save, not while typing.
      }
    };

    document.querySelectorAll('.workflow-live-input').forEach(input => {
      input.addEventListener('input', updatePrompt);
      input.addEventListener('change', updatePrompt);
    });
    document.querySelector('#copyWorkflowPrompt').addEventListener('click', async () => {
      try {
        syncFromDom();
        const value = workflowAgentPrompt(spec);
        document.querySelector('#workflowPromptPreview').value = value;
        if (await copyPlainText(value)) toast('Agent prompt copied.');
        else toast('Clipboard unavailable.', true);
      } catch (error) {
        toast(error.message, true);
      }
    });
    document.querySelector('#addWorkflowStage').addEventListener('click', () => {
      redraw(() => spec.stages.push(blankStage()));
    });
    document.querySelectorAll('[data-stage-up]').forEach(button => {
      button.addEventListener('click', () => redraw(() => {
        const index = Number(button.dataset.stageUp);
        if (index > 0) [spec.stages[index - 1], spec.stages[index]] = [spec.stages[index], spec.stages[index - 1]];
      }));
    });
    document.querySelectorAll('[data-stage-down]').forEach(button => {
      button.addEventListener('click', () => redraw(() => {
        const index = Number(button.dataset.stageDown);
        if (index < spec.stages.length - 1) [spec.stages[index + 1], spec.stages[index]] = [spec.stages[index], spec.stages[index + 1]];
      }));
    });
    document.querySelectorAll('[data-stage-remove]').forEach(button => {
      button.addEventListener('click', () => redraw(() => {
        if (spec.stages.length <= 1) throw new Error('Workflow requires at least one stage.');
        spec.stages.splice(Number(button.dataset.stageRemove), 1);
      }));
    });
    document.querySelectorAll('[data-binding-add]').forEach(button => {
      button.addEventListener('click', () => redraw(() => {
        const stage = spec.stages[Number(button.dataset.bindingAdd)];
        stage.bindings.push(blankBinding('binding-' + (stage.bindings.length + 1)));
      }));
    });
    document.querySelectorAll('[data-binding-remove]').forEach(button => {
      button.addEventListener('click', () => redraw(() => {
        const stageIndex = Number(button.dataset.stageIndex);
        spec.stages[stageIndex].bindings.splice(Number(button.dataset.bindingRemove), 1);
      }));
    });
    document.querySelectorAll('.binding-skill,.binding-fallback').forEach(input => {
      input.addEventListener('input', () => {
        updateSkillSuggestions(input);
        updatePrompt();
      });
      if (input.classList.contains('binding-skill')) {
        input.addEventListener('change', () => updateSelectedSkillPreview(input));
        updateSelectedSkillPreview(input);
      }
    });
    document.querySelector('#previewWorkflowVersion').addEventListener('click', async () => {
      const target = document.querySelector('#workflowEditorResult');
      try {
        syncFromDom();
        const result = await api('/api/workflows/preview', {
          method: 'POST',
          body: { spec: workflowSpecForSubmit(spec) }
        });
        target.innerHTML = '<div class="success-state"><strong>Workflow looks valid.</strong><p>' +
          esc(result.plan?.stages?.length || spec.stages.length) + ' steps are ready to save.</p></div>';
      } catch (error) {
        target.innerHTML = '<div class="error-state">' + esc(error.message) + '</div>';
      }
    });
    document.querySelector('#createWorkflowVersion').addEventListener('click', async () => {
      if (!canMutate()) return;
      const target = document.querySelector('#workflowEditorResult');
      try {
        syncFromDom();
        const result = await api('/api/workflows', {
          method: 'POST',
          body: { spec: workflowSpecForSubmit(spec) }
        });
        location.hash = '#/workflows/' + encodeURIComponent(result.workflow_id);
      } catch (error) {
        target.innerHTML = '<div class="error-state">' + esc(error.message) +
          '<p>No automatic version increment or retry was performed.</p></div>';
      }
    });
  };

  draw();
}

function workflowStageEditor(stage, index, stages) {
  const fallbackOptions = ['<option value="">None</option>'].concat(
    stages.filter((_, itemIndex) => itemIndex !== index).map(item =>
      '<option value="' + esc(item.key) + '"' +
      (stage.fallback_stage === item.key ? ' selected' : '') + '>' + esc(item.key) + '</option>'
    )
  ).join('');
  const primary = stage.bindings[0] || blankBinding('primary');
  const extras = stage.bindings.slice(1).map((binding, extraIndex) =>
    workflowBindingEditor(binding, index, extraIndex + 1, false)
  ).join('');
  return '<article class="workflow-step-card" data-editor-stage="' + index + '">' +
    '<header class="workflow-step-head"><span class="step-number">' + (index + 1) + '</span><div><strong>' + esc(msg('workflow.stepNumber', { number: index + 1 })) +
    '</strong><small>' + esc(stage.title || stage.key || msg('Describe this step')) + '</small></div><div class="step-actions">' +
    '<button class="icon-button" data-stage-up="' + index + '" aria-label="Move up">' + iconSvg('up') + '</button>' +
    '<button class="icon-button" data-stage-down="' + index + '" aria-label="Move down">' + iconSvg('down') + '</button>' +
    '<button class="icon-button danger-icon" data-stage-remove="' + index + '" aria-label="Delete step">' + iconSvg('trash') + '</button></div></header>' +
    '<div class="workflow-step-main"><div class="field"><label for="stage-title-' + index + '">Step title</label>' +
    '<input id="stage-title-' + index + '" class="stage-title workflow-live-input" name="stage-title-' + index + '" autocomplete="off" value="' +
    esc(stage.title || '') + '" placeholder="Research the problem"></div>' +
    '<div class="field"><label for="stage-description-' + index + '">What should happen in this step?</label>' +
    '<textarea id="stage-description-' + index + '" class="stage-description workflow-live-input" name="stage-description-' + index + '" placeholder="Describe the purpose of this stage in normal language.">' +
    esc(stage.description || '') + '</textarea></div>' +
    '<div class="field"><label for="stage-instructions-' + index + '">Instructions for the Agent</label>' +
    '<textarea id="stage-instructions-' + index + '" class="stage-instructions workflow-live-input" name="stage-instructions-' + index + '" placeholder="For example: inspect existing work first, compare alternatives, then implement only the selected approach.">' +
    esc(stage.instructions || '') + '</textarea></div>' +
    '<div class="field"><label for="stage-output-' + index + '">Expected output</label>' +
    '<input id="stage-output-' + index + '" class="stage-expected-output workflow-live-input" name="stage-output-' + index + '" autocomplete="off" value="' +
    esc(stage.expected_output || '') + '" placeholder="For example: research summary + chosen approach"></div>' +
    '<div class="field"><label for="stage-done-' + index + '">How do we know this step is done?</label>' +
    '<input id="stage-done-' + index + '" class="stage-completion-criteria workflow-live-input" name="stage-done-' + index + '" autocomplete="off" value="' +
    esc(stage.completion_criteria || '') + '" placeholder="For example: evidence is recorded and no unresolved blockers remain"></div>' +
    workflowBindingEditor(primary, index, 0, true) + '</div>' +
    '<details class="step-advanced"><summary>' + iconSvg('advanced', 'summary-icon') + '<span>Advanced step settings</span></summary>' +
    '<div class="step-advanced-body"><p class="muted">Retries, conditions, fallback and extra bindings are optional. Beginners can leave them unchanged.</p>' +
    '<div class="form-grid"><div class="field"><label for="stage-key-' + index + '">Internal step key</label>' +
    '<input id="stage-key-' + index + '" class="stage-key workflow-live-input" name="stage-key-' + index + '" autocomplete="off" value="' +
    esc(stage.key) + '" placeholder="research"></div>' +
    '<div class="field"><label for="stage-fallback-' + index + '">Fallback stage</label><select id="stage-fallback-' + index + '" class="stage-fallback" name="stage-fallback-' + index + '">' + fallbackOptions + '</select></div>' +
    '<div class="field"><label for="stage-retry-' + index + '">Retry limit</label><input id="stage-retry-' + index + '" class="stage-retry" name="stage-retry-' + index + '" type="number" min="0" value="' +
    stage.retry_limit + '"></div><div class="field"><label for="stage-loop-' + index + '">Loop limit</label><input id="stage-loop-' + index + '" class="stage-loop" name="stage-loop-' + index + '" type="number" min="0" value="' +
    stage.loop_limit + '"></div><div class="field full"><label for="stage-condition-' + index + '">Condition JSON</label><textarea id="stage-condition-' + index + '" class="stage-condition" name="stage-condition-' + index + '">' +
    esc(pretty(stage.condition)) + '</textarea></div><div class="field full"><label for="stage-success-' + index + '">Success gate JSON</label><textarea id="stage-success-' + index + '" class="stage-success" name="stage-success-' + index + '">' +
    esc(pretty(stage.success_gate)) + '</textarea></div><div class="field full"><label for="stage-failure-' + index + '">Failure gate JSON</label><textarea id="stage-failure-' + index + '" class="stage-failure" name="stage-failure-' + index + '">' +
    esc(pretty(stage.failure_gate)) + '</textarea></div><div class="field full"><label for="stage-loop-stop-' + index + '">Loop stop condition JSON</label><textarea id="stage-loop-stop-' + index + '" class="stage-loop-stop" name="stage-loop-stop-' + index + '">' +
    esc(pretty(stage.loop_stop_condition)) + '</textarea></div></div>' +
    '<div class="extra-bindings"><div class="extra-bindings-head"><strong>Extra Skill bindings</strong><button class="button" data-binding-add="' + index + '">' + iconSvg('plus') + '<span>Add another Skill to this step</span></button></div>' +
    (extras || '<p class="muted">None</p>') + '</div></div></details></article>';
}

function workflowBindingEditor(binding, stageIndex, bindingIndex, primary = false) {
  const listId = 'skill-options-' + stageIndex + '-' + bindingIndex;
  const fieldPrefix = 'binding-' + stageIndex + '-' + bindingIndex;
  if (primary) {
    return '<div class="primary-binding" data-editor-binding="' + bindingIndex + '">' +
      '<input type="hidden" class="binding-key" name="' + fieldPrefix + '-key" value="' + esc(binding.key || 'primary') + '">' +
      '<div class="field"><label for="' + fieldPrefix + '-skill">Main Skill (optional)</label><div class="skill-picker">' +
      iconSvg('search', 'search-icon') + '<input id="' + fieldPrefix + '-skill" class="binding-skill workflow-live-input" name="' + fieldPrefix +
      '-skill" autocomplete="off" list="' + listId + '" value="' + esc(binding.skill_id) + '" placeholder="Leave empty for a text-only stage, or search a Skill…">' +
      '<datalist id="' + listId + '"></datalist></div><div class="selected-skill-preview" data-selected-skill-preview></div></div>' +
      '<details class="binding-technical"><summary>This Skill\'s advanced options</summary><div class="binding-technical-body">' +
      '<div class="field"><label>Binding type</label><select class="binding-type" name="' + fieldPrefix + '-type" aria-label="Binding type"><option value="required"' + (binding.type === 'required' ? ' selected' : '') +
      '>required</option><option value="optional"' + (binding.type === 'optional' ? ' selected' : '') +
      '>optional</option><option value="conditional"' + (binding.type === 'conditional' ? ' selected' : '') +
      '>conditional</option></select></div>' +
      '<div class="field"><label>When to use it</label><input class="binding-condition" name="' + fieldPrefix + '-condition" value="' +
      esc(JSON.stringify(binding.condition || {})) + '" placeholder="{}"></div>' +
      '<div class="field"><label>Fallback Skill</label><input class="binding-fallback" name="' + fieldPrefix + '-fallback" autocomplete="off" value="' +
      esc(binding.fallback_skill_id || '') + '" placeholder="optional fallback skill_id"></div></div></details></div>';
  }
  return '<div class="binding binding-editor friendly-binding" data-editor-binding="' + bindingIndex + '">' +
    '<div class="field"><label>Binding name</label><input class="binding-key" name="' + fieldPrefix + '-key" autocomplete="off" value="' + esc(binding.key) + '"></div>' +
    '<div class="field"><label>Main Skill</label><input class="binding-skill" name="' + fieldPrefix + '-skill" autocomplete="off" list="' + listId + '" value="' + esc(binding.skill_id) +
    '" placeholder="Search a Skill name or ID…"><datalist id="' + listId + '"></datalist></div>' +
    '<div class="field"><label>Binding type</label><select class="binding-type" name="' + fieldPrefix + '-type" aria-label="Binding type"><option value="required"' + (binding.type === 'required' ? ' selected' : '') +
    '>required</option><option value="optional"' + (binding.type === 'optional' ? ' selected' : '') +
    '>optional</option><option value="conditional"' + (binding.type === 'conditional' ? ' selected' : '') +
    '>conditional</option></select></div><div class="field"><label>When to use it</label><input class="binding-condition" name="' + fieldPrefix +
    '-condition" value="' + esc(JSON.stringify(binding.condition || {})) + '" placeholder="{}"></div>' +
    '<div class="field"><label>Fallback Skill</label><input class="binding-fallback" name="' + fieldPrefix + '-fallback" autocomplete="off" value="' +
    esc(binding.fallback_skill_id || '') + '"></div><button class="button danger" data-stage-index="' + stageIndex +
    '" data-binding-remove="' + bindingIndex + '">Remove</button></div>';
}

async function updateSkillSuggestions(input) {
  const query = input.value.trim();
  if (query.length < 2) return;
  try {
    const data = await api('/api/skills?query=' + encodeURIComponent(query) + '&limit=8');
    const listId = input.getAttribute('list');
    if (!listId) return;
    const list = document.getElementById(listId);
    if (list) {
      list.innerHTML = data.items.map(item =>
        '<option value="' + esc(item.skill_id) + '">' + esc(item.name) + '</option>'
      ).join('');
    }
  } catch {
    // Suggestions are convenience only; validation remains server-authoritative.
  }
}

async function updateSelectedSkillPreview(input) {
  const host = input.closest('[data-editor-binding]')?.querySelector('[data-selected-skill-preview]');
  if (!host) return;
  const skillId = input.value.trim().toLowerCase();
  if (!skillId) {
    host.innerHTML = '<span class="muted">Choose a Skill from the suggestions to see what kind of capability it is.</span>';
    return;
  }
  host.innerHTML = '<span class="muted">Loading Skill…</span>';
  try {
    const loaded = await loadSkillCapabilityBundle(skillId, 1);
    const skill = loaded.skill;
    const analysis = loaded.analysis;
    const capability = analysis.kind;
    const cases = inferUseCases(skill);
    host.innerHTML = '<div class="selected-skill-card">' +
      '<span class="selected-skill-icon">' + iconSvg(capability.icon) + '</span>' +
      '<div><small>Selected Skill</small><strong>' + esc(skill.name) + '</strong>' +
      '<p>' + esc(beginnerSkillSummary(skill, cases)) + '</p>' +
      '<div class="selected-skill-meta"><span>' + esc(msg(capability.label)) + '</span>' +
      (analysis.resourceCount ? '<span>' + analysis.resourceCount + ' ' + esc(msg('Loaded internal files')) + '</span>' : '') +
      (analysis.recursive ? '<span class="nested-capability-note">This is a composite capability. Its internal workflow will be kept intact.</span>' : '') +
      '</div></div></div>';
  } catch {
    host.innerHTML = '<span class="muted">Choose a Skill from the suggestions to see what kind of capability it is.</span>';
  }
}


async function renderRuns(params) {
  const url = new URL('/api/runs', location.origin);
  url.searchParams.set('limit', '60');
  for (const key of ['status', 'workflow_id', 'skill_id', 'cursor']) {
    const value = params.get(key);
    if (value) url.searchParams.set(key, value);
  }
  const [data, workflows] = await Promise.all([
    api(url.pathname + url.search),
    api('/api/workflows?limit=200')
  ]);
  root.innerHTML = pageHead(
    'Activity',
    'See what automations did, whether they finished, where they stopped, and which Skills they used.'
  );
  const workflowOptions = ['<option value="">All workflows</option>'].concat(
    workflows.items.map(item =>
      '<option value="' + esc(item.workflow_id) + '"' +
      (params.get('workflow_id') === item.workflow_id ? ' selected' : '') + '>' +
      esc(item.name) + ' v' + item.version + '</option>'
    )
  ).join('');
  root.innerHTML += '<form class="toolbar surface-toolbar" id="runFilters"><div class="field"><label for="runStatus">Status</label>' +
    '<select id="runStatus" name="run-status"><option value="">All statuses</option>' +
    ['planned', 'active', 'blocked', 'completed', 'failed'].map(value =>
      '<option value="' + value + '"' + (params.get('status') === value ? ' selected' : '') + '>' +
      value + '</option>'
    ).join('') + '</select></div><div class="field"><label for="runWorkflow">Workflow</label><select id="runWorkflow" name="run-workflow">' +
    workflowOptions + '</select></div><div class="field grow"><label for="runSkill">Canonical Skill</label>' +
    '<input id="runSkill" name="run-skill" autocomplete="off" value="' + esc(params.get('skill_id') || '') +
    '" placeholder="skill_id…"></div><button class="button" type="submit">Apply</button></form>';

  if (!data.items.length) {
    root.innerHTML += '<div class="empty">No runs match the current filters.</div>';
  } else {
    root.innerHTML += '<div class="entity-list activity-entity-list">' + data.items.map(item => {
      const task = item.task || item.workflow_name || item.run_id;
      return '<a class="entity-row" href="#/runs/' + esc(item.run_id) + '">' +
        '<span class="entity-main"><strong>' + esc(task) + '</strong><small>' + esc(item.workflow_name) + ' v' + item.workflow_version +
        ' · <span class="mono">' + esc(item.run_id) + '</span></small></span>' +
        '<span class="entity-meta"><strong>' + badge(item.status === 'active' ? 'running' : item.status, statusTone(item.status)) + '</strong><span><span data-i18n="Current step">Current step</span>: ' +
        esc(item.current_stage_key || '—') + '</span></span>' +
        '<span class="entity-meta"><strong data-i18n="Updated at">Updated at</strong><span>' + esc(item.updated_at) + '</span></span>' +
        iconSvg('arrow', 'card-arrow') + '</a>';
    }).join('') + '</div>';
  }
  const cursor = Number(data.cursor || 0);
  const next = data.next_cursor == null ? '' : '<button class="button" id="runsNext">Next</button>';
  const prev = cursor > 0 ? '<button class="button" id="runsPrev">Previous</button>' : '';
  root.innerHTML += '<div class="pagination"><span>' +
    (data.total ? (cursor + 1) + '–' + Math.min(cursor + data.items.length, data.total) + ' of ' + data.total + ' results' : '0 results') +
    '</span><div class="actions">' + prev + next + '</div></div>';

  document.querySelector('#runFilters').addEventListener('submit', event => {
    event.preventDefault();
    const nextParams = new URLSearchParams();
    const status = document.querySelector('#runStatus').value;
    const workflowId = document.querySelector('#runWorkflow').value;
    const skillId = document.querySelector('#runSkill').value.trim();
    if (status) nextParams.set('status', status);
    if (workflowId) nextParams.set('workflow_id', workflowId);
    if (skillId) nextParams.set('skill_id', skillId);
    location.hash = '#/runs?' + nextParams.toString();
  });
  document.querySelector('#runsNext')?.addEventListener('click', () => {
    params.set('cursor', String(data.next_cursor));
    location.hash = '#/runs?' + params.toString();
  });
  document.querySelector('#runsPrev')?.addEventListener('click', () => {
    params.set('cursor', String(Math.max(0, cursor - 60)));
    location.hash = '#/runs?' + params.toString();
  });
}

function runDraft() {
  return {
    blockReason: document.querySelector('#runBlockReason')?.value || '',
    evidenceKind: document.querySelector('#runEvidenceKind')?.value || 'operator',
    evidenceKey: document.querySelector('#runEvidenceKey')?.value || '',
    evidencePayload: document.querySelector('#runEvidencePayload')?.value || '{}',
    gateResult: document.querySelector('#runGateResult')?.value || '{"passed":true}'
  };
}

function evidenceComposer(draft = {}) {
  return '<section class="card"><div class="card-head"><h3>Add evidence</h3></div><div class="card-body">' +
    '<div class="form-grid"><div class="field"><label for="runEvidenceKind">Kind</label><input id="runEvidenceKind" name="run-evidence-kind" autocomplete="off" value="' +
    esc(draft.evidenceKind || 'operator') + '"></div><div class="field"><label for="runEvidenceKey">Evidence key (optional)</label>' +
    '<input id="runEvidenceKey" name="run-evidence-key" autocomplete="off" value="' + esc(draft.evidenceKey || '') + '"></div>' +
    '<div class="field full"><label for="runEvidencePayload">Payload JSON</label><textarea id="runEvidencePayload" name="run-evidence-payload">' +
    esc(draft.evidencePayload || '{}') + '</textarea></div></div>' +
    '<button class="button" id="runAddEvidence">Add evidence</button></div></section>';
}

async function renderRunDetail(runId, draft = {}, conflictMessage = '') {
  const run = await api('/api/runs/' + encodeURIComponent(runId));
  const workflow = await api('/api/workflows/' + encodeURIComponent(run.workflow_id));
  const stageById = Object.fromEntries(workflow.stages.map(stage => [stage.stage_id, stage.key]));
  const current = run.stages.find(stage => stage.stage_id === run.current_stage_id);
  const statusLabel = run.status === 'active' ? 'running' : run.status;

  const taskLabel = run.task || run.context?.task || workflow.name;
  root.innerHTML = pageHead(
    taskLabel,
    workflow.name + ' v' + workflow.version + ' · ' + run.run_id,
    badge(statusLabel, statusTone(run.status))
  );
  if (conflictMessage) {
    root.innerHTML += '<div class="error-state"><strong>Server rejected the previous action.</strong>' +
      '<p>' + esc(conflictMessage) + '</p><p>Authoritative state was refreshed. No automatic retry occurred.</p></div>';
  }
  if (run.status === 'blocked') {
    root.innerHTML += '<div class="risk-box"><strong>Blocked.</strong> ' +
      esc(current?.blocked_reason || 'No reason stored.') + '</div>';
  }

  const stageRows = run.stages.map(stage =>
    '<tr><td>' + stage.ordinal +
    '</td><td>' + esc(stageById[stage.stage_id] || stage.stage_id) +
    '</td><td>' + badge(stage.status, statusTone(stage.status)) +
    '</td><td>' + stage.retry_count +
    '</td><td>' + stage.loop_count +
    '</td><td>' + esc(stage.blocked_reason || '—') + '</td></tr>'
  ).join('');
  const humanStages = run.stages.map(stage =>
    '<div class="human-step"><span class="step-number">' + stage.ordinal + '</span><div class="step-copy"><strong>' +
      esc(stageById[stage.stage_id] || stage.stage_id) + '</strong><p>' +
      badge(stage.status, statusTone(stage.status)) +
      (stage.blocked_reason ? ' · ' + esc(stage.blocked_reason) : '') + '</p></div></div>'
  ).join('');
  root.innerHTML += '<section class="run-summary-strip"><div>' + iconSvg('activity', 'status-icon') +
    '<span><small data-i18n="Current step">Current step</small><strong>' +
    esc(current ? stageById[current.stage_id] || current.stage_id : '—') + '</strong></span></div><div><small>Status</small>' +
    badge(statusLabel, statusTone(run.status)) + '</div></section>';
  root.innerHTML += '<section class="automation-steps"><div class="section-head compact-head"><div><h2>Automation steps</h2></div></div>' +
    '<div class="human-steps">' + humanStages + '</div></section>';
  root.innerHTML += '<details class="advanced-summary run-technical"><summary>' + iconSvg('advanced', 'summary-icon') +
    '<span>Technical run details</span></summary><div class="advanced-summary-body">' +
    '<div class="detail-grid"><section class="card"><div class="card-head"><h2>Run context</h2></div><div class="card-body"><pre class="code-pane">' +
    esc(pretty(run.context)) + '</pre></div></section><section class="card"><div class="card-head"><h2>Current stage</h2></div>' +
    '<div class="card-body"><dl class="kv"><dt>Status</dt><dd>' + badge(statusLabel, statusTone(run.status)) +
    '</dd><dt>Stage</dt><dd>' + esc(current ? stageById[current.stage_id] || current.stage_id : '—') +
    '</dd><dt>Resolved bindings</dt><dd>' + esc(current ? pretty(current.resolved_bindings) : '—') +
    '</dd></dl></div></section></div>' +
    '<section class="card" style="margin-top:14px"><div class="card-head"><h2>Stage state</h2></div>' +
    '<div class="card-body"><div class="table-wrap"><table><thead><tr><th scope="col">#</th><th scope="col">Stage</th>' +
    '<th scope="col">Status</th><th scope="col">Retries</th><th scope="col">Loops</th><th scope="col">Blocked reason</th>' +
    '</tr></thead><tbody>' + stageRows + '</tbody></table></div></div></section></div></details>';

  root.innerHTML += '<section class="card" style="margin-top:10px"><div class="card-head"><h2>Legal actions</h2></div>' +
    '<div class="card-body" id="runActions"></div></section>';
  const actions = document.querySelector('#runActions');
  if (run.status === 'planned') {
    actions.innerHTML = '<button class="button primary" id="runStart">Start Run</button>';
  } else if (run.status === 'active') {
    actions.innerHTML =
      '<div class="detail-grid"><section class="card"><div class="card-head"><h3>Block current stage</h3></div>' +
      '<div class="card-body"><div class="field"><label for="runBlockReason">Explicit reason</label><input id="runBlockReason" name="run-block-reason" autocomplete="off" value="' +
      esc(draft.blockReason || '') + '"></div><button class="button" id="runBlock">Block</button></div></section>' +
      '<section class="card"><div class="card-head"><h3>Succeed current stage</h3></div><div class="card-body">' +
      '<div class="field"><label for="runGateResult">Gate result JSON</label><textarea id="runGateResult" name="run-gate-result">' +
      esc(draft.gateResult || '{"passed":true}') + '</textarea></div>' +
      '<button class="button primary" id="runSucceed">Succeed</button></div></section></div>' +
      evidenceComposer(draft);
  } else if (run.status === 'blocked') {
    actions.innerHTML = evidenceComposer(draft) +
      '<button class="button primary" id="runResume" style="margin-top:8px">Resume after evidence</button>';
  } else {
    actions.innerHTML = '<p class="muted">This Run is terminal. No state mutation control is exposed.</p>' +
      '<pre class="code-pane">' + esc(pretty(run.terminal_result)) + '</pre>';
  }

  const evidenceTimeline = run.evidence.length
    ? '<div class="timeline">' + run.evidence.map(item =>
        '<div class="timeline-item"><h3>' + esc(item.kind) + ' ' + mono(item.evidence_id) +
        '</h3><p>' + esc(item.created_at) + '</p><pre class="code-pane">' +
        esc(pretty(item.payload)) + '</pre></div>'
      ).join('') + '</div>'
    : '<div class="empty">No evidence yet.</div>';
  const auditTimeline = run.audit.length
    ? '<div class="timeline">' + run.audit.map(item =>
        '<div class="timeline-item"><h3>' + esc(item.action) + '</h3><p>' +
        esc(item.created_at) + ' · ' + esc(item.entity_type) + '</p><p class="mono">' +
        esc(JSON.stringify(item.payload)) + '</p></div>'
      ).join('') + '</div>'
    : '<div class="empty">No audit events.</div>';
  root.innerHTML += '<div class="detail-grid" style="margin-top:10px"><section class="card"><div class="card-head"><h2>Evidence</h2></div>' +
    '<div class="card-body">' + evidenceTimeline + '</div></section><section class="card"><div class="card-head"><h2>Audit</h2></div>' +
    '<div class="card-body">' + auditTimeline + '</div></section></div>';

  bindRunActions(runId);
}

function bindRunActions(runId) {
  const mutate = async (action, body = {}) => {
    if (!canMutate()) return;
    const draft = runDraft();
    try {
      await api('/api/runs/' + encodeURIComponent(runId) + '/' + action, {
        method: 'POST',
        body
      });
      await refreshHealth();
      await renderRunDetail(runId);
    } catch (error) {
      await renderRunDetail(runId, draft, error.message);
    }
  };
  document.querySelector('#runStart')?.addEventListener('click', () => mutate('start'));
  document.querySelector('#runBlock')?.addEventListener('click', () => {
    mutate('block', { reason: document.querySelector('#runBlockReason').value });
  });
  document.querySelector('#runAddEvidence')?.addEventListener('click', () => {
    try {
      const key = document.querySelector('#runEvidenceKey').value.trim();
      const body = {
        kind: document.querySelector('#runEvidenceKind').value,
        payload: parseJson(document.querySelector('#runEvidencePayload').value, 'Evidence payload')
      };
      if (key) body.evidence_key = key;
      mutate('evidence', body);
    } catch (error) {
      toast(error.message, true);
    }
  });
  document.querySelector('#runResume')?.addEventListener('click', () => mutate('resume'));
  document.querySelector('#runSucceed')?.addEventListener('click', () => {
    try {
      mutate('succeed', {
        gate_result: parseJson(document.querySelector('#runGateResult').value, 'Gate result')
      });
    } catch (error) {
      toast(error.message, true);
    }
  });
}


async function renderAgentTools() {
  const toolCards = [
    {
      icon: 'code',
      name: 'Coding Tools',
      job: 'Code, files, tests and Git',
      description: 'Used when an Agent needs to edit project files, run tests or builds, inspect command output, or work with Git.'
    },
    {
      icon: 'browser',
      name: 'Playwright',
      job: 'Browser and webpage actions',
      description: 'Used for opening webpages, clicking and filling forms, reading the DOM, taking screenshots, and browser QA.'
    },
    {
      icon: 'system',
      name: 'Remote Desktop Commander',
      job: 'Computer files, processes and local services',
      description: 'Used for host-level files and processes, checking local services, and recovering local tool connections when needed.'
    },
    {
      icon: 'research',
      name: 'Serena',
      job: 'Understand large codebases',
      description: 'Used to find symbols, references and code structure before making a precise engineering change.'
    },
    {
      icon: 'advanced',
      name: 'Windows-MCP',
      job: 'Native Windows interface',
      description: 'Used only when a task depends on Windows UI outside a normal webpage, such as native dialogs or system controls.'
    }
  ];

  root.innerHTML = pageHead(
    'Tools & MCP',
    'Tools are the Agent’s hands. Skills explain how to do a job; Workflows arrange the job; MCP connections let the Agent actually operate software, webpages and your computer.',
    '<a class="button" href="#/advanced">Open Advanced Tools</a>'
  );
  root.innerHTML += '<section class="tools-beginner-note">' + iconSvg('agent', 'tools-note-icon') +
    '<div><strong>You normally do not need to choose a tool yourself.</strong>' +
    '<p>The Agent should first read the selected Skill. That Skill or Workflow tells it which tools are appropriate. Connection availability is rediscovered when the Agent actually executes the task.</p></div></section>';
  root.innerHTML += '<div class="agent-tools-grid">' + toolCards.map(tool =>
    '<article class="agent-tool-card">' +
      '<span class="agent-tool-icon">' + iconSvg(tool.icon) + '</span>' +
      '<div><small>What it is for</small><h2>' + esc(tool.name) + '</h2><strong>' + esc(tool.job) + '</strong>' +
      '<p>' + esc(tool.description) + '</p></div></article>'
  ).join('') + '</div>';
  root.innerHTML += '<section class="tool-routing-note"><div class="tool-routing-flow">' +
    '<span><b>1</b><strong>Choose a Skill</strong><small>Start from the capability you need.</small></span>' +
    '<span class="tool-routing-arrow">→</span>' +
    '<span><b>2</b><strong>Read its full instructions</strong><small>Keep nested workflows and routes intact.</small></span>' +
    '<span class="tool-routing-arrow">→</span>' +
    '<span><b>3</b><strong>Use the required MCP/tools</strong><small>The Agent routes to the right tool automatically.</small></span>' +
    '</div></section>';
}

async function renderAdvanced() {
  const health = await api('/api/health');
  root.innerHTML = pageHead(
    'Advanced Tools',
    'Maintenance, troubleshooting and system-level tools live here. You normally do not need them when browsing Skills or automations.'
  );
  const destinations = [
    ['health', '#/system/health', 'System health', 'Check whether the index, database and local services are healthy.'],
    ['sources', '#/system/sources', 'Skill sources', 'See where Skills were discovered and which source has priority.'],
    ['organize', '#/system/organization', 'Manual categories & tags', 'Manage categories and tags you created. An empty state is normal.'],
    ['contexts', '#/system/contexts', 'Workspaces & Agents', 'Inspect workspace and Agent relationship metadata.'],
    ['deploy', '#/deployments', 'Deployment & physical locations', 'Preview Skill deployment plans and managed locations; physical changes remain dry-run only.']
  ];
  root.innerHTML += '<div class="advanced-hub-grid">' + destinations.map(item =>
    '<a class="advanced-hub-card" href="' + item[1] + '">' + iconSvg(item[0], 'advanced-hub-icon') +
    '<div><strong>' + item[2] + '</strong><p>' + item[3] + '</p></div>' + iconSvg('arrow', 'card-arrow') + '</a>'
  ).join('') + '</div>';
  root.innerHTML += '<section class="advanced-status-line">' + iconSvg(health.ok ? 'check' : 'alert', 'status-icon') + '<div><strong>' +
    (health.ok ? 'Current system healthy' : 'Current system needs attention') + '</strong><span>' +
    health.registry.skill_count + ' Skills · schema v' + health.integrity.schema_version +
    ' · ' + esc(msg('advanced.activeTransactions', { count: health.active_deployment_transactions || 0 })) + '</span></div></section>';
}

async function renderDeployments() {
  const [transactions, locations] = await Promise.all([
    api('/api/deployments/transactions?limit=60'),
    api('/api/deployments/locations?limit=60')
  ]);
  const operations = [
    'adopt_existing',
    'deploy_from_local_source',
    'update_managed',
    'relocate_managed',
    'undeploy_to_quarantine'
  ];
  root.innerHTML = pageHead(
    'Deployments',
    'M03 physical safety truth. M06 enables dry-run planning and read-only transaction/location inspection only.'
  );
  root.innerHTML += '<div class="risk-box"><strong>Dry run only.</strong> Physical apply, update, relocate, undeploy, recover and rollback are not exposed by the accepted M04 contract.</div>';
  root.innerHTML += '<div class="detail-grid" style="margin-top:10px"><section class="card"><div class="card-head"><h2>Plan Builder</h2></div>' +
    '<div class="card-body"><div class="form-grid"><div class="field"><label for="deploySkill">Canonical skill_id</label>' +
    '<input id="deploySkill" name="deploy-skill" autocomplete="off" placeholder="skill_id…"></div><div class="field"><label for="deployOperation">Operation</label>' +
    '<select id="deployOperation" name="deploy-operation">' + operations.map(value => '<option value="' + value + '">' + value + '</option>').join('') +
    '</select></div><div class="field full"><label for="deploySource">Source path (when required)</label><input id="deploySource" name="deploy-source" autocomplete="off"></div>' +
    '<div class="field full"><label for="deployTarget">Target path (when required)</label><input id="deployTarget" name="deploy-target" autocomplete="off"></div></div>' +
    '<button class="button primary" id="previewDeployment">Preview dry run</button><div id="deploymentPlanResult"></div></div></section>' +
    '<aside class="disabled-action"><strong>Physical apply unavailable in M06</strong><span>No generic file operation fallback exists. A later owned typed contract must revalidate the plan, ownership, digests and rollback semantics.</span>' +
    '<button class="button" disabled>Apply deployment</button><button class="button" disabled>Recover transaction</button>' +
    '<button class="button" disabled>Rollback transaction</button></aside></div>';

  const locationContent = locations.items.length
    ? '<div class="table-wrap"><table><thead><tr><th scope="col">Skill</th><th scope="col">Ownership</th><th scope="col">Path</th><th scope="col">Digest</th><th scope="col">Updated</th></tr></thead><tbody>' +
      locations.items.map(item =>
        '<tr><td>' + esc(item.skill_id) + '</td><td>' + badge(item.ownership_class, 'accent') +
        '</td><td><span class="path" title="' + esc(item.path) + '">' + esc(item.path) +
        '</span></td><td>' + mono(item.content_digest || '—') + '</td><td>' + esc(item.updated_at) + '</td></tr>'
      ).join('') + '</tbody></table></div>'
    : '<div class="empty">No active managed locations.</div>';
  root.innerHTML += '<section class="card" style="margin-top:10px"><div class="card-head"><h2>Managed locations</h2></div><div class="card-body">' +
    locationContent + '</div></section>';

  const transactionContent = transactions.items.length
    ? '<div class="table-wrap"><table><thead><tr><th scope="col">State</th><th scope="col">Skill</th><th scope="col">Operation</th><th scope="col">Source</th><th scope="col">Target</th><th scope="col">Updated</th></tr></thead><tbody>' +
      transactions.items.map(item =>
        '<tr><td>' + badge(item.state, statusTone(item.state)) + '</td><td>' + esc(item.skill_id) +
        '</td><td>' + esc(item.operation) + '</td><td><span class="path" title="' + esc(item.source_path || '') +
        '">' + esc(item.source_path || '—') + '</span></td><td><span class="path" title="' + esc(item.target_path || '') +
        '">' + esc(item.target_path || '—') + '</span></td><td>' + esc(item.updated_at) + '</td></tr>'
      ).join('') + '</tbody></table></div>'
    : '<div class="empty">No deployment transactions. Dry-run plans do not create transaction rows.</div>';
  root.innerHTML += '<section class="card" style="margin-top:10px"><div class="card-head"><h2>Transaction history</h2></div><div class="card-body">' +
    transactionContent + '</div></section>';

  document.querySelector('#previewDeployment').addEventListener('click', async () => {
    const target = document.querySelector('#deploymentPlanResult');
    const payload = {
      skill_id: document.querySelector('#deploySkill').value.trim(),
      operation: document.querySelector('#deployOperation').value
    };
    const source = document.querySelector('#deploySource').value.trim();
    const destination = document.querySelector('#deployTarget').value.trim();
    if (source) payload.source_path = source;
    if (destination) payload.target_path = destination;
    try {
      const result = await api('/api/deployments/plan', {
        method: 'POST',
        body: payload
      });
      target.innerHTML = '<pre class="code-pane">' + esc(pretty(result)) + '</pre>';
    } catch (error) {
      target.innerHTML = '<div class="error-state"><strong>Policy / validation error</strong><p>' +
        esc(error.message) + '</p></div>';
    }
  });
}

function systemTabs(active) {
  const tabs = [
    ['health', 'Health'],
    ['sources', 'Sources'],
    ['organization', 'Organization'],
    ['contexts', 'Contexts']
  ];
  return '<div class="tabs" role="navigation">' + tabs.map(([key, label]) =>
    '<a class="tab"' + (active === key ? ' aria-current="page"' : '') + ' href="#/system/' + key + '">' +
    label + '</a>'
  ).join('') + '</div>';
}

async function renderSystem(view = 'health', params = new URLSearchParams()) {
  if (!['health', 'sources', 'organization', 'contexts'].includes(view)) view = 'health';
  root.innerHTML = pageHead(
    'System',
    'Authority, runtime and metadata truth. Secret, token, cookie and OAuth material are never displayed.'
  ) + systemTabs(view);

  if (view === 'health') {
    const issueCursor = Math.max(0, Number(params.get('issue_cursor') || 0));
    const [health, issues] = await Promise.all([
      api('/api/health'),
      api('/api/discovery-issues?cursor=' + issueCursor + '&limit=50')
    ]);
    const registry = health.registry;
    root.innerHTML += '<div class="grid metrics">' +
      '<div class="metric"><strong>:' + health.runtime.current.port + '</strong><span>Current · ' +
      (health.runtime.current.listening ? 'listening' : 'down') + '</span></div>' +
      '<div class="metric"><strong>:' + health.runtime.rollback.port + '</strong><span>Rollback · ' +
      (health.runtime.rollback.listening ? 'listening' : 'down') + '</span></div>' +
      '<div class="metric"><strong>' + registry.skill_count + '</strong><span>Selected Skills</span></div>' +
      '<div class="metric"><strong>' + registry.variant_count + '</strong><span>Variants</span></div>' +
      '<div class="metric"><strong>' + health.active_deployment_transactions + '</strong><span>Active physical tx</span></div></div>';
    root.innerHTML += '<div class="detail-grid" style="margin-top:10px"><section class="card"><div class="card-head"><h2>Canonical truth</h2></div>' +
      '<div class="card-body"><dl class="kv"><dt>Parity</dt><dd>' +
      badge(health.parity.ok ? 'PASS' : 'DEGRADED', health.parity.ok ? 'good' : 'bad') +
      '</dd><dt>SQLite integrity</dt><dd>' +
      badge((health.integrity.integrity_check || []).join(', '), health.integrity.integrity_check?.[0] === 'ok' ? 'good' : 'bad') +
      '</dd><dt>Foreign key violations</dt><dd>' + (health.integrity.foreign_key_violations || []).length +
      '</dd><dt>Schema version</dt><dd>' + health.integrity.schema_version +
      '</dd><dt>Non-selectable variants</dt><dd>' + registry.nonselectable_variant_count +
      '</dd><dt>Invalid inputs</dt><dd>' + registry.invalid_count +
      '</dd><dt>Explicit files</dt><dd>' + registry.explicit_file_count + '</dd></dl></div></section>' +
      '<section class="card"><div class="card-head"><h2>Runtime listeners</h2></div><div class="card-body"><dl class="kv">' +
      '<dt>Gateway</dt><dd>' + mono('127.0.0.1:' + health.runtime.gateway.port) + ' ' +
      badge(health.runtime.gateway.listening ? 'listening' : 'down', health.runtime.gateway.listening ? 'good' : 'bad') +
      '</dd><dt>Legacy</dt><dd>' + mono('127.0.0.1:' + health.runtime.legacy.port) + ' ' +
      badge(health.runtime.legacy.listening ? 'listening' : 'down', health.runtime.legacy.listening ? 'good' : 'bad') +
      '</dd><dt>Rollback</dt><dd>' + mono('127.0.0.1:' + health.runtime.rollback.port) + ' ' +
      badge(health.runtime.rollback.listening ? 'listening' : 'down', health.runtime.rollback.listening ? 'good' : 'bad') +
      '</dd><dt>Current</dt><dd>' + mono('127.0.0.1:' + health.runtime.current.port) + ' ' +
      badge(health.runtime.current.listening ? 'listening' : 'down', health.runtime.current.listening ? 'good' : 'bad') +
      '</dd></dl></div></section></div>';
    const issueBody = issues.items.length
      ? '<div class="table-wrap"><table><thead><tr><th scope="col">Invalid path</th><th scope="col">Errors</th></tr></thead><tbody>' +
        issues.items.map(item =>
          '<tr><td><span class="path" title="' + esc(item.path) + '">' + esc(item.path) +
          '</span></td><td>' + esc((item.errors || []).join(', ')) + '</td></tr>'
        ).join('') + '</tbody></table></div>'
      : '<div class="empty">No Discovery Issues.</div>';
    const issueStart = issues.total ? issues.cursor + 1 : 0;
    const issueEnd = issues.cursor + issues.items.length;
    const issuePrevious = Math.max(0, issues.cursor - 50);
    const issuePager =
      '<div class="pagination"><span>' + issueStart + '–' + issueEnd + ' of ' + issues.total + ' issues</span><div class="actions">' +
      (issues.cursor > 0
        ? '<a class="button" href="#/system/health?issue_cursor=' + issuePrevious + '">Previous</a>'
        : '') +
      (issues.next_cursor !== null
        ? '<a class="button" href="#/system/health?issue_cursor=' + issues.next_cursor + '">Next</a>'
        : '') +
      '</div></div>';
    root.innerHTML += '<section class="card" style="margin-top:10px"><div class="card-head"><h2>Discovery Issues</h2></div><div class="card-body">' +
      issueBody + issuePager + '</div></section>';
    return;
  }

  if (view === 'sources') {
    const cursor = Math.max(0, Number(params.get('cursor') || 0));
    const page = await api('/api/sources-page?cursor=' + cursor + '&limit=50');
    const rows = page.items.map(source =>
      '<tr><td>' + esc(source.source_class) + '</td><td>' + source.authority_tier +
      '</td><td>' + esc(String(source.selectable)) + '</td><td>' + esc(String(source.active)) +
      '</td><td><span class="path" title="' + esc(source.path) + '">' + esc(source.path) + '</span></td></tr>'
    ).join('');
    const start = page.total ? page.cursor + 1 : 0;
    const end = page.cursor + page.items.length;
    const previous = Math.max(0, page.cursor - 50);
    const pager =
      '<div class="pagination"><span>' + start + '–' + end + ' of ' + page.total + ' sources</span><div class="actions">' +
      (page.cursor > 0
        ? '<a class="button" href="#/system/sources?cursor=' + previous + '">Previous</a>'
        : '') +
      (page.next_cursor !== null
        ? '<a class="button" href="#/system/sources?cursor=' + page.next_cursor + '">Next</a>'
        : '') +
      '</div></div>';
    root.innerHTML += '<section class="card"><div class="card-head"><h2>Source authority</h2></div><div class="card-body">' +
      '<div class="table-wrap"><table><thead><tr><th scope="col">Class</th><th scope="col">Authority</th>' +
      '<th scope="col">Selectable</th><th scope="col">Active</th><th scope="col">Path</th></tr></thead><tbody>' +
      rows + '</tbody></table></div>' + pager + '</div></section>';
    return;
  }

  if (view === 'organization') {
    const [categories, tags] = await Promise.all([api('/api/categories'), api('/api/tags')]);
    const categoryContent = categories.length
      ? '<div class="table-wrap"><table><thead><tr><th scope="col">Name</th><th scope="col">Skills</th><th scope="col">Description</th><th scope="col">Action</th></tr></thead><tbody>' +
        categories.map(item =>
          '<tr><td>' + esc(item.name) + '</td><td>' + item.skill_count +
          '</td><td>' + esc(item.description || '—') + '</td><td><button class="button danger" data-delete-category="' +
          esc(item.category_id) + '" data-name="' + esc(item.name) + '">Delete</button></td></tr>'
        ).join('') + '</tbody></table></div>'
      : '<div class="empty">No categories yet. This is a normal first-use state.</div>';
    const tagContent = tags.length
      ? '<div class="table-wrap"><table><thead><tr><th scope="col">Name</th><th scope="col">Skills</th><th scope="col">Action</th></tr></thead><tbody>' +
        tags.map(item =>
          '<tr><td>' + esc(item.name) + '</td><td>' + item.skill_count +
          '</td><td><button class="button danger" data-delete-tag="' + esc(item.tag_id) +
          '" data-name="' + esc(item.name) + '">Delete</button></td></tr>'
        ).join('') + '</tbody></table></div>'
      : '<div class="empty">No tags yet. This is a normal first-use state.</div>';
    root.innerHTML += '<div class="detail-grid"><section class="card"><div class="card-head"><h2>Categories</h2></div><div class="card-body">' +
      categoryContent + '<div class="toolbar" style="margin-top:10px"><label class="sr-only" for="systemCategoryName">Category name</label><input id="systemCategoryName" name="system-category-name" autocomplete="off" placeholder="Category name…">' +
      '<label class="sr-only" for="systemCategoryDescription">Category description</label><input id="systemCategoryDescription" name="system-category-description" autocomplete="off" placeholder="Description…"><button class="button" id="systemCategorySave">Create / update</button></div></div></section>' +
      '<section class="card"><div class="card-head"><h2>Tags</h2></div><div class="card-body">' + tagContent +
      '<div class="toolbar" style="margin-top:10px"><label class="sr-only" for="systemTagName">Tag name</label><input id="systemTagName" name="system-tag-name" autocomplete="off" placeholder="Tag name…">' +
      '<button class="button" id="systemTagSave">Create / update</button></div></div></section></div>';
    document.querySelector('#systemCategorySave').addEventListener('click', async () => {
      if (!canMutate()) return;
      try {
        await api('/api/categories', {
          method: 'POST',
          body: {
            name: document.querySelector('#systemCategoryName').value,
            description: document.querySelector('#systemCategoryDescription').value
          }
        });
        await renderSystem('organization');
      } catch (error) { toast(error.message, true); }
    });
    document.querySelector('#systemTagSave').addEventListener('click', async () => {
      if (!canMutate()) return;
      try {
        await api('/api/tags', {
          method: 'POST',
          body: { name: document.querySelector('#systemTagName').value }
        });
        await renderSystem('organization');
      } catch (error) { toast(error.message, true); }
    });
    document.querySelectorAll('[data-delete-category]').forEach(button => {
      button.addEventListener('click', async () => {
        if (!canMutate()) return;
        if (!confirm(i18n.message(state.locale, 'confirm.deleteCategory', { name: button.dataset.name }))) return;
        try {
          await api('/api/categories/' + encodeURIComponent(button.dataset.deleteCategory) + '/delete', {
            method: 'POST',
            body: {}
          });
          await renderSystem('organization');
        } catch (error) { toast(error.message, true); }
      });
    });
    document.querySelectorAll('[data-delete-tag]').forEach(button => {
      button.addEventListener('click', async () => {
        if (!canMutate()) return;
        if (!confirm(i18n.message(state.locale, 'confirm.deleteTag', { name: button.dataset.name }))) return;
        try {
          await api('/api/tags/' + encodeURIComponent(button.dataset.deleteTag) + '/delete', {
            method: 'POST',
            body: {}
          });
          await renderSystem('organization');
        } catch (error) { toast(error.message, true); }
      });
    });
    return;
  }

  const [workspaces, agents] = await Promise.all([api('/api/workspaces'), api('/api/agents')]);
  const workspaceContent = workspaces.length
    ? '<div class="table-wrap"><table><thead><tr><th scope="col">Workspace</th><th scope="col">Root</th></tr></thead><tbody>' +
      workspaces.map(item =>
        '<tr><td>' + esc(item.name) + '</td><td><span class="path">' + esc(item.root_path) + '</span></td></tr>'
      ).join('') + '</tbody></table></div>'
    : '<div class="empty">No workspace metadata. Editing is intentionally not exposed in this M06 surface.</div>';
  const agentContent = agents.length
    ? '<div class="table-wrap"><table><thead><tr><th scope="col">Agent</th><th scope="col">Workspace</th></tr></thead><tbody>' +
      agents.map(item =>
        '<tr><td>' + esc(item.name) + '</td><td>' + esc(item.workspace_id || '—') + '</td></tr>'
      ).join('') + '</tbody></table></div>'
    : '<div class="empty">No agent metadata. Editing is intentionally not exposed in this M06 surface.</div>';
  root.innerHTML += '<div class="detail-grid"><section class="card"><div class="card-head"><h2>Workspaces</h2></div><div class="card-body">' +
    workspaceContent + '</div></section><section class="card"><div class="card-head"><h2>Agents</h2></div><div class="card-body">' +
    agentContent + '</div></section></div>';
}

window.addEventListener('hashchange', render);

searchBox.addEventListener('keydown', event => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  const query = searchBox.value.trim();
  location.hash = '#/skills' + (query ? '?query=' + encodeURIComponent(query) : '');
});

document.addEventListener('keydown', event => {
  const tag = document.activeElement?.tagName;
  const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag);
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    searchBox.focus();
    searchBox.select();
    return;
  }
  if (event.key === '/' && !editing) {
    event.preventDefault();
    searchBox.focus();
    return;
  }
  if (event.key === 'Escape') {
    setNavigationOpen(false);
    if (editing) document.activeElement.blur();
  }
});

navToggle.addEventListener('click', () => {
  setNavigationOpen(!appShell.classList.contains('nav-open'));
});
document.querySelector('.nav-list').addEventListener('click', () => {
  setNavigationOpen(false);
});
document.addEventListener('click', event => {
  if (appShell.classList.contains('nav-open') && !event.target.closest('.sidebar, #navToggle')) {
    setNavigationOpen(false);
  }
});

localeZh.addEventListener('click', () => setLocale('zh-CN'));
localeEn.addEventListener('click', () => setLocale('en'));

applyLocale(document);

if (!location.hash) {
  location.hash = '#/overview';
} else {
  render();
}
