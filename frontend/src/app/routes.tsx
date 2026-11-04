import { createBrowserRouter } from "react-router-dom";
import { CourseScreen } from "../screens/Course";
import { LectureScreen } from "../screens/Lecture";
import { InboxScreen } from "../screens/Inbox";
import { Placeholder } from "../screens/Placeholder";
import { SettingsScreen } from "../screens/Settings";
import { Today } from "../screens/Today";
import { Shell } from "./Shell";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <Today /> },
      { path: "review", element: <Placeholder title="Review" text="Spaced review arrives in v0.2." /> },
      { path: "inbox", element: <InboxScreen /> },
      { path: "course/:courseId", element: <CourseScreen /> },
      { path: "course/:courseId/lecture/:lectureId", element: <LectureScreen /> },
      { path: "settings", element: <SettingsScreen /> },
    ],
  },
]);
