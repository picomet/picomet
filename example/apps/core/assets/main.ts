export function setDialog(v: string) {
  const newUrl = new URL(location.toString());
  newUrl.searchParams.set("v", v);
  history.pushState({}, "", newUrl.toString());
}

export function removeDialog() {
  const newUrl = new URL(location.toString());
  newUrl.searchParams.delete("v");
  history.pushState({}, "", newUrl.toString());
}
