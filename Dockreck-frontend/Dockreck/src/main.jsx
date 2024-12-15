import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App.jsx";
// Importing bootstrap
import "bootstrap/dist/css/bootstrap.min.css";
import MainComp from "./components/MainComp.jsx";
import CategoryComp from "./components/CategoryComp.jsx";
import LibraryComp from "./components/LibraryComp.jsx";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      {
        path: "/",
        element: <MainComp />,
      },

      {
        path: "/classification",
        element: <CategoryComp />,
      },
      {
        path: "/library",
        element: <LibraryComp />,
      },
    ],
  },
]);
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>
);
