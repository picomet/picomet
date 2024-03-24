import type { getCookie as getCookieType } from "comet";
import type { update as updateType } from "comet";
import type { removeDialog as removeDialogType } from "main";

declare global {
  const getCookie: typeof getCookieType;
  const update: typeof updateType;
  const removeDialog: typeof removeDialogType;

  interface Success {
    success: string;
  }

  interface Errors {
    errors: {
      __all__: string[];
      [key: string]: string[];
    };
  }
}
