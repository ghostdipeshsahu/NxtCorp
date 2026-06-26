export default function WelcomeScreen({ username, onNext }) {
  return (
    <div
      className="text-center"
      style={{ userSelect: 'none', WebkitUserSelect: 'none', MozUserSelect: 'none' }}
    >
      <div className="mx-auto w-14 h-14 rounded-2xl bg-nxt-accent grid place-items-center text-white font-display text-2xl mb-4 shadow-panel">
        N
      </div>
      <h1 className="font-display text-3xl text-nxt-text mb-2">
        Welcome to NxtCorp.
      </h1>
      <p className="text-nxt-muted text-sm mb-6">
        Hyderabad Office · AI Trainee
      </p>

      <div className="text-left bg-nxt-panel/60 border border-nxt-border rounded-xl p-4 mb-6 text-sm text-nxt-text/85 leading-relaxed">
        <p className="mb-2">
          Hey {username || 'there'} — congratulations, you're in.
        </p>
        <p className="mb-2">
          You're starting as an <span className="text-nxt-gold font-medium">AI Trainee</span> at NxtCorp, a fast-moving tech company in Hyderabad.
        </p>
        <p className="mb-2">
          Your job is not to write code yourself. You work with stakeholders to understand what needs to be built, use AI to build it, verify the output is correct, and fix it when it isn't.
        </p>
        <p className="mb-2">
          That's how real developers work today. That's what you'll learn here.
        </p>
        <p>
          Before you head to your desk, let's get you set up. Two quick choices: your name and your avatar.
        </p>
      </div>

      <button
        type="button"
        onClick={onNext}
        className="w-full rounded-lg bg-nxt-accent hover:brightness-110 text-white font-medium py-2.5 transition shadow-panel"
      >
        Let's go →
      </button>
    </div>
  );
}
