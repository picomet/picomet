/* eslint-disable jsdoc/require-param-description */
/* eslint-disable no-undef */
/**
 * @param {Element} $el
 * @param {object} $data
 */
export function submitSignup($el, $data) {
  fetch("/api/signup", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: new FormData($el),
  })
    .then((response) => {
      response.json().then((data) => {
        if (data.success) {
          update(["&auth"]);
          removeDialog();
          setTimeout(() => {
            $el.reset();
          }, 0);
        } else if (data.errors) {
          $data.errors = data.errors;
        }
      });
    })
    .catch(() => {});
}
