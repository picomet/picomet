// @ts-check
const path = require("node:path");
const eslint = require("@eslint/js");
const tseslint = require("typescript-eslint");
const globals = require("globals");
const jsdoc = require("eslint-plugin-jsdoc");

module.exports = tseslint.config(
  {
    ignores: [
      "**/env/*",
      "**/dist/*",
      "**/build/*",
      "**/esbonio/*",
      "**/.picomet/*",
    ],
  },
  eslint.configs.recommended,
  {
    files: ["**/*.ts"],
    plugins: {
      "@typescript-eslint": tseslint.plugin,
    },
    rules: {
      ...tseslint.configs.eslintRecommended.rules,
      ...tseslint.configs.recommended.at(-1).rules,
      ...tseslint.configs.recommendedTypeChecked.at(-1).rules,
    },
  },
  {
    files: ["src/picomet/assets/**/*.ts"],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        sourceType: "module",
        project: true,
        tsconfigRootDir: __dirname,
      },
      globals: {
        ...globals.browser,
      },
    },
  },
  {
    files: [
      "example/**/assets/**/*.ts",
      "example/**/comets/**/*.ts",
      "example/globals.d.ts",
    ],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        sourceType: "module",
        project: true,
        tsconfigRootDir: path.join(__dirname, "example"),
      },
      globals: {
        ...globals.browser,
      },
    },
  },
  {
    files: ["**/*.postcss.js", "**/*.tailwind.js", "src/picomet/tailwind.js"],
    plugins: {
      jsdoc,
    },
    rules: {
      ...jsdoc.configs["flat/recommended"].rules,
    },
    languageOptions: {
      globals: {
        ...globals.commonjs,
        ...globals.node,
      },
    },
  },
  {
    files: ["eslint.config.js"],
    languageOptions: {
      globals: {
        ...globals.commonjs,
        ...globals.node,
      },
    },
  },
);
