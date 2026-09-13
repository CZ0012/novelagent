import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { activateLocale, normalizeAppLocale, UI_LOCALE_STORAGE_KEY } from "./localization";

const rootElement = document.getElementById("root") as HTMLElement;
let locale = normalizeAppLocale(null);
try {
  locale = normalizeAppLocale(window.localStorage.getItem(UI_LOCALE_STORAGE_KEY));
} catch {
  // Local storage can be disabled; the default locale remains available.
}
// Render only after the chosen catalog is ready: no flash of another language,
// and opening the app never downloads an unselected locale catalog.
activateLocale(locale).then(() => {
  ReactDOM.createRoot(rootElement).render(<React.StrictMode><App /></React.StrictMode>);
}).catch(() => {
  rootElement.textContent = "无法加载界面，请刷新重试。 / Unable to load the interface. Please reload.";
});
