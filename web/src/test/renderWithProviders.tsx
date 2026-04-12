import { ReactElement } from "react";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ToastProvider } from "../components/ToastProvider";
import { LanguageProvider } from "../localization";

type Options = {
  route?: string;
  path?: string;
};

export function renderWithProviders(ui: ReactElement, options: Options = {}) {
  return render(
    <MemoryRouter initialEntries={[options.route || "/"]}>
      <LanguageProvider language="en" setLanguage={() => undefined}>
        <ToastProvider>
          {options.path ? (
            <Routes>
              <Route path={options.path} element={ui} />
            </Routes>
          ) : (
            ui
          )}
        </ToastProvider>
      </LanguageProvider>
    </MemoryRouter>
  );
}
