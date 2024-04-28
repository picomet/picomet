import type { update as updateType } from "comet";
declare const update: typeof updateType;

let HMR: WebSocket;

function connect() {
  HMR = new WebSocket(`ws://${location.host}/ws/hmr`);
  HMR.addEventListener("message", (event) => {
    if (typeof event.data == "string") {
      interface LayoutChange {
        layout: string;
      }
      interface TemplateChange {
        template: string;
      }
      interface AssetChange {
        staticUrl: string;
      }
      interface StyleChange extends AssetChange {
        style: string;
      }
      interface TailwindChange extends AssetChange {
        tailwind: string;
      }
      interface ScriptChange extends AssetChange {
        script: string;
      }
      interface LinkChange extends AssetChange {
        link: string;
      }
      const data = JSON.parse(event.data) as
        | LayoutChange
        | TemplateChange
        | StyleChange
        | TailwindChange
        | ScriptChange
        | LinkChange;
      if ("layout" in data) {
        location.reload();
      } else if ("template" in data) {
        update([`$${data.template}`]).catch(() => {});
      } else if ("tailwind" in data) {
        const id = data.tailwind.split(".")[0];
        const el = document.querySelector(`link[data-tailwind-id="${id}"]`);
        if (el) {
          el.setAttribute("href", `${data.staticUrl}${data.tailwind}`);
        }
      } else if ("style" in data) {
        const id = data.style.split(".")[0];
        const el = document.querySelector(`[data-style-id="${id}"]`);
        if (el) {
          el.setAttribute("href", `${data.staticUrl}${data.style}`);
        }
      } else if ("script" in data) {
        const id = data.script.split(".")[0];
        const el = document.querySelector(`[data-script-id="${id}"]`);
        if (el) {
          const cleanup = window[`${id}_cleanup`] as unknown;
          if (typeof cleanup == "function") {
            cleanup();
          }
          import(`${data.staticUrl}${data.script}`)
            .then((module: object) => {
              Object.keys(module).forEach((key) => {
                if (key == "cleanup") {
                  window[`${id}_cleanup`] = module[key] as unknown;
                } else {
                  window[key] = module[key] as unknown;
                }
              });
            })
            .catch(() => {});
        }
      } else if ("link" in data) {
        const id = data.link.split(".")[0];
        const els = document.querySelectorAll(`[data-asset-id="${id}"]`);
        els.forEach((el) => {
          el.setAttribute(
            el.getAttribute("data-target"),
            `${data.staticUrl}${data.link}`,
          );
        });
      }
    }
  });
}

connect();

function reConnect() {
  if (HMR.readyState == WebSocket.CLOSED) {
    connect();
  }
}
const reConnectInterval = setInterval(reConnect, 1000);

export function cleanup() {
  HMR.close();
  clearInterval(reConnectInterval);
}
