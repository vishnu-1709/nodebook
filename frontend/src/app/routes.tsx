import { createBrowserRouter } from "react-router-dom";
import { CourseScreen } from "../screens/Course";
import { LectureScreen } from "../screens/Lecture";
import { InboxScreen } from "../screens/Inbox";
import { Onboarding } from "../screens/Onboarding";
import { ReviewScreen } from "../screens/Review";
import { ReviewSession } from "../screens/ReviewSession";
import { SettingsScreen } from "../screens/Settings";
import { Today } from "../screens/Today";
import { Shell } from "./Shell";

export const router = createBrowserRouter([
  { path: "/welcome", element: <Onboarding /> },
  {
    path: "/",
    element: <Shell />,
    children: [
      { index: true, element: <Today /> },
      { path: "review", element: <ReviewScreen /> },
      { path: "review/session", element: <ReviewSession /> },
      { path: "inbox", element: <InboxScreen /> },
      { path: "course/:courseId", element: <CourseScreen /> },
      { path: "course/:courseId/lecture/:lectureId", element: <LectureScreen /> },
      { path: "settings", element: <SettingsScreen /> },
    ],
  },
]);
