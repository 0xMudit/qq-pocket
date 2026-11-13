import React from "react";
import { createRoot } from "react-dom/client";
import { Lab } from "./lab";
import App from "./app";
import "./theme.css";
createRoot(document.getElementById("root")).render(
  location.pathname === "/lab" ? <Lab /> : <App />,
);
