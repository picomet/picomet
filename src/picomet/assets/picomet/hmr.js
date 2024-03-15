/* eslint-disable jsdoc/require-returns-description */
/** */
function connect() {
  window.HMR = new WebSocket(`ws://${location.host}/ws/hmr`);
  window.HMR.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.layout) {
      location.reload();
    } else if (data.template) {
      // eslint-disable-next-line no-undef
      update([`$${data.template}`]);
    } else if (data.tailwind) {
      const id = data.tailwind.split(".")[0];
      const el = document.querySelector(`link[data-tailwind-id="${id}"]`);
      if (el) {
        el.setAttribute("href", `/${data.assetUrl}${data.tailwind}`);
      }
    } else if (data.style) {
      const id = data.style.split(".")[0];
      const el = document.getElementById(id);
      if (el) {
        const linkEl = document.createElement("link");
        linkEl.rel = "stylesheet";
        linkEl.href = `/${data.assetUrl}${data.style}`;
        linkEl.id = id;
        el.replaceWith(linkEl);
      }
    } else if (data.script) {
      const id = data.script.split(".")[0];
      const el = document.querySelector(`[data-script-id="${id}"]`);
      if (el) {
        const cleanup = window[`${id}_cleanup`];
        if (typeof cleanup == "function") {
          cleanup();
        }
        import(`/${data.assetUrl}${data.script}`).then((module) => {
          Object.keys(module).forEach((key) => {
            if (key == "cleanup") {
              window[`${id}_cleanup`] = module[key];
            } else {
              window[key] = module[key];
            }
          });
        });
      }
    } else if (data.asset) {
      const id = data.asset.split(".")[0];
      const els = document.querySelectorAll(`[data-asset-id="${id}"]`);
      for (let el of els) {
        el.setAttribute(
          el.getAttribute("data-target"),
          `/${data.assetsUrl}${data.asset}`,
        );
      }
    }
  });
}
connect();

/** */
function reConnect() {
  if (window.HMR.readyState == WebSocket.CLOSED) {
    connect();
  }
}
const reConnectInterval = setInterval(reConnect, 1000);

/** */
export function cleanup() {
  window.HMR.close();
  clearInterval(reConnectInterval);
}
