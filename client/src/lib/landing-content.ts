/**
 * Static marketing content for the landing page and the new-project dialog.
 * This is page copy, not project data: real projects come from the API.
 */
import type { LandingShowcase } from './types'

/** Example ideas offered in the hero input and the new-project dialog. */
export const IDEA_SUGGESTIONS: string[] = [
  'A habit tracker that pairs you with a friend for accountability',
  'A marketplace for students to rent out textbooks',
  'A recipe app that suggests meals from what is in your fridge',
  'A volunteer shift planner for local charities',
]

/** Sample run shown in the animated "How it works" previews on the landing page. */
export const LANDING_SHOWCASE: LandingShowcase = {
  idea: 'An app where students find study partners from the same course and book a room together.',
  specItems: [
    'Sign up with a university email',
    'Weekly availability grid that finds shared free time',
    'Create or join study sessions per course',
    'Book a library room for a session',
  ],
  stack: [
    { layer: 'Frontend', name: 'React + Vite', why: 'Fast, typed, huge ecosystem' },
    { layer: 'Backend', name: 'FastAPI', why: 'Readable Python with auto docs' },
    { layer: 'Database', name: 'PostgreSQL', why: 'Constraints stop double bookings' },
    { layer: 'Hosting', name: 'Docker on Render', why: 'Free tier, same everywhere' },
  ],
  codeFile: 'backend/main.py',
  codeLines: [
    [{ text: 'from', tone: 'keyword' }, { text: ' fastapi ' }, { text: 'import', tone: 'keyword' }, { text: ' FastAPI, HTTPException' }],
    [],
    [{ text: 'app' }, { text: ' = ', tone: 'punct' }, { text: 'FastAPI', tone: 'fn' }, { text: '(title=' }, { text: '"StudySync API"', tone: 'string' }, { text: ')' }],
    [],
    [{ text: '@app.get', tone: 'fn' }, { text: '(' }, { text: '"/sessions"', tone: 'string' }, { text: ')' }],
    [{ text: 'def', tone: 'keyword' }, { text: ' ' }, { text: 'list_sessions', tone: 'fn' }, { text: '() -> ' }, { text: 'list', tone: 'type' }, { text: '[' }, { text: 'StudySession', tone: 'type' }, { text: ']:' }],
    [{ text: '    # Soonest sessions first', tone: 'comment' }],
    [{ text: '    return', tone: 'keyword' }, { text: ' ' }, { text: 'sorted', tone: 'fn' }, { text: '(SESSIONS.values(), key=' }, { text: 'lambda', tone: 'keyword' }, { text: ' s: s.starts_at)' }],
    [],
    [{ text: '@app.post', tone: 'fn' }, { text: '(' }, { text: '"/sessions/{id}/join"', tone: 'string' }, { text: ')' }],
    [{ text: 'def', tone: 'keyword' }, { text: ' ' }, { text: 'join_session', tone: 'fn' }, { text: '(id: ' }, { text: 'str', tone: 'type' }, { text: '):' }],
    [{ text: '    if', tone: 'keyword' }, { text: ' ' }, { text: 'len', tone: 'fn' }, { text: '(session.members) >= session.capacity:' }],
    [{ text: '        raise', tone: 'keyword' }, { text: ' ' }, { text: 'HTTPException', tone: 'type' }, { text: '(' }, { text: '409', tone: 'number' }, { text: ', ' }, { text: '"Session is full"', tone: 'string' }, { text: ')' }],
  ],
  eva: { personas: 3, score: 82 },
  repo: 'demo-student/studysync',
  fileCount: 12,
  deployLog: [
    'Building Docker image',
    'Installing requirements.txt',
    'Running health check on /docs',
    'Connecting PostgreSQL database',
  ],
  liveUrl: 'studysync.onrender.com',
  learned: ['REST APIs', 'Pydantic validation', 'React state', 'Docker', 'CI/CD'],
}
