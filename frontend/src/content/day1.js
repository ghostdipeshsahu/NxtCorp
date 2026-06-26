// Day 1 story content — verbatim from spec §12.

export const PRIYA_WELCOME =
  "Welcome to NxtCorp! 🎉 I'm Priya, your manager. Really glad to have you on the team.\n\n" +
  "Here's how we work: every task starts with a meeting. Stakeholders explain what they need. Your job is to listen, take notes, and then use AI to build exactly what they asked for.\n\n" +
  "Sounds straightforward — but getting it exactly right takes practice. Your first task is already in the queue. Head to the meeting room when you're ready. 👋";

export const ARJUN_INTRO =
  "Hey! Arjun here — welcome to the team 🙌 Priya's great, you'll like working with her.\n\n" +
  "Fair warning: Zara from QA is intense 😅 But she's actually the best — catches everything before it hits production. You'll appreciate her once you've seen what slips through without her.\n\n" +
  "Good luck on your first task!";

export const ZARA_INTRO =
  "Hi. Zara here — QA Engineer.\n" +
  "I review every output before it ships.\n" +
  "If something's off, I'll flag it.\n" +
  "No hard feelings — that's just the job.\n" +
  "Do good work and we'll get along fine.";

export const RAVI_INTRO =
  "Welcome to NxtCorp.\n" +
  "We move fast here and we expect quality work.\n" +
  "Priya will get you started.\n" +
  "Good luck.";

export const DAY1_MESSAGES = [
  {
    id: 'day1_priya_welcome',
    character: 'priya',
    expression: 'happy',
    body: PRIYA_WELCOME,
  },
  {
    id: 'day1_arjun_intro',
    character: 'arjun',
    expression: 'happy',
    body: ARJUN_INTRO,
  },
  {
    id: 'day1_zara_intro',
    character: 'zara',
    expression: 'neutral',
    body: ZARA_INTRO,
  },
  {
    id: 'day1_ravi_intro',
    character: 'ravi',
    expression: 'proud',
    body: RAVI_INTRO,
  },
];
