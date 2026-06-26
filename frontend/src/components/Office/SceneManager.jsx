import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import CabinScene from './CabinScene.jsx';
import DeskScene from './DeskScene.jsx';
import CoffeeScene from './CoffeeScene.jsx';
import MeetingRoomScene from './MeetingRoomScene.jsx';
import WalkAnimation from './WalkAnimation.jsx';

// SceneManager: the left panel. Renders one of cabin/desk/coffee. Handles
// transition via WalkAnimation when `currentScene` changes.
//
// Props:
//   currentScene      - 'cabin' | 'meeting' | 'desk' | 'coffee'
//   profile           - PlayerProfile (used for desk callout + coffee bubbles)
//   task              - current TaskView (drives DeskScene monitor + meeting script)
//   priyaExpression   - drives Priya's face in CabinScene
//   onCoffeeBack      - coffee scene "Head back to my desk →" handler
//   meetingNotes      - student's notes (controlled by App)
//   onMeetingNotesChange - notes auto-save callback
//   onMeetingDone     - meeting scene "Go to my desk →" handler
export default function SceneManager({
  currentScene = 'cabin',
  profile,
  task,
  priyaExpression = 'happy',
  onCoffeeBack,
  meetingNotes = '',
  onMeetingNotesChange,
  onMeetingDone,
}) {
  // Local "displayed" scene lags the prop so we can swap during the walk fade.
  const [displayed, setDisplayed] = useState(currentScene);
  const [transitioning, setTransitioning] = useState(false);
  const fromRef = useRef(currentScene);

  useEffect(() => {
    if (currentScene === displayed) return;
    // Start transition. WalkAnimation swaps displayed at midpoint and clears
    // `transitioning` on complete.
    fromRef.current = displayed;
    setTransitioning(true);
  }, [currentScene, displayed]);

  function renderScene(name) {
    if (name === 'cabin') return <CabinScene priyaExpression={priyaExpression} />;
    if (name === 'meeting') return <MeetingRoomScene
      script={task?.meeting_script || []}
      initialNotes={meetingNotes}
      onNotesChange={onMeetingNotesChange}
      onDone={onMeetingDone}
    />;
    if (name === 'coffee') return <CoffeeScene
      open={currentScene === 'coffee'}
      profile={profile}
      onBack={onCoffeeBack}
    />;
    return <DeskScene profile={profile} task={task} meetingNotes={meetingNotes} />;
  }

  return (
    <div className="relative h-full w-full">
      <AnimatePresence mode="wait">
        <motion.div
          key={displayed}
          initial={{ opacity: 0.2 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35 }}
          className="absolute inset-0"
        >
          {renderScene(displayed)}
        </motion.div>
      </AnimatePresence>

      {transitioning && (
        <WalkAnimation
          from={fromRef.current}
          to={currentScene}
          playerName={profile?.display_name || 'You'}
          onMidpoint={() => setDisplayed(currentScene)}
          onComplete={() => setTransitioning(false)}
        />
      )}
    </div>
  );
}
