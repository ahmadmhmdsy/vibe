// apps/vibe/src/features/onboarding/FirstRun.tsx
// Shown instead of an empty chat when no provider is configured yet: a fresh
// install used to open on a dead composer, and the only clue was a 500 later.
//
// The panel answers three questions in order - what this is, why it cannot be
// used yet, what to do now. The provider list decides the second answer:
// providers that exist but have no key are a different problem from a catalog
// that returned nothing, and only the first one has a next step in Settings.
import { Button } from "../../components/ui/Button";
import { Icon } from "../../components/icons/Icon";
import { Kbd } from "../../components/ui/Kbd";
import { isMacPlatform } from "../../lib/platform";
import { EXAMPLE_PROMPTS } from "./examples";
import { useFirstRunStore } from "./store";
import "./onboarding.css";

export function FirstRun({
  onOpenSettings,
  onUseExample,
}: {
  onOpenSettings: () => void;
  onUseExample: (prompt: string) => void;
}) {
  const providers = useFirstRunStore((s) => s.providers);
  // The shortcut label has to name a key this keyboard actually has.
  const settingsKey = isMacPlatform() ? "Cmd" : "Ctrl";
  const hasProviders = providers.length > 0;

  return (
    <section className="first-run scroll-region" aria-labelledby="first-run-title">
      <div className="first-run-inner">
        <h2 id="first-run-title" className="first-run-title">
          {hasProviders ? "Add a provider key" : "No model provider is reachable"}
        </h2>
        <p className="first-run-lead">
          vibe is a local-first IDE. Describe an app in plain English and the agent writes the
          files, installs the dependencies, and runs a live preview on this machine.
        </p>
        <p className="first-run-why">
          {hasProviders
            ? "A provider is listed below, but none has a key configured, so the first prompt would fail. The key is stored on this machine and is sent only to the provider you choose."
            : "The provider catalog came back empty, so there is nothing for a prompt to reach. Check that the local server is running, then open settings."}
        </p>

        <div className="first-run-primary">
          {/* One action, not three: everything else on this panel is either an
              explanation or an example, never a second path into Settings. */}
          <Button variant="primary" onClick={onOpenSettings}>
            {hasProviders ? "Add a provider key" : "Open settings"}
          </Button>
          <span className="first-run-shortcut muted">
            or press <Kbd keys={[settingsKey, ","]} />
          </span>
        </div>

        <h3 className="section-label first-run-section-label">Getting started</h3>
        <ol className="first-run-steps">
          <li>Add a provider key in settings.</li>
          <li>Describe the app you want in the composer.</li>
          <li>Watch the agent build, run, and preview it.</li>
        </ol>

        <h3 className="section-label first-run-section-label" id="first-run-examples-label">
          Start from an example
        </h3>
        <ul
          className="first-run-examples"
          aria-labelledby="first-run-examples-label"
          aria-describedby="first-run-examples-hint"
        >
          {EXAMPLE_PROMPTS.slice(0, 4).map((prompt) => (
            <li key={prompt}>
              <button
                type="button"
                className="first-run-example"
                onClick={() => onUseExample(prompt)}
              >
                <Icon name="message" size={16} className="first-run-example-icon" />
                <span className="first-run-example-text">{prompt}</span>
                <Icon name="arrowRight" size={16} className="first-run-example-go" />
              </button>
            </li>
          ))}
        </ul>
        <p className="first-run-example-hint" id="first-run-examples-hint">
          Choosing a prompt opens a new session with it in the composer. Nothing is sent until you
          press Send.
        </p>
      </div>
    </section>
  );
}
