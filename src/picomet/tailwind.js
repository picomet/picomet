/* eslint-disable jsdoc/require-param-description */
/* eslint-disable jsdoc/require-returns-description */
const postcss = require("postcss");
const fs = require("fs");
const crypto = require("crypto");
const path = require("path");

/**
 * @async
 * @param {string} inputCss
 * @param {string} tailwindConf
 * @param {string} postcssConf
 * @param {string} destDir
 * @param {string} id
 * @param {string[]} content
 * @param {boolean} DEBUG
 * @returns {string[]}
 */
async function compile(
  inputCss,
  tailwindConf,
  postcssConf,
  destDir,
  id,
  content,
  DEBUG,
) {
  const css = fs.readFileSync(inputCss);
  const twConfig = require(tailwindConf);
  twConfig.content = content;
  const plugins = require(postcssConf).plugins;
  for (let plugin in plugins) {
    if (
      typeof plugins[plugin] === "function" &&
      plugins[plugin]({}).postcssPlugin == "tailwindcss"
    ) {
      plugins[plugin] = require("tailwindcss")(twConfig);
    }
  }
  if (!DEBUG) {
    try {
      plugins.push(
        require("cssnano")({
          preset: "default",
        }),
      );
      // eslint-disable-next-line no-empty
    } catch (e) {}
  }
  const result = await postcss(plugins).process(css, { from: undefined });
  const hash = crypto
    .createHash("md5")
    .update(result.css)
    .digest("hex")
    .slice(0, 6);
  const fname = `${id}.${hash}.css`;
  const dest = path.join(destDir, fname);

  for (const file of fs.readdirSync(destDir)) {
    if (file.split(".")[0] == id) {
      fs.rmSync(path.join(destDir, file));
    }
  }

  fs.writeFileSync(dest, result.css);
  return [css.toString(), fname, result.css];
}

module.exports = { compile };
