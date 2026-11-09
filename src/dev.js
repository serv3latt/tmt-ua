import { APP_VERSION } from './config.js';
import { isPlaceholder } from './blocks.js';

// Dev-mode screens (?mode=dev): a menu to jump to any block, a corner badge
// with the delivery queue that leads back to the menu, and a dump of the
// collected data at the end. Nothing here runs in main or pilot mode.

// Builds a dev link that keeps the current set.* overrides.
export function devUrl(session, extra = {}) {
  const query = new URLSearchParams({ mode: 'dev', ...extra });
  for (const [path, value] of Object.entries(session.overrides)) query.set(`set.${path}`, value);
  return `?${query}`;
}

export function renderDevMenu(blocks, session) {
  const rows = blocks
    .map(
      (b) => `<tr data-block="${b.id}">
        <td>${b.label}</td>
        <td>${isPlaceholder(b) ? `заглушка, ${b.task}` : 'готово'}</td>
        <td><a href="${devUrl(session, { start: b.id })}">звідси</a></td>
        <td><a href="${devUrl(session, { only: b.id })}">лише цей</a></td>
      </tr>`,
    )
    .join('');
  document.body.innerHTML = `
    <main class="dev-menu">
      <h1>TMT-UA · dev · <span class="dev-version">${APP_VERSION}</span></h1>
      <p><a href="${devUrl(session, { start: blocks[0].id })}">Уся сесія з початку</a></p>
      <p><a href="${devUrl(session, { tool: 'env' })}">Перевірка середовища</a>: клавіші в
        повноекранному режимі, вихід із вкладки, масштаб. Нічого не надсилає.</p>
      <table><tbody>${rows}</tbody></table>
      <p class="dev-hint">Параметри з <code>config.js</code> можна змінити в адресі,
        наприклад <code>&amp;set.tmt.timeLimitMs=20000</code>.</p>
    </main>`;
}

// Returns the badge element and update({ pending, rejected }) for the queue.
export function createDevBadge(session) {
  const badge = document.createElement('a');
  badge.className = 'dev-badge';
  badge.href = devUrl(session);
  const update = ({ pending, rejected }) => {
    badge.textContent = `dev ${APP_VERSION} · у черзі ${pending}`;
    if (rejected) badge.textContent += ` · відхилено ${rejected}`;
    badge.classList.toggle('dev-badge-alert', rejected > 0);
  };
  update({ pending: 0, rejected: 0 });
  return { element: badge, update };
}

export function renderDevEnd(jsPsych, session, badge) {
  document.body.innerHTML = `
    <main class="dev-end">
      <h1>Кінець dev-сесії</h1>
      <p><a href="${devUrl(session)}">До меню</a></p>
      <pre></pre>
    </main>`;
  document.querySelector('.dev-end pre').textContent = JSON.stringify(
    jsPsych.data.get().values(),
    null,
    2,
  );
  document.body.append(badge.element);
}
