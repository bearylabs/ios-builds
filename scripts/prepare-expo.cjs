// Wrap the upstream configuration in the disposable checkout, not in upstream Git.
const fs = require('node:fs');
const path = require('node:path');
const config = JSON.parse(process.env.APP_CONFIG);
const root = process.argv[2];
if (!fs.existsSync(path.join(root, 'app.config.js'))) {
  throw new Error('The Expo adapter currently expects a CommonJS app.config.js');
}
fs.renameSync(path.join(root, 'app.config.js'), path.join(root, 'app.upstream.config.js'));
fs.writeFileSync(path.join(root, 'app.config.js'), `
const upstream = require('./app.upstream.config.js');
const identity = ${JSON.stringify(config)};
module.exports = (...args) => {
  const original = typeof upstream === 'function' ? upstream(...args) : upstream;
  if (original && typeof original.then === 'function') throw new Error('Async Expo config not supported');
  const config = { ...original, ios: { ...original.ios } };
  delete config.owner;
  config.scheme = identity.url_scheme;
  config.ios.bundleIdentifier = identity.bundle_id;
  config.ios.infoPlist = { ...config.ios.infoPlist, CFBundleDisplayName: identity.display_name };
  delete config.ios.appleTeamId;
  if (process.env.APPLE_TEAM_ID) config.ios.appleTeamId = process.env.APPLE_TEAM_ID;
  config.updates = { ...config.updates, enabled: false };
  delete config.updates.url;
  config.extra = { ...config.extra };
  delete config.extra.eas;
  return config;
};
`);
const env = {
  OPENWHISPR_APP_ENV: 'production',
  OPENWHISPR_IOS_BUNDLE_IDENTIFIER: config.bundle_id,
  OPENWHISPR_SCHEME: config.url_scheme,
  OPENWHISPR_DISPLAY_NAME: config.display_name,
  OPENWHISPR_KEYBOARD_DISPLAY_NAME: config.display_name,
  EXPO_NO_DOTENV: '1',
  SENTRY_DISABLE_AUTO_UPLOAD: 'true',
  SENTRY_ALLOW_FAILURE: 'true',
  EXPO_NO_TELEMETRY: '1',
};
// Public configuration only: never put provider credentials in the bundle.
for (const [key, value] of Object.entries(env)) {
  if (/[\r\n]/.test(value)) throw new Error('Multiline environment value');
  fs.appendFileSync(process.env.GITHUB_ENV, `${key}=${value}\n`);
}
