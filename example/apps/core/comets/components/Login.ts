export function submitLogin($el: HTMLFormElement, $data: Errors) {
  fetch("/api/login", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken"),
    },
    body: new FormData($el),
  })
    .then((response) => {
      response
        .json()
        .then((data: Success | Errors) => {
          if ("success" in data) {
            update(["&auth"]).catch(() => {});
            removeDialog();
            setTimeout(() => {
              $el.reset();
            }, 0);
          } else if (data.errors) {
            $data.errors = data.errors;
          }
        })
        .catch(() => {});
    })
    .catch(() => {});
}
