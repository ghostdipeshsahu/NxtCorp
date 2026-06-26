// Mirror of backend backend/models/schemas.JOB_LEVELS. v3 universal ladder:
// same titles for every student regardless of job role.
export const JOB_TITLE_BY_LEVEL = {
  1: 'AI Trainee',
  2: 'AI Professional',
  3: 'AI Power User',
  4: 'AI Work Specialist',
  5: 'AI Work Expert',
};

// Tooltip copy shown when student hovers over their career level / next level
// title. v5 framing: the developer loop — requirements → AI → verification.
export const JOB_LEVEL_TOOLTIPS = {
  1: 'You are learning the developer loop — gathering requirements, using AI, and verifying output.',
  2: 'You can complete standard developer tasks independently using AI — from requirements to verified output.',
  3: 'You handle complex tasks involving multiple stakeholders and use AI effectively across all exercise types.',
  4: 'You lead development work using AI — decomposing, building, verifying, and refining with minimal coaching.',
  5: 'You work at production quality — requirements gathered, AI output verified, code optimized and reliable.',
};
