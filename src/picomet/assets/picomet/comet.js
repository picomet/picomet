/* eslint-disable jsdoc/require-param-description */
/* eslint-disable jsdoc/require-returns-description */

/**
 * @param {string} cookieName
 * @returns {string}
 */
export function getCookie(cookieName) {
  var name = cookieName + "=";
  var ca = document.cookie.split(";");
  for (var i = 0; i < ca.length; i++) {
    var c = ca[i];
    while (c.charAt(0) == " ") {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

/**
 * @param {Element} element
 * @returns {undefined|string}
 */
export function getFullXPath(element) {
  if (!(element instanceof Element)) return;
  var path = [];
  var currentNode = element;

  while (currentNode !== document.documentElement) {
    var count = 0;

    for (var siblingNode of currentNode.parentNode.children) {
      if (
        siblingNode.nodeType === Node.ELEMENT_NODE &&
        siblingNode.tagName === currentNode.tagName
      ) {
        count++;
      }
      if (siblingNode === currentNode) {
        break;
      }
    }

    const tagName = currentNode.tagName.toLowerCase();
    path.unshift(`${tagName}[${count}]`);
    currentNode = currentNode.parentNode;
  }
  path.unshift("html[1]");
  return `/${path.join("/")}`;
}

/**
 * @param {string} urlPrevious
 * @param {string} urlNew
 * @returns {string[]}
 */
function getParamTargets(urlPrevious, urlNew) {
  let targets = [];
  let paramsPrevious = new URL(urlPrevious).searchParams;
  let paramsNew = new URL(urlNew).searchParams;
  paramsNew.forEach((value, key) => {
    if (value != paramsPrevious.get(key)) {
      targets.push(`?${key}`);
    }
  });
  return targets;
}

/**
 * @param {MouseEvent} event
 */
function handleClick(event) {
  event.preventDefault();
  const url = event.currentTarget.href;
  if (location.href != new URL(url).href) {
    update(
      location.pathname != new URL(url).pathname
        ? ["&page"]
        : getParamTargets(location.href, url) || ["&x"],
      url,
      location.pathname != new URL(url).pathname,
    ).then((data) => {
      if (!data.redirect) {
        history.pushState({}, "", url);
      }
    });
  }
}

/**
 * @param {Element} el
 */
function appendToHead(el) {
  const copiedEl = el.cloneNode(true);
  copiedEl.removeAttribute("x-head");
  document.head.appendChild(copiedEl);
}

document.addEventListener("alpine:init", () => {
  Alpine.directive("head", (el, _, { cleanup }) => {
    const tag = el.tagName.toLowerCase();
    if (tag == "title") {
      document.title = el.textContent;
    } else if (tag == "meta") {
      const name = el.getAttribute("name");
      const property = el.getAttribute("property");
      if (name) {
        const meta = document.head.querySelector(`meta[name="${name}"]`);
        if (meta) {
          meta.setAttribute("content", el.getAttribute("content"));
        } else {
          appendToHead(el);
        }
      } else if (property) {
        const meta = document.head.querySelector(
          `meta[property="${property}"]`,
        );
        if (meta) {
          meta.setAttribute("content", el.getAttribute("content"));
        } else {
          appendToHead(el);
        }
      }
    }
    cleanup(() => {
      if (tag == "title") {
        document.title = "";
      } else if (tag == "meta") {
        const name = el.getAttribute("name");
        const property = el.getAttribute("property");
        if (name) {
          document.head.querySelector(`meta[name="${name}"]`).remove();
        } else if (property) {
          document.head.querySelector(`meta[property="${property}"]`).remove();
        }
      }
    });
  });
  Alpine.directive("form", (el, _, { cleanup }) => {
    /**
     * @param {SubmitEvent} event
     */
    function handleSubmit(event) {
      event.preventDefault();
      const body = new FormData(el);
      const url = new URL(window.location);
      fetch(url, {
        method: "post",
        body: body,
        headers: {
          Targets: JSON.stringify([getFullXPath(el)]),
          "X-CSRFToken": getCookie("csrftoken"),
        },
      }).then((response) => {
        handleResponse(response);
      });
    }
    el.addEventListener("submit", handleSubmit);
    cleanup(() => {
      el.removeEventListener("click", handleSubmit);
    });
  });

  Alpine.directive("link", (el, _, { cleanup }) => {
    el.addEventListener("click", handleClick);
    cleanup(() => {
      el.removeEventListener("click", handleClick);
    });
  });

  Alpine.directive("prop", (el, { value, expression }) => {
    Alpine.addScopeToNode(el, {
      [value]: JSON.parse(expression.replaceAll("&quot;", '"')),
    });
  }).before("data");
});

/**
 * @async
 * @param {string[]} targets
 * @param {string} url
 * @param {boolean} scrollToTop
 * @returns {Promise<JSON>}
 */
export async function update(targets, url, scrollToTop) {
  const response = await fetch(new URL(url || window.location), {
    headers: {
      Targets: JSON.stringify(targets),
    },
  });
  return await handleResponse(response, scrollToTop);
}

/** */
function handleNavigate() {
  Alpine.store("previousUrl", location.href);
}

// eslint-disable-next-line no-undef
navigation.addEventListener("navigate", handleNavigate);

/** */
function handlePopState() {
  const previousUrl = Alpine.store("previousUrl");
  const newUrl = location.toString();
  update(
    new URL(previousUrl).pathname != new URL(newUrl).pathname
      ? ["&page"]
      : getParamTargets(previousUrl, newUrl) || ["&x"],
  );
}

window.addEventListener("popstate", handlePopState);

/** */
export function cleanup() {
  // eslint-disable-next-line no-undef
  navigation.removeEventListener("navigate", handleNavigate);
  window.removeEventListener("popstate", handlePopState);
}

/**
 * @async
 * @param {string} action
 * @param {JSON|FormData} payload
 * @param {Array} [keys]
 * @returns {Promise<void>}
 */
export async function call(action, payload, keys) {
  let url = new URL(window.location);
  let formData;
  if (payload instanceof FormData) {
    formData = payload;
  } else {
    formData = new FormData();
    for (let key in payload) {
      formData.append(key, payload[key]);
    }
  }
  let response = await fetch(url, {
    method: "post",
    body: formData,
    headers: {
      Action: action,
      Keys: JSON.stringify(keys || []),
      "X-CSRFToken": getCookie("csrftoken"),
    },
  });
  await handleResponse(response);
}

/**
 * @async
 * @param {Response} response
 * @param {boolean} scrollToTop
 * @returns {Promise<JSON>}
 */
async function handleResponse(response, scrollToTop) {
  let data = await response.json();
  if (data.redirect) {
    history.pushState({}, "", data.redirect);
    if (data.update) {
      let targets = ["&page"];
      for (let target of JSON.parse(response.headers.get("Targets") || "[]")) {
        if (!targets.includes(target)) {
          targets.push(target);
        }
      }
      update(targets, null, location.pathname != data.redirect);
    }
  } else {
    if (scrollToTop) {
      window.scrollTo(0, 0);
    }
    for (let target in data) {
      let el = document.evaluate(
        target,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null,
      ).singleNodeValue;
      if (el) {
        for (let id in data[target].css) {
          if (!document.querySelector(`[data-style-id="${id}"]`)) {
            const linkElement = document.createElement("link");
            linkElement.rel = "stylesheet";
            linkElement.href = data[target].css[id];
            linkElement.setAttribute("data-style-id", id);
            document.head.appendChild(linkElement);
          }
        }
        for (let id in data[target].js) {
          if (!window[`${id}_cleanup`]) {
            import(data[target].js[id]).then((module) => {
              Object.keys(module).forEach((key) => {
                if (key == "cleanup") {
                  window[`${id}_cleanup`] = module[key];
                } else {
                  window[key] = module[key];
                }
              });
            });
          }
        }
        el.outerHTML = data[target].html;
      }
    }
  }
  return data;
}
