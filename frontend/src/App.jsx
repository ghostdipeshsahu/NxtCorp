import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  advanceStory,
  completeOnboarding,
  getCurrentTask,
  getProfile,
  getStoryCurrent,
  getToken,
  logout,
  markMeetingComplete,
  respondToCoach,
  runAttempt,
} from './api.js';
import Login from './components/Auth/Login.jsx';
import OnboardingFlow from './components/Onboarding/OnboardingFlow.jsx';
import TopBar from './components/Office/TopBar.jsx';
import SceneManager from './components/Office/SceneManager.jsx';
import TaskPanel from './components/Task/TaskPanel.jsx';
import ChatPanel from './components/Chat/ChatPanel.jsx';
import ProfileModal from './components/Profile/ProfileModal.jsx';
import StoryEventOverlay from './components/Story/StoryEventOverlay.jsx';
import PromotionCinematic from './components/Story/PromotionCinematic.jsx';
import EmployeeOfMonthCinematic from './components/Story/EmployeeOfMonthCinematic.jsx';
import Day1Arrival from './components/Story/Day1Arrival.jsx';
import BadgeUnlock from './components/UI/BadgeUnlock.jsx';
import FirstTryBanner from './components/UI/FirstTryBanner.jsx';
import CustomCursor from './components/UI/CustomCursor.jsx';
import { JOB_TITLE_BY_LEVEL } from './content/levels.js';
import { useSound } from './sound/useSound.js';

export default function App() {
  const [authed, setAuthed] = useState(Boolean(getToken()));
  const [profile, setProfile] = useState(null);
  const [task, setTask] = useState(null);
  const [messages, setMessages] = useState([]);
  const [attemptNumber, setAttemptNumber] = useState(1);
  const [running, setRunning] = useState(false);
  const [respondBusy, setRespondBusy] = useState(false);
  const [lastRun, setLastRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [bootstrapped, setBootstrapped] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [storyQueue, setStoryQueue] = useState([]);
  const [storyBusy, setStoryBusy] = useState(false);

  // Scene system (left panel). Replaces the old OfficeView.
  const [currentScene, setCurrentScene] = useState('cabin'); // start in cabin (Priya assigns)
  const [coffeeHint, setCoffeeHint] = useState(null); // { text, loading, error }
  // v4: Meeting Room notes. Free-text the student takes while the briefing
  // plays. Saved here so they survive the cabin→meeting→desk transition.
  // Resets on new task load. Read-only once the student leaves the meeting.
  const [meetingNotes, setMeetingNotes] = useState('');
  // v3: when Arjun auto-fires after 3 failed attempts we show a toast
  // notification announcing the break to coffee corner.
  const [arjunToast, setArjunToast] = useState(null); // string | null
  const lastPriyaCountRef = useRef(0);

  // Cinematic state.
  const [promo, setPromo] = useState(null);   // { newTitle, displayName } or null
  const [badgeQueue, setBadgeQueue] = useState([]);
  const [firstTryOpen, setFirstTryOpen] = useState(false);
  const [day1Open, setDay1Open] = useState(false);
  // v3: Employee of the Month full-screen cinematic.
  const [eotmAward, setEotmAward] = useState(null); // { yearMonth, displayName } | null

  // Refs that watch profile transitions for promotion / badge detection.
  const prevLevelRef = useRef(null);
  const prevBadgeKeysRef = useRef(new Set());

  const { play, soundOn, toggleSound } = useSound();

  // ---------- Bootstrap ----------

  const bootstrapProfile = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const prof = await getProfile();
      setProfile(prof);
    } catch (err) {
      if (err.status === 401) {
        logout();
        setAuthed(false);
      } else {
        setLoadError(err.message);
      }
    } finally {
      setLoading(false);
      setBootstrapped(true);
    }
  }, []);

  const loadOffice = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const t = await getCurrentTask();
      setTask(t);
      // v3 fix: #team-chat carries Priya's *voice* line (priya_chat_message),
      // NOT the center-panel ticket framing. They are different content.
      // Falls back to a generic Priya voice — never the task description.
      const seeded = [];
      if (t) {
        const chatLine =
          t.priya_chat_message ||
          "New ticket just came in. Head to the meeting room first — the stakeholders will explain what they need. Take good notes. You will need them at your desk.";
        seeded.push({
          id: `framing-${t.question_id}`,
          character: t.framing_character || 'priya',
          expression: 'happy',
          body: chatLine,
        });
      }
      setMessages(seeded);
    } catch (err) {
      if (err.status === 401) {
        logout();
        setAuthed(false);
      } else {
        setLoadError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    bootstrapProfile();
  }, [authed, bootstrapProfile]);

  // After onboarding flips done, run the Day 1 arrival cinematic; only AFTER
  // it finishes do we load the office. On subsequent sessions (already
  // onboarded when bootstrap finishes), skip the cinematic.
  const onboardingJustCompletedRef = useRef(false);

  useEffect(() => {
    if (!authed || !profile || !profile.onboarding_done) return;
    if (onboardingJustCompletedRef.current) {
      setDay1Open(true);
      // loadOffice triggered after Day1Arrival's onDone callback (below).
    } else {
      loadOffice();
      refreshStoryQueue();
    }
    // Initialize promotion/badge baselines from the first profile we see.
    if (prevLevelRef.current == null) {
      prevLevelRef.current = profile.job_level;
      prevBadgeKeysRef.current = new Set(
        (profile.badges || []).map((b) => b.badge_key),
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed, profile?.onboarding_done, loadOffice]);

  // ---------- Cinematic detection ----------

  // Watch the profile for new badges + level-ups, queue cinematics.
  useEffect(() => {
    if (!profile) return;
    // Badges: diff current vs. previous.
    const current = new Set((profile.badges || []).map((b) => b.badge_key));
    const newly = [];
    current.forEach((k) => {
      if (!prevBadgeKeysRef.current.has(k)) newly.push(k);
    });
    if (newly.length > 0) {
      setBadgeQueue((q) => [...q, ...newly]);
      play('badge');
    }
    prevBadgeKeysRef.current = current;

    // Level-up: open the promotion cinematic.
    if (prevLevelRef.current != null && profile.job_level > prevLevelRef.current) {
      const newTitle = profile.job_title || JOB_TITLE_BY_LEVEL[profile.job_level] || '';
      setPromo({ newTitle, displayName: profile.display_name });
      play('promotion');
    }
    prevLevelRef.current = profile.job_level;
  }, [profile, play]);

  // ---------- Onboarding ----------

  async function handleOnboardingSubmit(payload) {
    const updated = await completeOnboarding(payload);
    onboardingJustCompletedRef.current = true;
    setProfile(updated);
  }

  // ---------- Scene triggers ----------

  // New task → start in the manager's cabin AND reset the per-task
  // attempt counter. Attempts are scoped to the current ticket, not the
  // session — a fresh ticket always opens at Attempt #1.
  useEffect(() => {
    if (!task) return;
    setCurrentScene('cabin');
    setAttemptNumber(1);
    setLastRun(null);
    // v4: meeting notes are per-task — wipe them when the ticket changes
    // so notes from the previous task don't carry over to the new one.
    setMeetingNotes('');
  }, [task?.question_id]);

  // Every new Priya coach reply pushes the scene back to the cabin.
  // (Arjun's reply is handled directly in handleRun — it never enters
  // the #team-chat messages array per v3 BUG 2 fix.)
  useEffect(() => {
    const priyaMessages = messages.filter((m) => m.character === 'priya');
    if (priyaMessages.length > lastPriyaCountRef.current) {
      setCurrentScene('cabin');
    }
    lastPriyaCountRef.current = priyaMessages.length;
  }, [messages]);

  // Auto-dismiss the Arjun toast after a few seconds.
  useEffect(() => {
    if (!arjunToast) return undefined;
    const t = setTimeout(() => setArjunToast(null), 4000);
    return () => clearTimeout(t);
  }, [arjunToast]);

  function handleCoffeeBack() {
    // v3: after Arjun's coffee-corner conversation, the student goes
    // STRAIGHT back to their desk to work independently with the hint
    // in mind — NOT to Priya's cabin. Priya only re-engages after the
    // student submits again and fails.
    setCurrentScene('desk');
    setCoffeeHint(null);
  }

  // v4/v5: "Start task" inside the cabin routes the student into the
  // Meeting Room briefing the FIRST time they touch a task. Once the
  // meeting is completed (persisted server-side per question), this
  // shortcuts straight to the desk — no replay of the briefing.
  function handleStartTask() {
    if (task?.meeting_completed) {
      setCurrentScene('desk');
    } else {
      setCurrentScene('meeting');
    }
  }

  async function handleMeetingDone(finalNotes) {
    if (typeof finalNotes === 'string') setMeetingNotes(finalNotes);
    setCurrentScene('desk');
    // v5: persist meeting_completed on the backend so a refresh — or
    // Priya's later coaching messages that route back through the cabin
    // — never replays the meeting for this ticket.
    try {
      await markMeetingComplete();
      // Reflect the flag locally so the cabin CTA hides immediately.
      setTask((t) => (t ? { ...t, meeting_completed: true } : t));
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[meeting] mark-complete failed', err);
    }
  }

  // ---------- Story ----------

  async function refreshStoryQueue() {
    try {
      const state = await getStoryCurrent();
      const seenKeys = new Set(storyQueue.map((e) => e.event_key));
      const incoming = (state.pending_events || []).filter(
        (e) => !seenKeys.has(e.event_key),
      );
      if (incoming.length > 0) {
        setStoryQueue((q) => [...q, ...incoming]);
      }
    } catch (_) {
      /* non-fatal */
    }
  }

  async function dismissCurrentEvent(skipped) {
    const ev = storyQueue[0];
    if (!ev) return;
    setStoryBusy(true);
    try {
      await advanceStory({ event_key: ev.event_key, skipped });
    } catch (_) {
      /* keep dismissing */
    } finally {
      setStoryBusy(false);
      setStoryQueue((q) => q.slice(1));
      try {
        const prof = await getProfile();
        setProfile(prof);
      } catch (_) {
        /* non-fatal */
      }
      refreshStoryQueue();
    }
  }

  // ---------- Run / respond ----------

  async function handleRun(payload) {
    // payload is a type-specific object built by the active editor; see api.runAttempt.
    setRunning(true);
    play('submit');
    // Student is already at their desk when they submit — the cabin→desk
    // transition happened when they clicked "Start task". Don't force the
    // scene here; we want Priya's reply to drive the next transition.
    try {
      const resp = await runAttempt({ ...payload, attempt_number: attemptNumber });
      setLastRun(resp);
      // v3 BUG 2 fix: #team-chat shows only Priya / Zara / Ravi messages.
      // The student's prompt belongs in the editor only — it is NOT a chat
      // message. Arjun's hint also never enters team chat; it routes to
      // the Coffee Corner overlay.
      const replyIsArjun = resp.coach_message.character === 'arjun';
      if (!replyIsArjun) {
        setMessages((m) => [
          ...m,
          {
            id: `priya-${resp.attempt_id}`,
            character: resp.coach_message.character,
            expression: resp.coach_message.expression,
            body: resp.coach_message.body,
            escalation_level: resp.coach_message.escalation_level,
          },
        ]);
      }
      if (replyIsArjun) {
        // v3 multi-turn flow: don't push Arjun's greeting as a hint payload;
        // CoffeeScene fetches the conversation itself via /api/coffee/turn.
        setCoffeeHint(null);
        setCurrentScene('coffee');
        setArjunToast('☕ Looks like you could use a break...');
      }
      play(resp.all_passed ? 'pass' : 'fail');

      // First-try celebration: spec §3.
      if (resp.all_passed && (resp.badges_earned || []).includes('first_try')) {
        setFirstTryOpen(true);
      }

      // v3: Employee of the Month — full-screen cinematic.
      if (resp.employee_of_month_awarded) {
        setEotmAward({
          yearMonth: resp.employee_of_month_awarded,
          displayName: profile?.display_name,
        });
      }

      try {
        const prof = await getProfile();
        setProfile(prof);
      } catch (_) {
        /* non-fatal */
      }
      if (!resp.all_passed) {
        setAttemptNumber((n) => n + 1);
      } else {
        // v3 BUG 1 fix: ticket complete → advance to the next task in the
        // sequence after a short celebration window. The backend has
        // already marked the question complete via mark_completed; we just
        // need to re-fetch so the frontend doesn't re-display the same
        // ticket as Attempt #1.
        setTimeout(() => {
          setLastRun(null);
          setAttemptNumber(1);
          loadOffice();
        }, 2500);
      }
      refreshStoryQueue();
    } catch (err) {
      // v3 BUG 2 fix: Zara NEVER appears in #team-chat. She assesses
      // internally only — her output goes to the Coach Agent (Priya).
      // Submit failures surface as a neutral system banner (loadError)
      // and a full console log, NOT as a fake character message.
      // eslint-disable-next-line no-console
      console.error('[run] submit failed', err);
      const detail = err?.isNetwork
        ? `Could not reach the backend. ${err.message}`
        : err?.message || 'Submit failed — please try again.';
      setLoadError(detail);
    } finally {
      setRunning(false);
    }
  }

  async function handleRespond(text) {
    setRespondBusy(true);
    try {
      const resp = await respondToCoach({ student_response: text });
      setMessages((m) => [
        ...m,
        { id: `player-resp-${Date.now()}`, character: 'player', body: text },
        {
          id: `priya-resp-${Date.now()}`,
          character: resp.coach_followup.character,
          expression: resp.coach_followup.expression,
          body: resp.coach_followup.body,
        },
      ]);
      play('message');
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          id: `error-${Date.now()}`,
          character: 'zara',
          expression: 'concerned',
          body: `Could not deliver your message: ${err.message}`,
        },
      ]);
    } finally {
      setRespondBusy(false);
    }
  }

  function handleLogout() {
    logout();
    setAuthed(false);
    setProfile(null);
    setTask(null);
    setMessages([]);
    setAttemptNumber(1);
    setLastRun(null);
    setBootstrapped(false);
    prevLevelRef.current = null;
    prevBadgeKeysRef.current = new Set();
  }

  if (!authed) {
    return (
      <>
        <CustomCursor />
        <Login onAuthed={() => setAuthed(true)} />
      </>
    );
  }

  if (!bootstrapped) {
    return (
      <div className="min-h-full grid place-items-center text-nxt-muted text-sm">
        Loading your account…
      </div>
    );
  }

  if (profile && !profile.onboarding_done) {
    return (
      <>
        <CustomCursor />
        <OnboardingFlow
          initialProfile={profile}
          onSubmit={handleOnboardingSubmit}
          onComplete={() => {}}
        />
      </>
    );
  }

  const lastPriya = [...messages].reverse().find((m) => m.character === 'priya');
  const priyaExpression = lastPriya?.expression || 'neutral';

  return (
    <div className="h-full flex flex-col bg-nxt-bg">
      <CustomCursor />
      <TopBar
        profile={profile}
        onLogout={handleLogout}
        onOpenProfile={() => setProfileOpen(true)}
        onToggleSound={toggleSound}
        soundOn={soundOn}
      />

      <ProfileModal
        profile={profile}
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
      />

      {!running && storyQueue.length > 0 && (
        <StoryEventOverlay
          event={storyQueue[0]}
          busy={storyBusy}
          onContinue={() => dismissCurrentEvent(false)}
          onSkip={() => dismissCurrentEvent(true)}
        />
      )}

      <BadgeUnlock
        queue={badgeQueue}
        onDismiss={(k) => setBadgeQueue((q) => q.filter((x) => x !== k))}
      />

      <FirstTryBanner
        open={firstTryOpen}
        onDone={() => setFirstTryOpen(false)}
      />

      <PromotionCinematic
        open={!!promo}
        displayName={promo?.displayName}
        newTitle={promo?.newTitle}
        onDismiss={() => setPromo(null)}
      />

      <EmployeeOfMonthCinematic
        award={eotmAward}
        profile={profile}
        onDismiss={() => setEotmAward(null)}
      />

      <Day1Arrival
        open={day1Open}
        onDone={() => {
          setDay1Open(false);
          onboardingJustCompletedRef.current = false;
          loadOffice();
          refreshStoryQueue();
        }}
      />

      {loadError && (
        <div className="m-3 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/40 text-sm text-red-300">
          {loadError}
        </div>
      )}

      <div className="flex-1 min-h-0 grid grid-cols-12 gap-3 p-3">
        {/* v5: Meeting Room is a FULL-WIDTH takeover — left transcript +
            right notes only. Center TaskPanel and right ChatPanel are
            hidden while the briefing plays. Switches back to the standard
            3-column layout (scene / task / chat) for every other scene. */}
        <section
          className={
            (currentScene === 'meeting' ? 'col-span-12' : 'col-span-3') +
            ' min-h-0'
          }
        >
          <SceneManager
            currentScene={currentScene}
            profile={profile}
            task={task}
            priyaExpression={priyaExpression}
            onCoffeeBack={handleCoffeeBack}
            meetingNotes={meetingNotes}
            onMeetingNotesChange={setMeetingNotes}
            onMeetingDone={handleMeetingDone}
          />
        </section>
        {currentScene !== 'meeting' && (
          <>
            <section className="col-span-6 min-h-0">
              <TaskPanel
                task={task}
                attemptNumber={attemptNumber}
                running={running}
                onRun={handleRun}
                lastRun={lastRun}
                loading={loading}
                inCabin={currentScene === 'cabin'}
                inMeeting={currentScene === 'meeting'}
                onStartTask={handleStartTask}
              />
            </section>
            <section className="col-span-3 min-h-0">
              <ChatPanel
                messages={messages}
                playerName={profile?.display_name || 'You'}
                avatarId={profile?.avatar_id}
                onRespond={handleRespond}
                respondBusy={respondBusy}
              />
            </section>
          </>
        )}
      </div>

      <AnimatePresence>
        {arjunToast && (
          <motion.div
            role="status"
            aria-live="polite"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="pointer-events-none fixed top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-full bg-nxt-coffee/95 text-nxt-text border border-nxt-lamp shadow-panel text-sm font-medium backdrop-blur"
          >
            {arjunToast}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
