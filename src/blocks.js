import { placeholder, placeholderMessage } from './tasks/placeholder.js';
import { deviceCheck, deviceCheckMessage } from './tasks/device_check.js';
import { fullscreenScreens, fullscreenMessage } from './tasks/fullscreen.js';
import { calibrationScreens, calibrationMessage } from './tasks/calibration.js';

// Blocks of a first session in their fixed order (decision 33;
// docs/11-technical-plan.md, section 2). build(block, ctx) returns the block's
// part of the jsPsych timeline; message(block, ctx) runs when the block ends
// and returns what to send to the receiver ({ summary, log, contact }) or
// null. ctx is { jsPsych, params, session, sender, monitor, calibration,
// end(status), ending() }; a block calls ctx.end(status) to end the session
// early after itself (main.js). label is shown in the dev menu, task names
// the development task that builds the block.
// isTask marks the five tasks: each starts only in fullscreen, and what
// happens around it (leaving the tab, fullscreen, zoom) is recorded
// (decisions 87, 99).

const block = (id, label, task, { isTask = false, build = placeholder, message = placeholderMessage } = {}) => ({
  id,
  label,
  task,
  isTask,
  build,
  message,
});

const TASK = { isTask: true };

export const BLOCKS = [
  block('device_check', 'Перевірка пристрою', 'Т0.5', { build: deviceCheck, message: deviceCheckMessage }),
  block('consent', 'Згода', 'Т2.2'),
  block('criteria', 'Критерії включення й виключення', 'Т2.2'),
  block('demographics', 'Біографічна анкета', 'Т2.2'),
  block('conditions', 'Анкета умов', 'Т2.2'),
  block('calibration', 'Калібрування екрана', 'Т0.6', { build: calibrationScreens, message: calibrationMessage }),
  block('fullscreen', 'Повноекранний режим', 'Т0.5', { build: fullscreenScreens, message: fullscreenMessage }),
  block('tmt_a', 'TMT, частина A', 'Т1.2–Т1.4', TASK),
  block('tmt_b', 'TMT, частина B', 'Т1.2–Т1.4', TASK),
  block('coding', 'Кодування символів', 'Т3.1', TASK),
  block('stroop', 'Stroop', 'Т3.2', TASK),
  block('sart', 'SART', 'Т3.3', TASK),
  block('pss10', 'PSS-10', 'Т2.3'),
  block('post', 'Питання після тесту', 'Т2.3'),
  block('retest_invite', 'Запрошення на ретест', 'Т2.3'),
  block('thanks', 'Подяка', 'Т2.3'),
];

export const isPlaceholder = (b) => b.build === placeholder;
