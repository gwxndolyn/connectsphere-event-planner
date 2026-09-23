import type { CampusEvent } from "./types";

export const mockEvents: CampusEvent[] = [
  {
    id: "evt-hackathon",
    title: "Fall Build Night",
    description:
      "A four-hour build sprint for whatever you've been meaning to ship. Mentors from the CS department drop by after 7.",
    category: "workshop",
    date: "Sat, Oct 3",
    time: "5:00 PM",
    venue: "Innovation Lab, Rieger 2nd Floor",
    capacity: 60,
    registeredCount: 41,
    registrationOpen: true,
  },
  {
    id: "evt-resume",
    title: "Resumes That Get Read",
    description:
      "A career-center workshop on cutting your resume down to what recruiters actually look at. Bring a draft.",
    category: "career",
    date: "Tue, Oct 6",
    time: "12:00 PM",
    venue: "Career Center, Room 118",
    capacity: 30,
    registeredCount: 30,
    registrationOpen: true,
  },
  {
    id: "evt-fallfest",
    title: "Fall Fest Block Party",
    description:
      "Food trucks, a student-band lineup, and the annual pumpkin catapult on the East Quad lawn.",
    category: "social",
    date: "Fri, Oct 9",
    time: "6:00 PM",
    venue: "East Quad Lawn",
    capacity: 400,
    registeredCount: 128,
    registrationOpen: true,
  },
  {
    id: "evt-jazz",
    title: "Late Jazz: Student Combo Night",
    description:
      "The jazz combo class closes out the semester with a short set in the recital hall. Doors at 7:30.",
    category: "performance",
    date: "Thu, Oct 15",
    time: "8:00 PM",
    venue: "Ellsworth Recital Hall",
    capacity: 90,
    registeredCount: 90,
    registrationOpen: true,
  },
  {
    id: "evt-figma",
    title: "Intro to Prototyping in Figma",
    description:
      "Hands-on session for building a clickable prototype from scratch. Laptops provided if you don't have one.",
    category: "workshop",
    date: "Mon, Oct 19",
    time: "4:30 PM",
    venue: "Design Studio, Art Building 3",
    capacity: 24,
    registeredCount: 9,
    registrationOpen: true,
  },
];
