/* eslint-disable jsdoc/require-param-description */

/**
 * @param {string} v
 */
export function setDialog(v) {
  var newUrl = new URL(location.toString());
  newUrl.searchParams.set("v", v);
  history.pushState({}, "", newUrl.toString());
}

/**
 *
 */
export function removeDialog() {
  var newUrl = new URL(location.toString());
  newUrl.searchParams.delete("v");
  history.pushState({}, "", newUrl.toString());
}
